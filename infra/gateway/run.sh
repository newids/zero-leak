#!/usr/bin/env bash
# VLM 게이트웨이 설치·기동 (GPU 서버, vLLM 과 같은 호스트). app.py 와 같은 폴더에서 실행.
# 사용: bash run.sh [all|install|start|stop|status|logs N]
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"; VENV="$DIR/.venv"; LOGF="$DIR/gateway.log"; PIDF="$DIR/gateway.pid"
UV="$HOME/.local/bin/uv"
PORT="${GATEWAY_PORT:-8080}"
export UPSTREAM="${UPSTREAM:-http://127.0.0.1:8000}"
export VLLM_API_KEY="${VLLM_API_KEY:-zlas-team-token}"          # /health 가 upstream 확인에만 사용

install() {
  [[ -x "$UV" ]] || curl -LsSf https://astral.sh/uv/install.sh | sh
  [[ -d "$VENV" ]] || "$UV" venv --python 3.12 "$VENV"
  "$UV" pip install --python "$VENV/bin/python" -q fastapi uvicorn httpx
  "$VENV/bin/python" -c "import fastapi, uvicorn, httpx; print('gateway deps ok')"
}
running() { [[ -f "$PIDF" ]] && kill -0 "$(cat "$PIDF")" 2>/dev/null; }
start() {
  running && { echo "이미 실행 중 (pid $(cat "$PIDF"))"; return 0; }
  (cd "$DIR" && nohup "$VENV/bin/uvicorn" app:app --host 0.0.0.0 --port "$PORT" > "$LOGF" 2>&1 < /dev/null & echo $! > "$PIDF")
  sleep 2; echo "게이트웨이 pid $(cat "$PIDF") :$PORT → $UPSTREAM"
}
stop() { running && { kill "$(cat "$PIDF")"; rm -f "$PIDF"; echo stopped; } || echo "실행 중 아님"; }
status() { curl -s "http://localhost:$PORT/health"; echo; }
case "${1:-all}" in
  all) install; start; status ;; install) install ;; start) start ;; stop) stop ;; status) status ;;
  logs) tail -n "${2:-30}" "$LOGF" ;; *) echo "사용: $0 [all|install|start|stop|status|logs N]"; exit 1 ;;
esac
