#!/usr/bin/env python3
"""
Zero-Leak 자율 조치 에이전트 (로컬 실행 — 분리 실행의 '손').
사이트 열기 → SoM 번호 배지 주입 + 비밀번호 마스킹 → 스크린샷 →
llm.decide() 로 다음 액션(클라우드의 '눈') → 가드레일 통과 시 실행 → 반복(최대 N단계).
handoff 가 나오면 shared/approve.flag 를 기다린다.

증명 포인트
- 비밀번호 평문은 이 프로세스 안에만 있다(FIELD_VALUES / vault.json).
- 외부 모델로 나가는 텍스트는 llm.MONITOR 가 전부 검사해 비밀번호 포함 건수를 센다.
- 브라우저가 테스트베드(localhost) 밖으로 비밀번호를 보내면 그것도 센다.
- 두 값이 state.json summary.plaintext_sent 로 기록된다. 데모에서는 0 이어야 한다.

실행:
  python agent.py --site shop      # 데모쇼핑 비밀번호 변경
  python agent.py --site webhard   # 데모웹하드 탈퇴
  python agent.py --all            # risk.json 순서대로 전부
  --provider mock|vllm|claude|openai   --headful (브라우저 창 표시)
"""
from __future__ import annotations
import argparse, datetime, json, os, pathlib, sys, time
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, Error as PWError
from llm import LLM, MONITOR, Screen, Action

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHARED = ROOT / "shared"
SHOTS = ROOT / "shots"
SHOTS.mkdir(exist_ok=True)
SOM_JS = (pathlib.Path(__file__).parent / "som.js").read_text()

MAX_STEPS = int(os.getenv("MAX_STEPS", "12"))
APPROVE_TIMEOUT = int(os.getenv("APPROVE_TIMEOUT", "30"))   # 승인 대기 최대 초
HANDOFF_POLL = 0.5
TESTBED_HOSTS = {"localhost", "127.0.0.1"}
ALLOWED_HOSTS = set(TESTBED_HOSTS)      # --allow-host 로 실제 사이트를 명시적으로 추가할 때만 넓어진다
APPROVE_STDIN = False                   # --approve-enter: 승인 대기 중 터미널 Enter 로도 승인
VIEWPORT = {"width": 720, "height": 460}
# 최종 제출 버튼 앞에서 사람 승인을 받는다 (데모: "변경 직전에 멈추고 [변경 확정]").
CONFIRM_WORDS = ["변경하기", "비밀번호 변경", "회원 탈퇴", "탈퇴하기", "저장", "제출"]
# 제출 뒤 같은 화면에 이런 문구가 보이면 실패한 것 — 다시 입력하지 않고 사람에게 넘긴다
ERROR_WORDS = ["일치하지 않", "사용할 수 없", "올바르지 않", "오류", "실패", "잘못", "다시 입력"]


def is_submit(target: dict) -> bool:
    return target["kind"] == "button" and any(w in target["label"] for w in CONFIRM_WORDS)


def password_inputs(scr: Screen, empty_only: bool) -> list[dict]:
    pw = [e for e in scr.elements if e["kind"] == "input"
          and ("비밀번호" in e["label"] or "password" in e["label"].lower())]
    return [e for e in pw if "(입력됨)" not in e["label"]] if empty_only else pw


def password_field_for(label: str) -> str:
    low = label.lower()
    return "current_password" if any(k in label for k in ("현재", "기존", "지금")) or "current" in low else "new_password"

# 데모용 입력 값 (실제 비밀번호 아님). 실제 서비스에서는 OS 키체인에서 읽는다.
# 실제 사이트 테스트: ZL_EMAIL / ZL_CURRENT_PASSWORD / ZL_NEW_PASSWORD / ZL_REASON 환경변수가 있으면 그 값을 쓴다.
# 값은 코드·로그·state.json·화면 어디에도 찍지 않는다. llm.MONITOR 와 네트워크 감시의 검색어로만 쓴다.
FIELD_VALUES = {
    "email": os.getenv("ZL_EMAIL", "demo1@zlas.kr"),
    "current_password": os.getenv("ZL_CURRENT_PASSWORD", "Test1234!"),
    "new_password": os.getenv("ZL_NEW_PASSWORD", "N9#mK2$pLq7!"),
    "reason": os.getenv("ZL_REASON", "서비스를 더 이상 사용하지 않음"),
}


def now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


