#!/usr/bin/env bash
# 네이버클라우드 A100 80GB 서버에 vLLM(OpenAI 호환) + Qwen2.5-VL 을 Docker 로 띄운다.
# 사용: ssh 접속 후  bash infra/a100_setup.sh        (최초 1회, 모델 다운로드 ~15GB)
#       bash infra/a100_setup.sh check              (상태·응답시간 확인만)
# 30분 안에 안 뜨면 붙잡지 않는다 → LLM_PROVIDER=claude 로 전환 (구현계획 6절).
set -euo pipefail

MODEL="${VLLM_MODEL:-Qwen/Qwen2.5-VL-7B-Instruct}"
PORT="${VLLM_PORT:-8000}"
NAME=zlas-vllm
IMG="${VLLM_IMAGE:-vllm/vllm-openai:latest}"
CACHE="${HF_CACHE:-$HOME/.cache/huggingface}"
API_KEY="${VLLM_API_KEY:-zlas-team-token}"       # 팀 내부 토큰. ACG 로 포트도 막을 것

check() {
  echo "== /v1/models"
  curl -s -H "Authorization: Bearer $API_KEY" "http://localhost:$PORT/v1/models" | head -c 400; echo
  echo "== 샘플 추론 (텍스트만)"
  t0=$(date +%s%N)
  curl -s "http://localhost:$PORT/v1/chat/completions" \
    -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
    -d "{\"model\":\"$MODEL\",\"max_tokens\":40,\"temperature\":0,
         \"messages\":[{\"role\":\"user\",\"content\":\"다음 JSON 하나로만 답하라: {\\\"tool\\\":\\\"done\\\"}\"}]}" \
    | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["choices"][0]["message"]["content"])'
  echo "응답 $(( ($(date +%s%N) - t0) / 1000000 )) ms"
}

if [[ "${1:-}" == "check" ]]; then check; exit 0; fi

command -v nvidia-smi >/dev/null || { echo "nvidia-smi 없음: GPU 드라이버 확인"; exit 1; }
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
command -v docker >/dev/null || { echo "docker 없음: apt install docker.io 후 재실행"; exit 1; }

docker rm -f $NAME >/dev/null 2>&1 || true
mkdir -p "$CACHE"
docker run -d --name $NAME --gpus all --ipc=host --restart unless-stopped \
  -p "$PORT:8000" -v "$CACHE:/root/.cache/huggingface" \
  -e VLLM_API_KEY="$API_KEY" \
  "$IMG" \
  --model "$MODEL" \
  --max-model-len 8192 \
  --limit-mm-per-prompt image=1 \
  --gpu-memory-utilization 0.45 \
  --max-num-seqs 16 \
  --dtype bfloat16

echo "기동 중... (모델 다운로드 시 10~15분). 로그: docker logs -f $NAME"
for i in $(seq 1 90); do
  if curl -sf -H "Authorization: Bearer $API_KEY" "http://localhost:$PORT/v1/models" >/dev/null; then
    echo "vLLM 준비 완료 (${i}0s)"; check; exit 0
  fi
  sleep 10
done
echo "15분 내 기동 실패. docker logs $NAME 확인. 대안: LLM_PROVIDER=claude"
exit 1
