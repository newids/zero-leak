#!/usr/bin/env python3
"""데모용 leak.json / vault.json 생성. 비밀번호는 전부 가짜(Test1234!/@)."""
import hashlib, json, pathlib

here = pathlib.Path(__file__).parent

vault = [
    {"site": "데모쇼핑",  "url": "http://localhost:5001/shop",
     "email": "demo1@zlas.kr", "password": "Test1234!"},
    {"site": "데모웹하드", "url": "http://localhost:5001/webhard",
     "email": "demo1@zlas.kr", "password": "Test1234@"},
]

def sha(p):  # 평문 → SHA-256 hex
    return hashlib.sha256(p.encode()).hexdigest()

# 유출: 쇼핑 비밀번호가 그대로 털렸다고 가정 (정확 일치 → critical)
leak = [
    {"email": "demo1@zlas.kr", "password_sha256": sha("Test1234!"),
     "source": "telegram-sim-2026-10"},
    # 무관한 노이즈 2건
    {"email": "someone@other.kr", "password_sha256": sha("hunter2hunter"),
     "source": "telegram-sim-2026-10"},
    {"email": "noise@x.kr", "password_sha256": sha("p@ssw0rd99"),
     "source": "paste-dump"},
]

(here / "vault.json").write_text(json.dumps(vault, ensure_ascii=False, indent=2))
(here / "leak.json").write_text(json.dumps(leak, ensure_ascii=False, indent=2))
# 예시 파일(형식 참고용)
(here / "risk.example.json").write_text(json.dumps([{
    "site": "데모쇼핑", "url": "http://localhost:5001/shop", "email": "demo1@zlas.kr",
    "risk": "critical", "reason": "유출 비밀번호와 정확히 일치", "action": "change"}],
    ensure_ascii=False, indent=2))
print("wrote vault.json, leak.json, risk.example.json")