class State:
    def __init__(self, provider: str):
        self.path = SHARED / "state.json"
        self.data = {"run_id": now(), "provider": provider, "current": {}, "steps": [],
                     "summary": {"sites": 0, "changed": 0, "withdrawn": 0, "skipped": 0,
                                 "elapsed_s": 0, "plaintext_sent": 0,
                                 "outbound_checked": 0}}
        self.t0 = time.time()
        self.browser_leaks: list[str] = []
        self.flush()

    def set_current(self, site, action, step, status):
        self.data["current"] = {"site": site, "action": action, "step": step, "status": status}
        self.flush()

    def log(self, n, site, action_json, status, shot, vlm_ms, route):
        self.data["steps"].append({"n": n, "site": site, "action_json": action_json,
                                   "status": status, "shot": shot, "vlm_ms": vlm_ms,
                                   "route": route, "ts": now()})
        self.flush()

    def finish_site(self, action):
        self.data["summary"]["changed" if action == "change" else "withdrawn"] += 1
        self.flush()

    def flush(self):
        s = self.data["summary"]
        s["elapsed_s"] = round(time.time() - self.t0, 1)
        s["plaintext_sent"] = len(MONITOR.violations) + len(self.browser_leaks)
        s["outbound_checked"] = MONITOR.checked
        self.data["leaks"] = MONITOR.violations + self.browser_leaks
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2))


SUBMIT_RESPONSES: list[dict] = []   # 제출 판정용: 조작 대상 사이트로 간 비-GET 요청의 응답 (상태 코드·경로만, 본문은 보지 않음)


def attach_network_monitor(page, state: State):
    """브라우저가 테스트베드 밖으로 비밀번호를 보내는지 감시 + 제출 응답 기록."""
    secrets = [v for k, v in FIELD_VALUES.items() if "password" in k]
    def on_response(resp):
        req = resp.request
        host = urlparse(req.url).hostname or ""
        if req.method in ("POST", "PUT", "PATCH") and (
                host in ALLOWED_HOSTS or any(host.endswith("." + h) for h in ALLOWED_HOSTS)):
            SUBMIT_RESPONSES.append({"t": time.time(), "method": req.method,
                                     "path": urlparse(req.url).path, "status": resp.status})
    page.on("response", on_response)
    def on_request(req):
        host = urlparse(req.url).hostname or ""
        # 조작 대상 사이트 자신(하위 도메인 포함: account.example.com)에게 비밀번호를 보내는 건 정상 (로그인·변경 폼)
        if host in ALLOWED_HOSTS or any(host.endswith("." + h) for h in ALLOWED_HOSTS):
            return
        body = (req.post_data or "") + req.url
        for s in secrets:
            if s in body:
                state.browser_leaks.append(f"browser→{host}: 비밀번호 포함")
    page.on("request", on_request)


def wait_for_approval(site: str) -> str:
    """'approved' | 'skipped' | 'timeout'.  approve.flag = 승인, skip.flag = 이 사이트 건너뛰기."""
    flag, skip = SHARED / "approve.flag", SHARED / "skip.flag"
    flag.unlink(missing_ok=True)
    skip.unlink(missing_ok=True)
    if APPROVE_STDIN:                   # 실제 사이트 테스트: 대시보드 없이 터미널에서 바로 승인
        try:
            ans = input(f"  ⏸  승인 대기: {site} — Enter=승인 / s=건너뛰기 / n=중단 > ").strip().lower()
        except EOFError:
            ans = "n"
        if ans == "":
            print("  ▶  승인 확인"); return "approved"
        if ans == "s":
            print("  ↷  사용자가 건너뜀"); return "skipped"
        print("  ✗  사용자가 중단"); return "timeout"
    print(f"  ⏸  승인 대기: {site} (shared/approve.flag | skip.flag, {APPROVE_TIMEOUT}s)")
    deadline = time.time() + APPROVE_TIMEOUT
    while time.time() < deadline:
        if flag.exists():
            flag.unlink()
            print("  ▶  승인 확인")
            return "approved"
        if skip.exists():
            skip.unlink()
            print("  ↷  사용자가 건너뜀")
            return "skipped"
        time.sleep(HANDOFF_POLL)
    print("  ✗  승인 시간 초과")
    return "timeout"


def settle(page, timeout_ms: int = 8000):
    """페이지 이동이 끝날 때까지 기다린다. 실제 사이트는 클릭 뒤 이동에 1~2초가 걸리고,
    이동 중에 som.js 를 실행하면 'Execution context was destroyed' 로 죽는다."""
    try:
        page.wait_for_load_state("load", timeout=timeout_ms)
    except PWError:
        pass                         # 계속 네트워크가 도는 사이트는 load 가 늦어도 그냥 진행


