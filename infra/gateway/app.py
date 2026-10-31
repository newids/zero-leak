#!/usr/bin/env python3
"""
VLM 게이트웨이 (VLM 담당). vLLM 앞에 서서 OpenAI 호환 형식을 그대로 유지하면서
1) 요청에 logprobs 를 켜 vLLM 에 전달하고,
2) 응답 JSON 의 confidence 를 모델의 자가 보고값(프롬프트 예시를 베낀 0.9) 대신
   실제로 고른 토큰("tool" 값, "n" 숫자)의 확률로 바꿔 넣고,
3) 요청/응답/지연/대안 후보를 JSONL 로 기록한다 (bench 재료).
agent/llm.py 는 수정 없이 VLLM_BASE_URL 만 이 게이트웨이로 바꾸면 된다. 인증은 vLLM 이 그대로 검사한다.

실행: uvicorn app:app --host 0.0.0.0 --port 8080   (환경변수 UPSTREAM, GATEWAY_LOG)
"""
from __future__ import annotations
import json, math, os, pathlib, re, time

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

UPSTREAM = os.getenv("UPSTREAM", "http://127.0.0.1:8000")
LOG = pathlib.Path(os.getenv("GATEWAY_LOG", os.path.expanduser("~/zlas-gateway/requests.jsonl")))
LOG.parent.mkdir(parents=True, exist_ok=True)
TOP_LOGPROBS = 3          # 로그에 남길 대안 후보 수 (2등 번호가 뭐였는지)

app = FastAPI(title="zlas-vlm-gateway")
client = httpx.AsyncClient(base_url=UPSTREAM, timeout=120)

TOOL_RE = re.compile(r'"tool"\s*:\s*"(\w+)"')
N_RE = re.compile(r'"n"\s*:\s*(\d+)')
CONF_RE = re.compile(r'"confidence"\s*:\s*[0-9.]+')


def _span_prob(tokens: list[dict], start: int, end: int) -> tuple[float, list]:
    """토큰 목록에서 문자 구간 [start,end) 에 걸친 토큰들의 결합 확률과 첫 토큰의 대안 후보를 돌려준다."""
    pos, logp, alts, hit = 0, 0.0, [], False
    for t in tokens:
        tok = t.get("token", ""); a, b = pos, pos + len(tok); pos = b
        if b <= start or a >= end:
            continue
        logp += t.get("logprob", 0.0)
        if not hit:
            hit = True
            alts = [{"token": x.get("token"), "p": round(math.exp(x.get("logprob", -99)), 3)}
                    for x in t.get("top_logprobs", [])]
    return (math.exp(logp) if hit else float("nan")), alts


def rescore(content: str, tokens: list[dict]) -> dict:
    """content 의 "tool"/"n" 값 토큰 확률로 confidence 를 계산. 실패하면 빈 dict (원문 유지)."""
    if not tokens:
        return {}
    joined = "".join(t.get("token", "") for t in tokens)
    text = joined if joined == content else content      # 토큰 연결이 원문과 다르면 원문 기준으로 검색
    m_tool, m_n = TOOL_RE.search(text), N_RE.search(text)
    if not m_tool:
        return {}
    p_tool, _ = _span_prob(tokens, *m_tool.span(1))
    out = {"p_tool": round(p_tool, 3), "tool": m_tool.group(1)}
    conf = p_tool
    if m_n:
        p_n, alts = _span_prob(tokens, *m_n.span(1))
        out |= {"p_n": round(p_n, 3), "n": int(m_n.group(1)), "n_alternatives": alts}
        conf = min(conf, p_n)
    if math.isnan(conf):
        return {}
    out["confidence"] = round(max(0.0, min(1.0, conf)), 3)
    return out


def rewrite_confidence(content: str, conf: float) -> str:
    if CONF_RE.search(content):
        return CONF_RE.sub(f'"confidence":{conf}', content, count=1)
    i = content.rfind("}")
    return content if i < 0 else content[:i] + f',"confidence":{conf}' + content[i:]


@app.get("/health")
async def health():
    try:
        r = await client.get("/v1/models", headers={"Authorization": f"Bearer {os.getenv('VLLM_API_KEY', '')}"})
        models = [m["id"] for m in r.json().get("data", [])] if r.status_code == 200 else []
        return {"ok": r.status_code == 200, "upstream": UPSTREAM, "models": models, "log": str(LOG)}
    except Exception as e:
        return JSONResponse({"ok": False, "upstream": UPSTREAM, "error": str(e)}, status_code=503)


@app.get("/v1/models")
async def models(request: Request):
    r = await client.get("/v1/models", headers={"Authorization": request.headers.get("authorization", "")})
    return Response(r.content, status_code=r.status_code, media_type="application/json")


@app.post("/v1/chat/completions")
async def chat(request: Request):
    body = await request.json()
    if body.get("stream"):
        return JSONResponse({"error": "gateway: stream 미지원 (llm.py 는 비스트리밍)"}, status_code=400)
    wanted_logprobs = bool(body.get("logprobs"))
    body |= {"logprobs": True, "top_logprobs": max(TOP_LOGPROBS, int(body.get("top_logprobs") or 0))}

    t0 = time.time()
    r = await client.post("/v1/chat/completions", json=body,
                          headers={"Authorization": request.headers.get("authorization", "")})
    ms = int((time.time() - t0) * 1000)
    if r.status_code != 200:
        return Response(r.content, status_code=r.status_code, media_type="application/json")

    data = r.json()
    choice = data["choices"][0]
    raw = choice["message"].get("content") or ""
    tokens = ((choice.get("logprobs") or {}).get("content")) or []
    score = rescore(raw, tokens)
    if "confidence" in score:
        choice["message"]["content"] = rewrite_confidence(raw, score["confidence"])
    choice["zlas"] = score | {"model_confidence": _model_conf(raw), "upstream_ms": ms}
    if not wanted_logprobs:
        choice.pop("logprobs", None)

    user_text = next((c.get("text", "") for m in body.get("messages", []) if m.get("role") == "user"
                      for c in (m.get("content") if isinstance(m.get("content"), list) else [{"text": m.get("content")}])
                      if c.get("type", "text") == "text"), "")
    with LOG.open("a") as f:
        f.write(json.dumps({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "ms": ms, "model": body.get("model"),
            "has_image": any(c.get("type") == "image_url" for m in body.get("messages", [])
                             if isinstance(m.get("content"), list) for c in m["content"]),
            "goal_line": user_text.split("\n", 1)[0][:80], "raw": raw[:300],
            "out": choice["message"]["content"][:300], **{k: v for k, v in choice["zlas"].items()},
            "usage": data.get("usage"),
        }, ensure_ascii=False) + "\n")
    return JSONResponse(data)


def _model_conf(raw: str) -> float | None:
    m = CONF_RE.search(raw)
    try:
        return float(m.group(0).split(":")[1]) if m else None
    except ValueError:
        return None
