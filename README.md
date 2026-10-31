# Z-LAS — Zero-Leak Action Shield

유출된 비밀번호를 탐지해 같은 패턴을 쓴 사이트를 찾고, 브라우저를 자율 조작해
비밀번호 변경·서비스 탈퇴를 대행하는 에이전트. 네이버클라우드 AI 해커톤 출품작.

핵심 설계는 **분리 실행(Split-Execution)**: 클라우드(A100 VLM / Claude)는 마스킹된 화면을 보고
"어디를 누를지"만 판단하고, 비밀번호 보관·입력은 사용자 기기의 로컬 에이전트가 한다.
비밀번호 평문은 외부로 나가지 않으며, 그 사실을 실행 때마다 측정해 `state.json` 에 기록한다.

```
leak.json ─► detect.py ─► risk.json ─► agent.py ─► state.json + shots/ ─► app.py / bench.py
                                           ▲ approve.flag ◄── app.py (사용자 승인)
```

## 실행 (3줄)

```bash
pip install -r requirements.txt && playwright install chromium
cd testbed && python app.py &                      # http://localhost:5001  (데모쇼핑·데모웹하드)
cd agent   && python agent.py --all --provider mock   # 키 없이 전체 흐름. 실제 데모는 vllm|claude
```

대시보드: `cd dashboard && streamlit run app.py` · 측정: `python bench.py`

## 폴더와 담당

| 폴더 | 담당 | 내용 |
| --- | --- | --- |
| `agent/` | 개발자 | `agent.py` 자율 조작 루프 · `llm.py` 모델 호출·가드레일·평문 감시 · `som.js` 번호 배지·마스킹 |
| `testbed/` | 기획자 | Flask 테스트베드 2종. 실제 사이트에는 접속하지 않는다 |
| `dashboard/` | 마케터 | Streamlit 3열 대시보드, 승인 버튼 |
| `shared/` | 계약 | `contract.md` 가 유일한 인터페이스. JSON 파일로만 통신 |
| `infra/` | 개발자 | `a100_setup.sh` — A100 에 vLLM(Qwen2.5-VL) 기동 |

## 모델 경로

| `LLM_PROVIDER` | 1차 판단 | 승격 | 가드레일 2차 |
| --- | --- | --- | --- |
| `mock` | 규칙 기반 (키 불필요) | — | 규칙 |
| `vllm` | A100 vLLM Qwen2.5-VL | 신뢰도 < 0.6 이면 Claude | 규칙 + Claude(키 있으면) |
| `claude` | Claude (이미지 입력) | — | 규칙 + Claude |
| `openai` | OpenAI (이미지 입력) | — | 규칙 + OpenAI |

키는 `.env` 에만 둔다 (`.env.example` 참고). 도구 함수는 `click(n)·fill(n,field)·handoff(reason)·done()` 네 개뿐이다.

## 평문 전송 0건 증명

- `som.js` 가 캡처 전에 `type=password` 입력란을 검은 사각형으로 덮는다 → 화면 PNG 에 비밀번호 없음.
- `llm.MONITOR` 가 외부 모델로 나가는 모든 텍스트에서 볼트 비밀번호 문자열을 검색한다.
- `agent.py` 가 브라우저의 테스트베드 외부 요청을 감시한다.
- 세 결과가 `shared/state.json` → `summary.plaintext_sent` 로 합산된다. 0 이 아니면 종료 코드 2.

## 마지막 실행 결과 (mock, 2026-10-31)

데모쇼핑 변경 9단계 · 데모웹하드 탈퇴 8단계(유인 팝업 2회 통과) · 10.9초 · 평문 전송 0건.
