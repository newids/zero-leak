# Z-LAS 코드 분석 메모 (기획자 관점, 중간 저장)

작성: 2026-10-31 · 기준 커밋: `aa6ed5a` (origin/main) · 상태: **초안 — 팀원 변경에 따라 바뀔 수 있음**

질문: "사이트마다 다른 '비밀번호 변경'을 우리 앱이 할 수 있게 하려면, 버튼 위치를 찾는 VLM을 네이버클라우드에 배포하는 것이 맞는가?"

결론: 절반은 맞고 절반은 방향을 바꿔야 한다.

## 1. 코드가 실제로 하는 일

```
agent.py 루프 (최대 12단계, MAX_STEPS)
 ├─ som.js      : 클릭 가능한 요소마다 [번호] 배지 + 중심 좌표(x,y), 라벨 텍스트 추출,
 │               type=password 입력란은 검은 사각형으로 마스킹
 ├─ 스크린샷     : 720×460 뷰포트 영역만 캡처 → shots/<site>_step_NN.png
 ├─ llm.decide : "요소 목록(텍스트) + 화면(PNG)" → {"tool":"click","n":3} JSON 하나
 │               provider: mock(키워드 규칙) | vllm(Qwen2.5-VL-7B, confidence<0.6 → Claude 승격)
 │                         | claude | openai
 ├─ 가드레일     : BLOCK_WORDS 규칙 → (ANTHROPIC_API_KEY 있으면) Claude 2차 검증(텍스트만)
 ├─ 승인        : CONFIRM_WORDS(변경하기·회원 탈퇴·저장·제출) 버튼이면 approve.flag 대기(30s)
 └─ 실행        : som.js가 준 좌표를 page.mouse.click(x,y), fill은 키보드 입력
```

핵심 사실: **버튼 위치는 VLM이 찾지 않는다.** `som.js`가 DOM `getBoundingClientRect`로 좌표를 이미 계산한다.
모델은 좌표를 출력하지 않고 번호만 고른다. 따라서 VLM의 역할은 visual grounding이 아니라
**"번호 붙은 후보 중 목표로 가는 것 고르기"**이고, 측정 대상도 좌표 정확도가 아니라 **선택 정확도**다.

## 2. 계획에서 맞는 부분

- A100 VLM 배포는 계획에 있고 `infra/a100_setup.sh`가 완성돼 있다. 새로 만들 것 없음.
- Notion ToDo의 8개 체크리스트가 그 절차 그대로다.

## 3. 방향을 바꿔야 하는 부분

1. **A100 배포는 개발자 몫.** `CLAUDE.md`: `infra/`는 개발자 소유. Notion ToDo: "개발자, 본선 T+0~T+1".
   기획자가 하려면 개발자와 먼저 합의.
2. **현재 테스트베드로는 VLM 필요성이 증명되지 않는다.** `mock`만으로 쇼핑몰 9단계·웹하드 8단계 전부 통과.
   라벨("비밀번호 변경", "회원정보 수정")이 키워드로 풀리기 때문. "mock 실패 / VLM 성공" 케이스가 있어야
   A100의 존재 이유가 생긴다.
3. **"사이트마다 다른 변경 흐름"을 만드는 곳은 `testbed/` (기획자 소유).** 지금 변경 흐름은 1개뿐.

## 4. 코드에서 발견한 약점 (테스트베드로 드러낼 수 있음)

| 약점 | 위치 | 영향 |
| --- | --- | --- |
| 스크롤 불가 | `som.js:32` `r.top > innerHeight` 제외, 도구에 `scroll` 없음, 뷰포트 720×460 | 변경 링크가 폴드 아래(푸터, 긴 설정 페이지)면 영원히 못 찾음 |
| 아이콘 버튼 라벨 없음 | `som.js:51` innerText 없으면 빈 라벨 | ⚙ 같은 버튼은 mock이 못 고름 → VLM이 이미지로 판단해야 하는 진짜 케이스 |
| div + JS 클릭 핸들러 | `som.js:9` 선택자 `a, button, input, select, textarea, [role=button], [onclick]` | addEventListener로 붙인 커스텀 버튼을 놓침 |
| 한국어 전용 규칙 | `_mock_decide` wants 목록, `BLOCK_WORDS` | 영문 UI(Account → Security → Change password)는 mock 실패, 가드레일 금지어도 영어 미포함(pay만) |
| 신뢰도 미보정 | `llm.py:233` `PROMOTE_BELOW = 0.6` | 7B 모델 자가 보고 confidence는 보정되지 않음 → 승격 빈도 예측 불가, 실측 필요 |

## 5. 제안하는 기획자 작업 순서 (미확정)

1. **테스트베드 변형 추가** (`testbed/app.py`) — 비밀번호 변경 경로 4~5종
   - 메뉴명 다름: "계정 설정 → 보안 → 비밀번호 재설정"
   - 현재 비밀번호 재인증 페이지가 중간에 끼어듦
   - 아이콘만 있는 설정 버튼(라벨 없음) ← mock 실패, VLM 필요
   - 긴 페이지, 변경 링크는 스크롤 아래 ← 현재 구조 한계 노출
   - 영문 UI
