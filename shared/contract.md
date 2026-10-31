# Zero-Leak 계약 (contract)

폴더 사이는 **파일로만** 통신한다. 함수 import 금지. 이 문서가 유일한 인터페이스 정의다.
필드를 임의로 추가·변경하지 않는다. 바꿔야 하면 세 사람 합의 후 개발자가 이 파일을 먼저 고친다.

## 파일 흐름

```
leak.json ──► detect.py ──► risk.json ──► agent.py ──► state.json ──► app.py / bench.py
                                 └──────────────────────────────────► app.py
                            approve.flag  ◄── app.py (사용자 승인)
                            shots/step_N.png ◄── agent.py
```

## leak.json  (기획자가 작성 → detect.py 입력)

유출 시뮬레이션 데이터. 비밀번호는 평문이 아니라 SHA-256 전체 해시로 적는다.

```json
[
  {
    "email": "demo1@zlas.kr",
    "password_sha256": "<64 hex>",
    "source": "telegram-sim-2026-10"
  }
]
```

## vault.json  (사용자 로컬 자격증명 — 기획자가 데모용으로 작성 → detect.py 입력)

사용자가 어느 사이트에 어떤 비밀번호를 썼는지. 평문은 데모 편의를 위해서만 두고,
실제 서비스에서는 로컬 기기 볼트에만 존재한다. 데모 비밀번호는 전부 가짜.
`dormant_days`(선택): 마지막 사용 후 경과일. 365 이상이면 detect.py 가 변형 일치 사이트를 `withdraw` 로 판정한다.

```json
[
  { "site": "데모쇼핑", "url": "http://localhost:5001/shop", "email": "demo1@zlas.kr", "password": "Test1234!" },
  { "site": "데모웹하드", "url": "http://localhost:5001/webhard", "email": "demo1@zlas.kr", "password": "Test1234@", "dormant_days": 1100 }
]
```

## risk.json  (detect.py 출력 → app.py·agent.py 입력)

```json
[
  {
    "site": "데모쇼핑",
    "url": "http://localhost:5001/shop",
    "email": "demo1@zlas.kr",
    "risk": "critical",            // critical | high | medium
    "reason": "유출 비밀번호와 정확히 일치",
    "action": "change"             // change | withdraw
  }
]
```

## state.json  (agent.py 출력 → app.py·bench.py 입력)

에이전트가 매 단계 덮어쓴다. 배열이 아니라 현재 실행 1건의 스냅샷 + 단계 로그.

```json
{
  "run_id": "2026-10-31T13:50:00",
  "current": { "site": "데모쇼핑", "action": "change", "step": 4, "status": "running" },
  "steps": [
    { "n": 1, "site": "데모쇼핑", "action_json": {"tool":"click","n":3}, "status": "ok",
      "shot": "shots/데모쇼핑_step_01.png", "vlm_ms": 540, "route": "vllm", "ts": "..." }
  ],
  "summary": { "sites": 2, "changed": 1, "withdrawn": 1, "elapsed_s": 0, "plaintext_sent": 0, "outbound_checked": 0 },
  "leaks": []
}
```

## approve.flag  (app.py 생성 → agent.py가 존재 여부로 읽음)

사용자가 대시보드에서 승인 버튼을 누르면 생성된다. 내용은 승인한 site 이름 한 줄.
agent.py는 `handoff` 뒤 이 파일이 나타날 때까지 대기한다.

## shots/  (agent.py 작성 → app.py가 표시)

파일명: `shots/<site>_step_<NN>.png`. 비밀번호 입력란은 이미 검은 사각형으로 가려진 상태.

## 도구 함수 (llm.py 도구 스키마 — 이 네 개만)

| 함수 | 뜻 |
| --- | --- |
| `click(n)` | SoM 번호 n번 요소를 클릭 |
| `fill(n, field)` | n번 입력란에 field 종류의 값을 채움 (field: email \| current_password \| new_password \| reason) |
| `handoff(reason)` | 2FA·캡차·최종 승인 필요 — 사람에게 넘김 |
| `done()` | 목표 완료 |

가드레일: 결제·송금·외부 URL 이동·동의 범위 확대로 이어지는 액션은 2차 검증 호출이 차단한다.
