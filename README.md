# Zero-Leak

유출된 비밀번호를 탐지해 같은 패턴을 쓴 사이트를 찾고, 브라우저를 자율 조작해
비밀번호 변경·서비스 탈퇴를 대행하는 에이전트. 코디세이 AI 해커톤 2026 출품작.

핵심 설계는 **분리 실행(Split-Execution)**: 클라우드(L4 VLM / Claude)는 마스킹된 화면을 보고
"어디를 누를지"만 판단하고, 비밀번호 보관·입력은 사용자 기기의 로컬 에이전트가 한다.
비밀번호 평문은 외부로 나가지 않으며, 그 사실을 실행 때마다 측정해 `state.json` 에 기록한다.

```
leak.json ─► detect.py ─► risk.json ─► agent.py ─► state.json + shots/ ─► userapp.py / app.py / bench.py
                                           ▲ approve.flag · skip.flag ◄── userapp.py (사용자 확정·건너뛰기)
```

## 환경 설정

- Python 3.11 이상 (3.11 · 3.12 · 3.13 확인), Git. GPU는 필요 없다(`mock` 모드는 키도 필요 없다).
- 저장소 루트에서 `.env` 를 만든다. 키는 `.env` 에만 둔다.

```bash
cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env
```

`.env` 의 주요 값 (전부 선택, 비워 두면 `mock` 으로 동작):

| 변수 | 기본값 | 뜻 |
| --- | --- | --- |
| `LLM_PROVIDER` | `mock` | `mock` \| `vllm` \| `claude` \| `openai` |
| `ANTHROPIC_API_KEY` · `OPENAI_API_KEY` | 빈 값 | `claude`/`openai` 경로와 승격에 사용 |
| `VLLM_BASE_URL` · `VLLM_MODEL` | 게이트웨이 주소 · `Qwen/Qwen2.5-VL-7B-Instruct-AWQ` | 네이버클라우드 L4 서버의 vLLM |
| `PROMOTE_BELOW` | `0.8` | 이보다 낮은 confidence 는 Claude 로 승격 |
| `CONFIRM_SUBMIT` | `0` (사용자 앱에서는 `1`) | `1` 이면 최종 제출 직전 확정 시트를 띄운다 |

## 실행

세 개의 터미널을 쓴다 (① 테스트베드 → ② 사용자 앱 → 브라우저에서 데모).

**macOS / Linux (bash)**

```bash
pip install -r requirements.txt && playwright install chromium
cd testbed   && python app.py        # ① http://localhost:5001  데모쇼핑·데모웹하드
cd dashboard && python userapp.py    # ② http://localhost:8502  사용자 앱 (영상·발표자료의 화면)
```

**Windows (PowerShell)** — 한국어 Windows 는 콘솔 인코딩 때문에 `PYTHONUTF8=1` 을 먼저 켠다.

```powershell
$env:PYTHONUTF8 = "1"
pip install -r requirements.txt
playwright install chromium
cd testbed;   python app.py          # ① 터미널 1
cd dashboard; python userapp.py      # ② 터미널 2 (새 창에서 $env:PYTHONUTF8 = "1" 다시 실행)
```

브라우저에서 `http://localhost:8502` 를 열면 "내 계정 보호 — 조치가 필요합니다" 알림으로 시작한다.
알림 → 위험 확인 → **지금 보호하기** → 에이전트가 두 사이트를 차례로 처리 → 완료 리포트.
사용자 앱은 `CONFIRM_SUBMIT=1` 로 에이전트를 띄우므로 사이트마다 제출 직전 확정 시트가 뜨고, 5초 뒤 자동 확정된다(건너뛰기·조치 변경 가능).

앱 없이 에이전트만 돌리기 (키 없이 전체 흐름):

```bash
cd agent && python agent.py --all --provider mock      # 실제 데모는 --provider vllm 또는 claude
```

관제 대시보드: `cd dashboard && streamlit run app.py` · 측정 표: `python bench.py` · 자세한 절차: `docs/데모 환경 실행 방법 안내.md`

