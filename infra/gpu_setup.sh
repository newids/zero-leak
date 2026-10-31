#!/usr/bin/env bash
# 네이버클라우드 GPU 서버(inno-gpu-017, NVIDIA L4 23GB)에 vLLM(OpenAI 호환) + Qwen2.5-VL 을
# Docker 없이 호스트 venv(uv) 로 띄운다. a100_setup.sh 는 Docker + A100 80GB 전제라 이 서버엔 맞지 않음.
# 사용 (서버에서):  bash gpu_setup.sh            # 설치(최초 1회) + 기동 + 준비 대기 + 확인
#                  bash gpu_setup.sh start|stop|check|logs [N]|wait|install
# L4 23GB 기준 기본값: 7B-AWQ(4비트, ~6GB) · gpu util 0.85 · 동시 4요청. 3초 넘으면 VLLM_MODEL 을 3B 로.
set -euo pipefail

MODEL="${VLLM_MODEL:-Qwen/Qwen2.5-VL-7B-Instruct-AWQ}"
PORT="${VLLM_PORT:-8000}"
API_KEY="${VLLM_API_KEY:-zlas-team-token}"        # 팀 내부 토큰. ACG 로 포트도 막을 것
GPU_UTIL="${VLLM_GPU_UTIL:-0.85}"
MAX_LEN="${VLLM_MAX_LEN:-8192}"
MAX_SEQS="${VLLM_MAX_SEQS:-4}"

DIR="$HOME/zlas-vllm"; VENV="$DIR/.venv"; LOG="$DIR/vllm.log"; PIDF="$DIR/vllm.pid"
UV="$HOME/.local/bin/uv"

install() {
  mkdir -p "$DIR"
  command -v nvidia-smi >/dev/null || { echo "nvidia-smi 없음: GPU 드라이버 확인"; exit 1; }
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
  # Triton 이 런타임에 C 확장을 컴파일하므로 Python 헤더와 gcc 가 필요 (없으면 Python.h 오류로 엔진 기동 실패)
  if [[ ! -f /usr/include/python3.12/Python.h ]] || ! command -v gcc >/dev/null; then
    echo "== python3.12-dev / build-essential 설치 (sudo)"
    sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3.12-dev build-essential
  fi
  [[ -x "$UV" ]] || { echo "== uv 설치"; curl -LsSf https://astral.sh/uv/install.sh | sh; }
  [[ -d "$VENV" ]] || { echo "== venv 생성"; "$UV" venv --python 3.12 "$VENV"; }
  if ! "$VENV/bin/python" -c "import vllm" 2>/dev/null; then
    echo "== vllm 설치 (torch 포함, 수 분)"; "$UV" pip install --python "$VENV/bin/python" vllm
  fi
  "$VENV/bin/python" -c "import vllm, torch; print('vllm', vllm.__version__, '| torch', torch.__version__, '| cuda', torch.cuda.is_available())"
}

running() { [[ -f "$PIDF" ]] && kill -0 "$(cat "$PIDF")" 2>/dev/null; }

start() {
  if running; then echo "이미 실행 중 (pid $(cat "$PIDF"))"; return 0; fi
  # FlashInfer 샘플러는 첫 실행 때 ninja+nvcc 로 커널을 JIT 컴파일하는데 이 서버엔 둘 다 없어 엔진이 죽는다.
  # 우리는 temperature=0(그리디)라 샘플러 구현이 결과에 영향 없음 → PyTorch 기본 샘플러로 고정.
  export VLLM_USE_FLASHINFER_SAMPLER=0
  nohup "$VENV/bin/vllm" serve "$MODEL" \
    --host 0.0.0.0 --port "$PORT" --api-key "$API_KEY" \
    --max-model-len "$MAX_LEN" --limit-mm-per-prompt '{"image":1}' \
    --gpu-memory-utilization "$GPU_UTIL" --max-num-seqs "$MAX_SEQS" \
    > "$LOG" 2>&1 < /dev/null &
  echo $! > "$PIDF"
  echo "기동 시작 pid $! · 모델 $MODEL (최초엔 다운로드 수 분). 로그: tail -f $LOG"
}

wait_ready() {
  for i in $(seq 1 120); do
    if curl -sf -H "Authorization: Bearer $API_KEY" "http://localhost:$PORT/v1/models" >/dev/null; then
      echo "vLLM 준비 완료 ($((i*10))s)"; return 0
    fi
    running || { echo "프로세스가 죽음. 로그 마지막 40줄:"; tail -40 "$LOG"; return 1; }
    sleep 10
  done
  echo "20분 내 기동 실패. tail -50 $LOG"; return 1
}

check() {
  echo "== /v1/models"
  curl -s -H "Authorization: Bearer $API_KEY" "http://localhost:$PORT/v1/models" | head -c 300; echo
  echo "== 샘플 추론 (텍스트만; 이미지 포함 측정은 노트북에서 infra/probe_vlm.py)"
  t0=$(date +%s%N)
  curl -s "http://localhost:$PORT/v1/chat/completions" \
    -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
    -d "{\"model\":\"$MODEL\",\"max_tokens\":40,\"temperature\":0,
         \"messages\":[{\"role\":\"user\",\"content\":\"다음 JSON 하나로만 답하라: {\\\"tool\\\":\\\"done\\\"}\"}]}" \
    | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["choices"][0]["message"]["content"])'
  echo "응답 $(( ($(date +%s%N) - t0) / 1000000 )) ms"
  echo "== GPU 메모리"; nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader
}

stop() { running && { kill "$(cat "$PIDF")"; rm -f "$PIDF"; echo "stopped"; } || echo "실행 중 아님"; }

case "${1:-all}" in
  all)     install; start; wait_ready; check ;;
  install) install ;;
  start)   start ;;
  stop)    stop ;;
  check)   check ;;
  wait)    wait_ready ;;
  logs)    tail -n "${2:-40}" "$LOG" ;;
  *) echo "사용: $0 [all|install|start|stop|check|wait|logs N]"; exit 1 ;;
esac
