#!/usr/bin/env python3
"""
VLM 스모크 테스트 (VLM 담당). 테스트베드의 실제 화면을 Playwright 로 열어 som.js 로 요소 목록·캡처를 만들고,
agent/llm.py 의 진짜 코드 경로(decide = 1차 + 승격 + 가드레일)로 보내 원문 응답·JSON 준수·지연·판정을 확인한다.
요소 목록을 손으로 적지 않고 매번 현재 테스트베드에서 생성하므로, 테스트베드 레이아웃이 바뀌어도 그대로 쓴다.
기대값은 번호가 아니라 '문구'로 적고 실행 시점에 번호로 바꾼다.

실행 (저장소 루트, 테스트베드 :5001 기동 상태, .env 는 직접 읽음):
  python infra/probe_vlm.py                      # .env 의 LLM_PROVIDER (기본 vllm)
  python infra/probe_vlm.py --provider claude    # 비교용
  python infra/probe_vlm.py --case webhard_trap  # 한 케이스만
"""
from __future__ import annotations
import argparse, os, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))
TESTBED = os.getenv("TESTBED_URL", "http://localhost:5001")
SHOTS = ROOT / "shots" / "probe"


def load_env():
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


# 케이스: 어느 경로를 열고(prep 으로 입력란을 미리 채울 수 있음), 어떤 한 걸음을 기대하는지.
# expect 의 label 은 요소 문구의 일부 일치. field 는 fill 일 때만.
CASES = {
    "shop_login": dict(goal="change", path="/shop", history=[],
                       expect=dict(tool="fill", label="아이디", field="email")),
    "shop_login_filled": dict(goal="change", path="/shop",
                              prep={"input:not([type=password]):not([type=checkbox]):not([type=submit])": "demo1@zlas.kr",
                                    "input[type=password]": "Test1234!"},
                              history=["/shop|아이디", "/shop|비밀번호"],
                              expect=dict(tool="click", label="로그인")),
    "shop_my": dict(goal="change", path="/shop/my", history=["/shop|로그인"],
                    expect=dict(tool="click", label="정보 변경")),
    "shop_account": dict(goal="change", path="/shop/account", history=["/shop/my|정보 변경"],
                         expect=dict(tool="click", label="비밀번호 변경")),
    "shop_pw": dict(goal="change", path="/shop/pw", history=["/shop/account|비밀번호 변경"],
                    expect=dict(tool="fill", label="현재 비밀번호", field="current_password")),
    "webhard_trap": dict(goal="withdraw", path="/webhard/leave1", history=["/webhard/account|회원 탈퇴"],
                         expect=dict(tool="click", label="포기하고 떠나기")),
}


def capture(pg, som_js, path, prep):
    pg.goto(TESTBED + path, wait_until="networkidle")
    for sel, val in (prep or {}).items():
        loc = pg.locator(sel).first
        if loc.count():
            loc.fill(val)
    d = pg.evaluate(som_js)
    SHOTS.mkdir(parents=True, exist_ok=True)
    shot = SHOTS / (path.strip("/").replace("/", "_") + ".png")
    h = pg.evaluate("Math.min(460, Math.max(220, document.body.scrollHeight + 24))")
    pg.screenshot(path=str(shot), clip={"x": 0, "y": 0, "width": 720, "height": h})
    return d, str(shot)


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=os.getenv("LLM_PROVIDER", "vllm"))
    ap.add_argument("--case", choices=sorted(CASES))
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright
    from llm import LLM, Screen, MONITOR, _openai_compatible, _claude, _system_prompt, _user_prompt, _parse
    MONITOR.add_secrets("Test1234!", "N9#mK2$pLq7!")
    som_js = (ROOT / "agent" / "som.js").read_text()
    names = [args.case] if args.case else list(CASES)
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 720, "height": 460})
        for name in names:
            c = CASES[name]
            d, shot = capture(pg, som_js, c["path"], c.get("prep"))
            scr = Screen.from_js(d)
            exp = c["expect"]
            exp_el = next((e for e in scr.elements if exp["label"] in e["label"]), None)
            print(f"\n=== {name}  provider={args.provider}  {c['path']}  요소 {len(scr.elements)}개")
            if not exp_el:
                print(f"  !! 기대 문구 '{exp['label']}' 가 화면에 없음 — 테스트베드 변경 확인"); results.append(False); continue
            expect = {"tool": exp["tool"], "n": exp_el["n"]} | ({"field": exp["field"]} if "field" in exp else {})

            # 1) 원문: JSON 준수를 눈으로 본다 (승격·가드레일 없이 1차 호출만)
            t0 = time.time()
            if args.provider == "vllm":
                raw = _openai_compatible(_user_prompt(c["goal"], scr, c["history"]), _system_prompt(), shot,
                                         base_url=os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1"),
                                         api_key=os.getenv("VLLM_API_KEY", "EMPTY"),
                                         model=os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct"))
            elif args.provider == "claude":
                raw = _claude(_user_prompt(c["goal"], scr, c["history"]), _system_prompt(), shot,
                              api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                              model=os.getenv("CLAUDE_MODEL", "claude-opus-4-8"))
            else:
                raw = "(mock: 원문 없음)"
            print(f"  [원문 {int((time.time()-t0)*1000)}ms] {raw.strip()[:200]!r}")
            if args.provider != "mock":
                pa = _parse(raw)
                print(f"  [파싱] {pa.as_dict()} conf={pa.confidence:.2f}"
                      + ("  <-- JSON 파싱 실패" if pa.confidence == 0.0 and pa.tool == "handoff" else ""))

            # 2) 실제 경로: decide() = 1차 + 반복 감지 + 승격 + 가드레일
            llm = LLM(args.provider)
            act = llm.decide(c["goal"], scr, c["history"], img_path=shot)
            got = {k: v for k, v in act.as_dict().items() if k in expect}
            ok = got == expect
            results.append(ok)
            lab = next((e["label"] for e in scr.elements if e["n"] == act.n), "") if act.n is not None else ""
            print(f"  [decide {llm.last_ms}ms via {llm.last_route}] {act.as_dict()} '{lab}' conf={act.confidence:.2f}"
                  f"  기대={expect} '{exp_el['label']}'  {'✅' if ok else '❌'}")
        browser.close()

    print(f"\n결과: {sum(results)}/{len(results)} ✅ · 평문 감시: 검사 {MONITOR.checked}건 · 위반 {len(MONITOR.violations)}건")
    sys.exit(0 if all(results) and not MONITOR.violations else 1)


if __name__ == "__main__":
    main()
