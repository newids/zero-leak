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

from playwright.sync_api import sync_playwright
from llm import LLM, MONITOR, Screen

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHARED = ROOT / "shared"
SHOTS = ROOT / "shots"
SHOTS.mkdir(exist_ok=True)
SOM_JS = (pathlib.Path(__file__).parent / "som.js").read_text()

MAX_STEPS = 12
APPROVE_TIMEOUT = int(os.getenv("APPROVE_TIMEOUT", "30"))   # 승인 대기 최대 초
HANDOFF_POLL = 0.5
TESTBED_HOSTS = {"localhost", "127.0.0.1"}
# 최종 제출 버튼 앞에서 사람 승인을 받는다 (데모: "변경 직전에 멈추고 [변경 확정]").
CONFIRM_WORDS = ["변경하기", "비밀번호 변경", "회원 탈퇴", "탈퇴하기", "저장", "제출"]

# 데모용 입력 값 (실제 비밀번호 아님). 실제 서비스에서는 OS 키체인에서 읽는다.
FIELD_VALUES = {
    "email": "demo1@zlas.kr",
    "current_password": "Test1234!",
    "new_password": "N9#mK2$pLq7!",
    "reason": "서비스를 더 이상 사용하지 않음",
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


def attach_network_monitor(page, state: State):
    """브라우저가 테스트베드 밖으로 비밀번호를 보내는지 감시."""
    secrets = [v for k, v in FIELD_VALUES.items() if "password" in k]
    def on_request(req):
        host = urlparse(req.url).hostname or ""
        if host in TESTBED_HOSTS:
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


def run_site(page, llm: LLM, state: State, site: str, url: str, action: str,
             confirm: bool = True) -> str:
    print(f"\n▶ {site} ({action}) — {url}")
    page.goto(url, wait_until="networkidle")
    history: list[str] = []          # "<path>|<label>"
    result = "incomplete"
    step = 0
    confirmed = False                # 이 사이트의 최종 제출을 승인받았는가

    for step in range(1, MAX_STEPS + 1):
        page.wait_for_timeout(200)
        scr = Screen.from_js(page.evaluate(SOM_JS))
        shot = f"shots/{site}_step_{step:02d}.png"
        h = page.evaluate("Math.min(460, Math.max(220, document.body.scrollHeight + 24))")
        page.screenshot(path=str(ROOT / shot), clip={"x": 0, "y": 0, "width": 720, "height": h})

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
                history.append(f"{scr.path}|handoff:{act.reason}")
                continue
            result = "skipped" if r == "skipped" else "handoff_timeout"
            break

        target = next((e for e in scr.elements if e["n"] == act.n), None)
        if not target:
            state.log(step, site, act.as_dict(), "bad_n", shot, llm.last_ms, llm.last_route)
            history.append(f"{scr.path}|bad_n:{act.n}")
            continue

        # 최종 제출 버튼이면 먼저 사람 승인 (핸드오프)
        if confirm and not confirmed and act.tool == "click" and target["kind"] == "button" \
                and any(w in target["label"] for w in CONFIRM_WORDS):
            ask = {"tool": "handoff", "reason": f"'{target['label']}' 최종 확정 전 승인 필요"}
            state.log(step, site, ask, "handoff", shot, llm.last_ms, llm.last_route)
            r = wait_for_approval(site)
            if r != "approved":
                result = "skipped" if r == "skipped" else "handoff_timeout"
                break
            confirmed = True

        try:
            page.mouse.click(target["x"], target["y"])
            if act.tool == "fill":
                page.keyboard.press("Control+A")
                page.keyboard.type(FIELD_VALUES.get(act.field, ""), delay=5)
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", choices=["shop", "webhard"])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--provider", default=os.getenv("LLM_PROVIDER", "mock"))
    ap.add_argument("--headful", action="store_true", help="브라우저 창 표시(데모)")
    ap.add_argument("--record", metavar="DIR",
                    help="에이전트 브라우저 화면을 webm 으로 녹화 (데모 영상용)")
    ap.add_argument("--no-confirm", action="store_true",
                    help="최종 제출 전 승인 대기를 생략 (자동 테스트용)")
    args = ap.parse_args()
    if not args.site and not args.all:
        ap.error("--site 또는 --all 필요")

    targets = load_targets(args)
    for t in targets:
        if (urlparse(t["url"]).hostname or "") not in TESTBED_HOSTS:
            sys.exit(f"테스트베드 외 사이트 거부: {t['url']}")

    llm = LLM(args.provider)
    state = State(llm.provider)
    state.data["summary"]["sites"] = len(targets)
    state.flush()
    print(f"provider={llm.provider}  targets={[t['site'] for t in targets]}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headful)
        ctx_kw = {"viewport": {"width": 720, "height": 460}}
        if args.record:
            ctx_kw |= {"record_video_dir": args.record,
                       "record_video_size": {"width": 720, "height": 460}}
        context = browser.new_context(**ctx_kw)
        page = context.new_page()
        attach_network_monitor(page, state)
        for t in targets:
            run_site(page, llm, state, t["site"], t["url"], t["action"],
                     confirm=not args.no_confirm)
        context.close()
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
