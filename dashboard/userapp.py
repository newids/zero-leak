#!/usr/bin/env python3
"""
Zero-Leak 사용자 앱 (실제 서비스 화면과 같은 데모 프론트).  마케터 담당.
- userapp.html 한 장을 서빙하고, 같은 파일 계약(shared/*.json, shots/)을 JSON API로 노출한다.
- detect.py / agent.py 는 subprocess 로 실행. 함수 import 금지.
실행: cd dashboard && python userapp.py   → http://localhost:8502
"""
from __future__ import annotations
import json, os, pathlib, subprocess, sys, time
from flask import Flask, jsonify, request, send_file, send_from_directory

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHARED, SHOTS = ROOT / "shared", ROOT / "shots"
DETECT, AGENT = ROOT / "testbed" / "detect.py", ROOT / "agent" / "agent.py"
app = Flask(__name__)
PROC: dict = {"agent": None}


def load(p, default):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def running() -> bool:
    return PROC["agent"] is not None and PROC["agent"].poll() is None


@app.get("/")
def index():
    return send_file(pathlib.Path(__file__).parent / "userapp.html")


@app.get("/shots/<path:name>")
def shot(name):
    return send_from_directory(SHOTS, name, max_age=0)


@app.get("/api/state")
def state():
    st = load(SHARED / "state.json", {})
    risk = load(SHARED / "risk.json", [])
    latest = {}
    for p in sorted(SHOTS.glob("*_step_*.png")):
        site, step = p.stem.rsplit("_step_", 1)
        latest[site] = {"file": p.name, "step": int(step), "mtime": p.stat().st_mtime}
    steps = st.get("steps", [])
    pending = None
    if running() and steps and steps[-1]["status"] == "handoff" \
            and not (SHARED / "approve.flag").exists() and not (SHARED / "skip.flag").exists():
        pending = {"site": steps[-1]["site"], "reason": steps[-1]["action_json"].get("reason", "")}
    return jsonify({"risk": risk, "state": st, "shots": latest, "running": running(),
                    "pending": pending, "vault": [{"site": v["site"], "email": v["email"], "url": v.get("url", ""),
                                                   "dormant_days": v.get("dormant_days", 0)}
                                                  for v in load(SHARED / "vault.json", [])]})


@app.post("/api/detect")
def detect():
    r = subprocess.run([sys.executable, str(DETECT)], capture_output=True, text=True)
    return jsonify({"ok": r.returncode == 0, "log": r.stdout})


@app.post("/api/protect")
def protect():
    if running():
        return jsonify({"ok": False, "why": "already running"})
    (SHARED / "approve.flag").unlink(missing_ok=True)
    (SHARED / "skip.flag").unlink(missing_ok=True)
    for p in SHOTS.glob("*.png"):
        p.unlink()
    provider = request.json.get("provider", os.getenv("LLM_PROVIDER", "mock")) if request.is_json else "mock"
    env = dict(os.environ, STEP_PAUSE_MS=os.getenv("STEP_PAUSE_MS", "700"))
    PROC["agent"] = subprocess.Popen([sys.executable, str(AGENT), "--all", "--provider", provider],
                                     cwd=str(AGENT.parent), env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return jsonify({"ok": True})


@app.post("/api/approve")
def approve():
    (SHARED / "approve.flag").write_text(request.json.get("site", "") if request.is_json else "")
    return jsonify({"ok": True})


@app.post("/api/action")
def set_action():
    """사용자가 사이트별 조치(change|withdraw)를 바꾼다. risk.json 의 action 을 덮어쓰고 원래 권고는 action_auto 에 남긴다."""
    body = request.json if request.is_json else {}
    site, action = body.get("site"), body.get("action")
    if action not in ("change", "withdraw"):
        return jsonify({"ok": False, "why": "action must be change|withdraw"}), 400
    risk = load(SHARED / "risk.json", [])
    for r in risk:
        if r["site"] == site:
            r.setdefault("action_auto", r["action"])
            r["action"] = action
            r["action_by"] = "auto" if action == r["action_auto"] else "user"
    (SHARED / "risk.json").write_text(json.dumps(risk, ensure_ascii=False, indent=2))
    return jsonify({"ok": True, "risk": risk})


@app.post("/api/skip")
def skip():
    (SHARED / "skip.flag").write_text(request.json.get("site", "") if request.is_json else "")
    return jsonify({"ok": True})


@app.post("/api/reset")
def reset():
    if running():
        PROC["agent"].terminate()
    for p in [SHARED / "state.json", SHARED / "risk.json", SHARED / "approve.flag", SHARED / "skip.flag"]:
        p.unlink(missing_ok=True)
    for p in SHOTS.glob("*.png"):
        p.unlink()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(port=8502, debug=False, threaded=True)