2. **측정표 확장** (`bench.py`) — provider(mock/vllm/claude) × 변형별 성공률·단계수·ms.
   슬라이드 7장 숫자이자 "A100이 1차 판단을 맡는 이유"의 근거.
3. 스크롤 문제는 개발자에게 **요청 사항으로** 전달. 도구 4개(click/fill/handoff/done)가 계약이라
   `scroll` 추가는 세 사람 합의 + `shared/contract.md` 수정 필요.
4. A100 배포는 개발자와 역할 확인 후. 직접 한다면 스크립트 그대로 실행.

## 6. 실행 전 알아둘 것 (개발자 영역)

- `.env` 자동 로딩 없음(`python-dotenv` 미사용). 실행 전 `set -a; source .env; set +a` 필요.
- 키 이름은 `ANTHROPIC_API_KEY`. `CLAUDE_API` 같은 다른 이름은 읽히지 않음.
- `anthropic==0.39.0`(2024년 버전)으로 `claude-opus-4-8` 호출이 되는지 미검증.
- vLLM 기동 옵션: `--max-model-len 8192 --limit-mm-per-prompt image=1 --gpu-memory-utilization 0.45 --max-num-seqs 16`.
  목표 응답 3초 이내, 초과 시 3B급 교체 또는 캡처 해상도 절반.

## 7. 한 줄 요약

"VLM을 배포해서 버튼을 찾게 한다"가 아니라
**"VLM이 풀어야 할 어려운 변경 흐름을 테스트베드에 만들고, 모델 경로별 성공률을 재서 A100의 필요성을 숫자로 증명한다"**가 기획자의 일.

---

# 추가: VLM 실측 1차 (2026-10-31 18:10, GPU 서버 `inno-gpu-017` L4 23GB)

서버: `infra/gpu_setup.sh` (Docker 없이 uv venv, vLLM 0.32.0, torch 2.13+cu130), 모델 `Qwen/Qwen2.5-VL-7B-Instruct-AWQ`,
`--gpu-memory-utilization 0.85 --max-num-seqs 4 --max-model-len 8192`, `VLLM_USE_FLASHINFER_SAMPLER=0`.
기동 후 GPU 사용 17.2GB / 23GB, KV 캐시 18만 토큰. 노트북 → `10.1.2.22:8000` VPN 경유 도달 확인.

기동 중 막힌 것 2개 (둘 다 스크립트에 반영): ① `Python.h` 없음 → `python3.12-dev build-essential` ② FlashInfer 샘플러 JIT 가 `ninja`/`nvcc` 요구 → 샘플러 비활성화.

## probe_vlm.py --all 결과

| 케이스 | Qwen 원문 | 지연(이미지 포함) | 기대 | 판정 |
| --- | --- | --- | --- | --- |
| shop_account (회원정보 메뉴) | `{"tool":"click","n":1,"confidence":0.9}` | 640ms (첫 호출 1.1s) | click 1 | ✅ |
| shop_pw (비밀번호 입력 화면) | `{"tool":"click","n":3,"confidence":0.9}` | 370ms | fill 1 current_password | ❌ 입력 안 채우고 '변경하기' 클릭 |
| webhard_trap (유인 팝업) | `{"tool":"click","n":2,"confidence":0.9}` | 370ms | click 2 | ✅ 다크패턴 통과 |

같은 shop_pw 를 Claude(opus-4-8)로: `{"tool":"fill","n":1,"field":"current_password","confidence":0.9}` 1.4s ✅

## 발견

1. **JSON 준수 3/3** — 사족 없이 JSON 하나만. `_parse` 실패 0건. 게이트웨이의 JSON 강제는 당장 불필요.
2. **지연 0.37~0.64s** — 목표 3s 대비 여유. L4 + AWQ 로 충분. 3B 교체 불필요.
3. **confidence 가 항상 0.9** — 프롬프트 예시의 `"confidence":0.9` 를 그대로 베낀 값. 자기 보고 신뢰도는 정보가 없고,
   따라서 `PROMOTE_BELOW=0.6` 승격은 **사실상 한 번도 발생하지 않는다.** 진짜 신뢰도가 필요하면 vLLM 의 `logprobs` 로
   선택 토큰 확률을 읽어 계산해야 함 (VLM 쪽 과제).
4. **shop_pw 실패는 '가짜 성공'으로 이어진다** — 테스트베드 `/shop/pw/done` 은 빈 폼도 받아 "변경 완료"를 띄우므로,
   실제 루프에서 Qwen 이 입력을 건너뛰고 제출해도 state.json 은 done 으로 기록된다. 측정이 거짓이 되는 경로.
   - 기획자(테스트베드): 비밀번호 입력란이 비면 완료 페이지로 가지 않게 검증 추가 → 가짜 성공 차단
   - 개발자(llm.py 프롬프트): "빈 입력란이 있으면 제출 버튼보다 먼저 채워라" 규칙 추가, som.js 가 입력란 채움 여부를 라벨에 표시