사람 개입은 캡차·본인인증·2FA(모델이 handoff)와 서버가 제출을 거부했을 때(규칙 handoff)에만 필요하다. 최종 제출 직전 확정은
에이전트 단독 실행에서는 기본 꺼짐이며 `CONFIRM_SUBMIT=1`(또는 `--confirm-submit`)로 켠다. 사용자 앱은 이 값을 켜서 띄운다.
실제 사이트 테스트는 `--url … --allow-host … --channel chrome --user-data-dir … --approve-enter` (계정값은 `ZL_*` 환경변수, `docs/실환경 실행 설정 방법 안내.md`).

## 폴더와 담당

| 폴더 | 담당 | 내용 |
| --- | --- | --- |
| `agent/` | 개발자 | `agent.py` 자율 조작 루프 · `llm.py` 모델 호출·가드레일·평문 감시 · `som.js` 번호 배지·마스킹 |
| `testbed/` | 기획자 | Flask 테스트베드 2종(`app.py`) · `detect.py` 연쇄 위험 탐지. 실제 사이트에는 접속하지 않는다 |
| `dashboard/` | 마케터 | `userapp.py`+`userapp.html` 사용자 앱(폰 프레임) · `app.py` Streamlit 관제 · `bench.py` 측정 |
| `shared/` | 계약 | `contract.md` 가 유일한 인터페이스. JSON 파일로만 통신 |
| `infra/` | 개발자 | `gpu_setup.sh` — L4 GPU 서버에 vLLM(Qwen2.5-VL-7B-Instruct-AWQ) 기동 |
| `tools/` | — | 시연 영상 녹화·합성 스크립트 |
| `docs/` | — | 기획서, 실행 안내, 코드 분석 메모 |

## 모델 경로

| `LLM_PROVIDER` | 1차 판단 | 승격 | 가드레일 2차 |
| --- | --- | --- | --- |
| `mock` | 규칙 기반 (키 불필요) | — | 규칙 |
| `vllm` | L4 vLLM Qwen2.5-VL | confidence < 0.8 이면 Claude (`PROMOTE_BELOW`) | 규칙 + Claude(키 있으면) |
| `claude` | Claude (이미지 입력) | — | 규칙 + Claude |
| `openai` | OpenAI (이미지 입력) | — | 규칙 + OpenAI |

도구 함수는 `click(n)·fill(n,field)·handoff(reason)·done()` 네 개뿐이다.

## 평문 전송 0건 증명

- `som.js` 가 캡처 전에 `type=password` 입력란을 검은 사각형으로 덮는다 → 화면 PNG 에 비밀번호 없음.
- `llm.MONITOR` 가 외부 모델로 나가는 모든 텍스트에서 볼트 비밀번호 문자열을 검색한다.
- `agent.py` 가 브라우저의 테스트베드 외부 요청을 감시한다.
- 세 결과가 `shared/state.json` → `summary.plaintext_sent` 로 합산된다. 0 이 아니면 종료 코드 2.

## 마지막 실행 결과 (2026-10-31)

- 테스트베드, `vllm` + Claude 승격, 에이전트 단독 실행(`CONFIRM_SUBMIT=0`): 데모쇼핑 변경 9단계 · 데모웹하드 탈퇴 8단계(유인 팝업 2회 통과) · 37초 · 외부 전송 33건 전수 검사 · 평문 전송 0건 · 사람 개입 0회.
  시연 영상의 사용자 앱 데모는 `CONFIRM_SUBMIT=1` 이라 제출 직전 확정 시트가 사이트마다 1회(총 2회) 뜨고, 5초 뒤 자동 확정된다.
- 실제 사이트(리디북스, 본인 계정): 로그인 → 내 정보 관리 → 비밀번호 변경 12단계 · 63초 · 사람 개입은 이메일 인증 코드 1회 · 평문 전송 0건.
- `python bench.py` 가 같은 표를 만든다.