def capture(page, shot_path: pathlib.Path) -> Screen:
    """som.js 실행 + 캡처. 이동 중이면 잠깐 기다렸다 다시 시도한다."""
    for attempt in range(6):
        settle(page)
        try:
            scr = Screen.from_js(page.evaluate(SOM_JS))
            h = page.evaluate(f"Math.min({VIEWPORT['height']}, Math.max(220, document.body.scrollHeight + 24))")
            page.screenshot(path=str(shot_path), clip={"x": 0, "y": 0, "width": VIEWPORT["width"], "height": h})
            return scr
        except PWError as e:
            if "Execution context was destroyed" in str(e) or "navigat" in str(e).lower():
                page.wait_for_timeout(700)
                continue
            raise
    raise RuntimeError("페이지가 계속 이동 중이라 화면을 읽지 못함")


def run_site(page, llm: LLM, state: State, site: str, url: str, action: str,
             confirm: bool = True) -> str:
    print(f"\n▶ {site} ({action}) — {url}")
    page.goto(url, wait_until="domcontentloaded")
    settle(page, 15000)
    history: list[str] = []          # "<path>|<label>"
    result = "incomplete"
    step = 0
    submitted_path = None            # 최종 제출을 누른 경로. 같은 화면에 머물면 완료/오류를 규칙으로 판정한다
    submitted_at = 0.0               # 제출 클릭 시각. 그 뒤의 서버 응답만 판정에 쓴다

    for step in range(1, MAX_STEPS + 1):
        page.wait_for_timeout(200)
        shot = f"shots/{site}_step_{step:02d}.png"
        scr = capture(page, ROOT / shot)

        if submitted_path and scr.path == submitted_path:
            # 제출 뒤에도 같은 화면: 완료 페이지가 없는 사이트(리디북스 등). 다시 입력·재제출은 절대 하지 않는다.
            # 판정 순서: 완료 문구 → 오류 문구 → 서버 응답(제출 뒤 비-GET 요청의 상태 코드) → 입력란 초기화 → 사람 확인
            errs = [h for h in scr.headings if any(w in h for w in ERROR_WORDS)]
            pw = password_inputs(scr, empty_only=False)
            resps = [r for r in SUBMIT_RESPONSES if r["t"] >= submitted_at]
            ok2xx = [r for r in resps if 200 <= r["status"] < 300]
            bad4xx = [r for r in resps if r["status"] >= 400]
            if scr.is_done():
                act, llm.last_route = Action("done", confidence=1.0), "rule:완료 문구"
            elif errs:
                act, llm.last_route = Action("handoff", reason=f"제출 후 오류 표시: {errs[0][:60]}", confidence=0.0), "rule:제출 후 오류"
            elif bad4xx and not ok2xx:
                act, llm.last_route = Action("handoff", reason=f"제출 응답 {bad4xx[0]['status']} {bad4xx[0]['path'][:40]}", confidence=0.0), "rule:서버 응답 오류"
            elif ok2xx:
                act, llm.last_route = Action("done", reason=f"제출 응답 {ok2xx[0]['status']} {ok2xx[0]['method']} {ok2xx[0]['path'][:40]}", confidence=0.95), "rule:서버 응답 2xx"
            elif pw and all("(입력됨)" not in e["label"] for e in pw):
                act, llm.last_route = Action("done", reason="제출 후 입력란 초기화", confidence=0.9), "rule:폼 초기화"
            else:
                act, llm.last_route = Action("handoff", reason="제출 후 완료를 확인할 수 없음 — 사람이 확인", confidence=0.0), "rule:제출 후 미확인"
            llm.last_ms = 0
        else:
            act = llm.decide(action, scr, history, img_path=str(ROOT / shot))
        state.set_current(site, action, step, "running")
        print(f"  [{step:02d}] {scr.path:<20} {act.as_dict()}  conf={act.confidence:.2f} "
              f"{llm.last_ms}ms via {llm.last_route}")

        if act.tool == "done":
            state.log(step, site, act.as_dict(), "done", shot, llm.last_ms, llm.last_route)
            result = "done"
            break

        if act.tool == "handoff":
            state.log(step, site, act.as_dict(), "handoff", shot, llm.last_ms, llm.last_route)
            r = wait_for_approval(site)
            if r == "approved":
                if submitted_path and scr.path == submitted_path:
                    # 제출 뒤 사람이 확인하고 승인 = 완료. 재입력으로 돌아가지 않는다.
                    state.log(step, site, {"tool": "done", "reason": "제출 후 사람이 확인"}, "done", shot, 0, "user")
                    result = "done"
                    break
                # 사유 문구는 남기지 않는다 — 남기면 모델이 다음 단계에서 그 문장을 보고 같은 이유로 또 handoff 한다.
                # 이 표식은 llm.decide 의 반복 감지도 초기화한다 (사람이 개입해 상황이 바뀌었으므로).
                history.append(f"{scr.path}|handoff:사람이 처리함")
                continue
            result = "skipped" if r == "skipped" else "handoff_timeout"
            break

        target = next((e for e in scr.elements if e["n"] == act.n), None)
        if not target:
            state.log(step, site, act.as_dict(), "bad_n", shot, llm.last_ms, llm.last_route)
            history.append(f"{scr.path}|bad_n:{act.n}")
            continue

        # 빈 비밀번호 입력란이 남았는데 제출을 누르려 하면 가로채서 그 칸부터 채운다 (모델이 확신하며 조기 제출하는 일이 잦다)
        if act.tool == "click" and is_submit(target):
            empties = password_inputs(scr, empty_only=True)
            if empties:
                e = empties[0]
                act = Action("fill", n=e["n"], field=password_field_for(e["label"]), confidence=1.0)
                target = e
                llm.last_route += "+rule:빈칸먼저"
                print(f"       ↺ 제출 전 빈 입력란 '{e['label']}' 먼저 채움 → {act.as_dict()}")

        # 최종 제출 버튼이면 매번 사람 승인 (핸드오프). 한 번 승인으로 다음 제출까지 열어 두지 않는다.
        if confirm and act.tool == "click" and is_submit(target):
            ask = {"tool": "handoff", "reason": f"'{target['label']}' 최종 확정 전 승인 필요"}
            state.log(step, site, ask, "handoff", shot, llm.last_ms, llm.last_route)
            r = wait_for_approval(site)
            if r != "approved":
                result = "skipped" if r == "skipped" else "handoff_timeout"
                break

        try:
            page.mouse.click(target["x"], target["y"])
            if act.tool == "fill":
                page.keyboard.press("Control+A")
                page.keyboard.type(FIELD_VALUES.get(act.field, ""), delay=5)
            elif is_submit(target):
                submitted_path, submitted_at = scr.path, time.time()
                settle(page)                           # 제출 요청의 응답이 돌아올 시간을 준다
                page.wait_for_timeout(800)
            history.append(f"{scr.path}|{target['label']}")
            state.log(step, site, act.as_dict(), "ok", shot, llm.last_ms, llm.last_route)
        except Exception as e:
            state.log(step, site, act.as_dict(), f"err:{e}", shot, llm.last_ms, llm.last_route)
            history.append(f"{scr.path}|err:{target['label']}")
        page.wait_for_timeout(int(os.getenv("STEP_PAUSE_MS", "250")))

    state.set_current(site, action, step, result)
    if result == "done":
        state.finish_site(action)
    elif result == "skipped":
        state.data["summary"]["skipped"] += 1
        state.log(step, site, {"tool": "skip"}, "skipped", shot, 0, "user")
    print(f"  = {site}: {result} ({step} steps)")
    return result


