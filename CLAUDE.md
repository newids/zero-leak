# Zero-Leak — 24시간 해커톤 프로젝트

## 무엇을 만드는가
유출된 비밀번호를 탐지해 같은 패턴을 쓴 사이트를 찾고, 브라우저를 자율 조작해
비밀번호 변경·서비스 탈퇴를 대행하는 에이전트. 데모는 테스트베드 2개 사이트에서만.

## 폴더 소유
- agent/     개발자. Playwright 에이전트, LLM 호출 계층
- testbed/   기획자. Flask 테스트베드 2종 (쇼핑몰, 웹하드)
- dashboard/ 마케터. Streamlit 대시보드
- shared/    계약 파일. 바꾸려면 세 사람 합의 후 개발자만 수정
- shots/     에이전트가 쓰는 화면 PNG. 커밋하지 않음

## 폴더 사이 통신은 파일로만
shared/contract.md 가 유일한 인터페이스. leak.json·vault.json → detect.py → risk.json,
agent.py → state.json + shots/, app.py → approve.flag. 함수 import 금지.

## 도구 함수 (llm.py 도구 스키마, 이 네 개만)
click(n) · fill(n, field) · handoff(reason) · done()

## 규칙
- 파이썬 3.11+, 의존성은 requirements.txt 에만 추가
- 외부 API 키·비밀번호·실제 계정 정보를 코드나 프롬프트에 쓰지 않는다. 가짜 값만 (Test1234!)
- 테스트베드 외 실제 사이트에 접속하는 코드를 만들지 않는다
- 파일을 만들면 반드시 실행해 보고, 실행 명령과 결과를 응답 끝에 적는다
- 다른 폴더의 파일은 읽기만 한다. 수정이 필요하면 소유자에게 요청 사항을 적는다
- 한 번의 요청에 파일 하나. 두 파일을 동시에 만들지 않는다

## 실행
- 테스트베드: cd testbed && python app.py            # http://localhost:5001
- 대시보드:   cd dashboard && streamlit run app.py
- 에이전트:   cd agent && python agent.py --site shop  (--provider mock|vllm|claude)
- 측정:       cd agent && python ../bench.py