5. **Claude 경로 버그 (심각)** — `llm.py:212` `_claude()` 가 `temperature=0` 을 보내는데 `claude-opus-4-8` 은 400 거부.
   결과: `--provider claude` 불가, `vllm` 모드의 가드레일 2차 호출은 `llm.py:309` except 에서 "검증기 오류 무시"로 **조용히 통과**,
   승격도 실패. "모든 클릭은 Claude 2차 검증" 주장이 현재 코드에선 거짓. 수정: `temperature=0` 제거(한 줄).
   검토 제안: 검증기 장애 시 allow 가 아니라 handoff 로(fail-closed).
   `anthropic==0.39.0` + `claude-opus-4-8` 조합 자체는 temperature 만 빼면 동작 확인.
6. 의존성: `openai==1.54.0`/`anthropic==0.39.0` 이 `httpx>=0.28` 과 충돌(`proxies` 인자) → `requirements.txt` 에 `httpx==0.27.2` 추가.
7. 평문 감시: 외부 전송 11건 검사, 위반 0건.

## 개발자 요청 (agent/llm.py, 2026-10-31)

1. `_claude()` (llm.py:212) 의 `temperature=0` 삭제 — claude-opus-4-8 이 400 거부. 이것만 빼면 anthropic 0.39.0 조합 동작 확인.
2. `_guardrail_model()` except 절: 검증기 장애 시 allow 가 아니라 handoff (fail-open → fail-closed). 팀 판단 필요.
3. `_system_prompt()` 에 "fill 할 수 있는 빈 입력란(input)이 있으면 제출 버튼보다 먼저 채워라" 추가.
4. (선택) `som.js` 가 input 의 value 유무를 라벨에 표시.
확인: `python infra/probe_vlm.py --provider claude --all` 3/3, `--provider vllm --all` 에서 shop_pw 가 fill 로.
수정 후 `infra/probe_vlm.py` 의 `_claude_no_temperature` 임시 대체 블록은 기획자가 제거.

## 추가: 게이트웨이로 실제 confidence 계산 (2026-10-31 18:40)

`infra/gateway/app.py` (FastAPI, GPU 서버 :8080 → vLLM :8000). 요청에 `logprobs` 를 켜고, 응답 JSON 의 `confidence` 를
모델 자가 보고값(항상 0.9) 대신 **고른 토큰의 실제 확률** `min(p_tool, p_n)` 으로 바꿔 넣는다. OpenAI 호환 형식 그대로라
`llm.py` 무수정, `.env` 의 `VLLM_BASE_URL` 만 `:8080` 으로 전환. 요청마다 `~/zlas-gateway/requests.jsonl` 에 지연·원문·대안 후보 기록.

| 케이스 | 판정 | p_tool | p_n | **confidence** | n 후보 (확률) |
| --- | --- | --- | --- | --- | --- |
| shop_account | ✅ click 1 | 0.997 | 0.999 | **0.997** | 1 (0.999) · 2 (0.000) · 3 (0.000) |
| shop_pw | ❌ click 3 | **0.649** | 0.965 | **0.649** | 3 (0.965) · 2 (0.026) · 1 (0.004) |
| webhard_trap | ✅ click 2 | 0.989 | 0.994 | **0.989** | 2 (0.994) · 1 (0.003) · 3 (0.002) |

해석:
- 자가 보고 0.9 는 정보가 없었지만, 토큰 확률은 **틀린 답에서만 낮다** (0.65 vs 0.99). 승격 신호로 쓸 수 있다.
- shop_pw 의 불확실성은 `n` 이 아니라 **`tool`** 에 있다 — "click" 0.649, 나머지 약 0.35 가 "fill" 쪽. 모델이 "채울까 누를까"를 망설였고
  Claude 는 같은 화면에서 fill 을 골랐다. 즉 이 케이스는 승격이 정확히 필요한 자리다.
- 현재 `PROMOTE_BELOW = 0.6` 은 0.649 를 통과시킨다. 표본 3개뿐이라 단정은 이르지만 **0.8 근처**가 맞아 보인다.
  → 개발자 요청 추가: `PROMOTE_BELOW` 를 환경변수(`PROMOTE_BELOW`, 기본 0.6)로 빼서 측정값으로 조정 가능하게.
- 게이트웨이 경유 지연: 320~500ms (vLLM 직접 호출 대비 +수십 ms). 목표 3s 대비 여유.

남은 과제: 표본 확대 — 테스트베드 변형(아이콘 버튼, 영문 UI, 스크롤 아래, 재인증 페이지)을 추가해 20~30 케이스로
confidence 분포와 임계값을 정한다. 이게 "A100(L4) 1차 판단 + Claude 승격" 구조의 근거 숫자가 된다.