def load_targets(args) -> list[dict]:
    vault = json.loads((SHARED / "vault.json").read_text())
    MONITOR.add_secrets(*[v["password"] for v in vault],
                        *[v for k, v in FIELD_VALUES.items() if "password" in k])
    if args.url:                        # 실제 사이트 테스트 (--allow-host 로 호스트를 명시해야 통과)
        host = urlparse(args.url).hostname or ""
        return [{"site": args.site_name or host, "url": args.url, "action": args.goal}]
    if args.all:
        risk_path = SHARED / "risk.json"
        if not risk_path.exists():
            sys.exit("shared/risk.json 없음 — detect.py 를 먼저 실행")
        return json.loads(risk_path.read_text())
    key = "쇼핑" if args.site == "shop" else "웹하드"
    v = next((x for x in vault if key in x["site"]), None)
    if not v:
        sys.exit(f"vault 에 {key} 사이트 없음")
    return [{"site": v["site"], "url": v["url"],
             "action": "change" if args.site == "shop" else "withdraw"}]


def main():
    global MAX_STEPS, APPROVE_STDIN, VIEWPORT
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", choices=["shop", "webhard"])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--provider", default=os.getenv("LLM_PROVIDER", "mock"))
    ap.add_argument("--headful", action="store_true", help="브라우저 창 표시(데모)")
    ap.add_argument("--record", metavar="DIR",
                    help="에이전트 브라우저 화면을 webm 으로 녹화 (데모 영상용)")
    ap.add_argument("--no-confirm", action="store_true",
                    help="최종 제출 전 승인 대기를 생략 (자동 테스트용)")
    # 실제 사이트 테스트 (본인 소유 계정, 팀 합의 하에만). 기본값은 테스트베드 전용 그대로.
    ap.add_argument("--url", help="조작할 시작 URL. --allow-host 에 그 호스트를 적어야 실행됨")
    ap.add_argument("--allow-host", action="append", default=[], metavar="HOST",
                    help="테스트베드 외 허용 호스트 (반복 가능). 비밀번호는 이 호스트에만 전송 허용")
    ap.add_argument("--goal", choices=["change", "withdraw"], default="change", help="--url 일 때 목표")
    ap.add_argument("--site-name", help="--url 일 때 기록·캡처에 쓸 이름 (기본: 호스트명)")
    ap.add_argument("--max-steps", type=int, default=MAX_STEPS, help=f"최대 단계 (기본 {MAX_STEPS})")
    ap.add_argument("--viewport", default=f"{VIEWPORT['width']}x{VIEWPORT['height']}",
                    help="브라우저 크기 WxH. 실제 사이트는 1280x800 권장")
    ap.add_argument("--approve-enter", action="store_true",
                    help="승인 대기 때 대시보드 대신 터미널 Enter 로 승인 (실제 사이트 테스트용)")
    ap.add_argument("--channel", choices=["chromium", "chrome"], default="chromium",
                    help="chrome = 설치된 Google Chrome 사용. 실제 사이트의 봇 검증(Cloudflare 등)은 진짜 브라우저로 통과")
    ap.add_argument("--user-data-dir", metavar="DIR",
                    help="브라우저 프로필 폴더 (지속 세션). 실제 사이트 테스트용 전용 폴더를 쓰고 개인 프로필은 쓰지 않는다")
    args = ap.parse_args()
    if not args.site and not args.all and not args.url:
        ap.error("--site, --all 또는 --url 필요")

    MAX_STEPS, APPROVE_STDIN = args.max_steps, args.approve_enter
    w, h = (int(x) for x in args.viewport.lower().split("x"))
    VIEWPORT = {"width": w, "height": h}
    ALLOWED_HOSTS.update(args.allow_host)

    targets = load_targets(args)
    for t in targets:
        if (urlparse(t["url"]).hostname or "") not in ALLOWED_HOSTS:
            sys.exit(f"허용되지 않은 사이트 거부: {t['url']}  (--allow-host {urlparse(t['url']).hostname} 로 명시)")
    if args.url:
        print(f"!! 실제 사이트 모드: {args.url}  허용 호스트={sorted(ALLOWED_HOSTS - TESTBED_HOSTS)}  "
              f"계정값 출처={'환경변수' if os.getenv('ZL_CURRENT_PASSWORD') else '데모 기본값(주의)'}")

    llm = LLM(args.provider)
    state = State(llm.provider)
    state.data["summary"]["sites"] = len(targets)
    state.flush()
    print(f"provider={llm.provider}  targets={[t['site'] for t in targets]}")

    with sync_playwright() as p:
        ctx_kw = {"viewport": dict(VIEWPORT)}
        if args.record:
            ctx_kw |= {"record_video_dir": args.record,
                       "record_video_size": dict(VIEWPORT)}
        launch_kw = {"headless": not args.headful}
        if args.channel == "chrome":
            launch_kw["channel"] = "chrome"
        if args.user_data_dir:          # 지속 프로필: 사용자 기기의 진짜 브라우저 세션으로 동작 (분리 실행의 '손')
            browser = None
            context = p.chromium.launch_persistent_context(args.user_data_dir, **launch_kw, **ctx_kw)
            page = context.pages[0] if context.pages else context.new_page()
        else:
            browser = p.chromium.launch(**launch_kw)
            context = browser.new_context(**ctx_kw)
            page = context.new_page()
        attach_network_monitor(page, state)
        for t in targets:
            run_site(page, llm, state, t["site"], t["url"], t["action"],
                     confirm=not args.no_confirm)
        context.close()
        if browser:
            browser.close()

    state.flush()
    s = state.data["summary"]
    print(f"\n완료: 변경 {s['changed']} · 탈퇴 {s['withdrawn']} · 건너뜀 {s['skipped']} · {s['elapsed_s']}s · "
          f"외부 전송 검사 {s['outbound_checked']}건 · 평문 전송 {s['plaintext_sent']}건")
    if state.data["leaks"]:
        print("  !! 평문 노출:", state.data["leaks"])
        sys.exit(2)


if __name__ == "__main__":
    main()
