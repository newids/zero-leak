#!/usr/bin/env python3
"""
VLM 스모크 테스트 (VLM 담당). 실제 캡처 1장 + 요소 목록을 agent/llm.py 의 진짜 코드 경로로 보내
원문 응답·JSON 준수·지연시간·승격 여부를 확인한다. agent.py 전체 루프 없이 모델만 시험할 때 쓴다.

실행 (저장소 루트에서):
  python infra/probe_vlm.py                      # .env 의 LLM_PROVIDER (기본 vllm)
  python infra/probe_vlm.py --provider claude    # 비교용
  python infra/probe_vlm.py --case shop_pw       # 다른 화면
.env 는 직접 읽는다 (python-dotenv 미사용 프로젝트).
"""
from __future__ import annotations
import argparse, json, os, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))


def load_env():
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


# 시험 화면: mock 실행으로 만든 shots/ 와 같은 페이지의 요소 목록 (som.js 출력과 동일 형식)
CASES = {
    "webhard_trap": dict(
        goal="withdraw", shot="shots/데모웹하드_step_04.png",
        screen=dict(path="/webhard/leave1", title="잠깐만요!", headings=["잠깐만요!"], elements=[
            {"n": 1, "label": "혜택을 유지하고 계속 이용하기", "kind": "link", "x": 0, "y": 0},
            {"n": 2, "label": "포기하고 떠나기", "kind": "link", "x": 0, "y": 0}]),
        expect={"tool": "click", "n": 2}),
    "shop_pw": dict(
        goal="change", shot="shots/데모쇼핑_step_06.png",
        screen=dict(path="/shop/pw", title="비밀번호 변경", headings=["비밀번호 변경"], elements=[
            {"n": 1, "label": "현재 비밀번호 (비밀번호)", "kind": "input", "x": 0, "y": 0},
            {"n": 2, "label": "새 비밀번호 (비밀번호)", "kind": "input", "x": 0, "y": 0},
            {"n": 3, "label": "변경하기", "kind": "button", "x": 0, "y": 0}]),
        expect={"tool": "fill", "n": 1, "field": "current_password"}),
    "shop_account": dict(
        goal="change", shot="shots/데모쇼핑_step_05.png",
        screen=dict(path="/shop/account", title="회원정보 수정", headings=["회원정보 수정"], elements=[
            {"n": 1, "label": "비밀번호 변경", "kind": "link", "x": 0, "y": 0},
            {"n": 2, "label": "배송지 관리", "kind": "link", "x": 0, "y": 0}]),
        expect={"tool": "click", "n": 1}),
}


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=os.getenv("LLM_PROVIDER", "vllm"))
    ap.add_argument("--case", choices=sorted(CASES), default="webhard_trap")
    ap.add_argument("--all", action="store_true", help="모든 케이스 실행")
    args = ap.parse_args()

    import llm as llm_mod

    # 임시 대체: llm._claude 는 temperature=0 을 보내는데 claude-opus-4-8 은 이를 400 으로 거부한다
    # ("`temperature` is deprecated for this model"). 진짜 수정은 agent/llm.py (개발자) 에서 해야 하며,
    # 그 전까지 이 probe 안에서만 temperature 없는 버전으로 바꿔 끼운다. 그 외 동작은 원본과 동일.
    def _claude_no_temperature(messages_text, system, img_path, *, api_key, model, max_tokens=300):
        import anthropic
        llm_mod.MONITOR.scan(system + messages_text, f"claude:{model}")
        client = anthropic.Anthropic(api_key=api_key)
        blocks = [{"type": "text", "text": messages_text}]
        if img_path and os.path.exists(img_path):
            blocks.insert(0, {"type": "image", "source": {
                "type": "base64", "media_type": "image/png", "data": llm_mod._b64(img_path)}})
        msg = client.messages.create(model=model, max_tokens=max_tokens, system=system,
                                     messages=[{"role": "user", "content": blocks}])
        return "".join(b.text for b in msg.content if b.type == "text")
    llm_mod._claude = _claude_no_temperature

    from llm import LLM, Screen, MONITOR, _openai_compatible, _claude, _system_prompt, _user_prompt, _parse
    MONITOR.add_secrets("Test1234!", "N9#mK2$pLq7!")
    names = sorted(CASES) if args.all else [args.case]
    ok_all = True

    for name in names:
        c = CASES[name]
        scr = Screen.from_js(c["screen"])
        img = str(ROOT / c["shot"])
        if not os.path.exists(img):
            sys.exit(f"{c['shot']} 없음 — 먼저 cd agent && python agent.py --all --provider mock --no-confirm")
        print(f"\n=== {name}  provider={args.provider}  shot={c['shot']}")

        # 1) 원문 응답: JSON 준수 여부를 눈으로 본다 (가드레일·승격 없이 1차 호출만)
        t0 = time.time()
        if args.provider == "vllm":
            raw = _openai_compatible(_user_prompt(c["goal"], scr, []), _system_prompt(), img,
                                     base_url=os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1"),
                                     api_key=os.getenv("VLLM_API_KEY", "EMPTY"),
                                     model=os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct"))
        elif args.provider == "claude":
            raw = _claude(_user_prompt(c["goal"], scr, []), _system_prompt(), img,
                          api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                          model=os.getenv("CLAUDE_MODEL", "claude-opus-4-8"))
        else:
            raw = "(mock: 원문 없음)"
        raw_ms = int((time.time() - t0) * 1000)
        print(f"[원문 {raw_ms}ms] {raw.strip()[:300]!r}")
        if args.provider != "mock":
            parsed = _parse(raw)
            print(f"[파싱] {parsed.as_dict()} conf={parsed.confidence:.2f}"
                  + ("  <-- JSON 파싱 실패" if parsed.confidence == 0.0 and parsed.tool == "handoff" else ""))

        # 2) 실제 경로: decide() = 1차 + 승격 + 가드레일
        llm = LLM(args.provider)
        act = llm.decide(c["goal"], scr, [], img_path=img)
        got = {k: v for k, v in act.as_dict().items() if k in c["expect"]}
        ok = got == c["expect"]
        ok_all &= ok
        print(f"[decide {llm.last_ms}ms via {llm.last_route}] {act.as_dict()} conf={act.confidence:.2f}"
              f"  기대={c['expect']}  {'✅' if ok else '❌'}")

    print(f"\n평문 감시: 검사 {MONITOR.checked}건 · 위반 {len(MONITOR.violations)}건")
    sys.exit(0 if ok_all and not MONITOR.violations else 1)


if __name__ == "__main__":
    main()
