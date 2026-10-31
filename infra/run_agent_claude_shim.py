#!/usr/bin/env python3
"""
임시 러너: agent/llm.py 의 _claude() 가 temperature=0 을 보내 claude-opus-4-8 에서 400 이 나는 동안,
temperature 없는 대체 함수를 끼워 agent.py 를 그대로 실행한다 (비교 측정용). agent/ 코드는 수정하지 않는다.
개발자가 llm.py 를 고치면 이 파일은 삭제한다.

실행 (저장소 루트, .env 로드 후):  python infra/run_agent_claude_shim.py --site shop --provider claude --no-confirm
"""
from __future__ import annotations
import os, pathlib, runpy, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
AGENT = ROOT / "agent"
sys.path.insert(0, str(AGENT))
os.chdir(AGENT)                      # agent.py 는 자기 폴더 기준 상대 경로(shots/, ../shared)를 쓴다

import llm as llm_mod


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
sys.argv = ["agent.py", *sys.argv[1:]]
runpy.run_path(str(AGENT / "agent.py"), run_name="__main__")
