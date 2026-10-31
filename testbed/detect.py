#!/usr/bin/env python3
"""
유출 탐지 + 연쇄 위험(Domino Risk) 산출.  (기획자 담당, 순수 파이썬)

입력  shared/leak.json   유출 덤프 (비밀번호는 SHA-256 해시만)
      shared/vault.json  사용자 로컬 볼트 (어느 사이트에 어떤 비밀번호)
출력  shared/risk.json   사이트별 위험도·사유·조치 (contract.md 형식)

원리
1. k-익명성 대조: 볼트 비밀번호 해시의 앞 5자리만으로 유출 목록을 거른 뒤,
   거른 후보에 대해서만 전체 해시를 비교한다 (실서비스에서는 앞 5자리만 외부로 나감).
2. 연쇄 위험: 정확히 일치한 비밀번호에서 한국인의 변형 습관으로 후보를 만들고
   해시로 다른 사이트 볼트와 대조한다. 평문은 이 프로세스 밖으로 나가지 않는다.
   - 특수문자 교체  !  @  #  $  %
   - 끝자리 숫자/연도 교체 (2023~2026, 1~2자리 증감)
   - 한/영 키보드 전환 (qwer → ㅂㅈㄷㄱ)
   - 대소문자 첫 글자 토글
3. 조치: 정확 일치 → change. 변형 일치 → 휴면(dormant_days ≥ 365)이면 withdraw, 아니면 change.

실행: python detect.py            → shared/risk.json
      python detect.py --explain  → 대조 과정 출력
"""
from __future__ import annotations
import argparse, hashlib, itertools, json, pathlib, sys

SHARED = pathlib.Path(__file__).resolve().parent.parent / "shared"
PREFIX = 5                  # k-익명성: 외부로 보내는 해시 앞자리 수
DORMANT_DAYS = 365

KO_EN = str.maketrans("qwertyuiopasdfghjklzxcvbnmQWERTYUIOPASDFGHJKLZXCVBNM",
                      "ㅂㅈㄷㄱㅅㅛㅕㅑㅐㅔㅁㄴㅇㄹㅎㅗㅓㅏㅣㅋㅌㅊㅍㅠㅜㅡㅃㅉㄸㄲㅆㅛㅕㅑㅒㅖㅁㄴㅇㄹㅎㅗㅓㅏㅣㅋㅌㅊㅍㅠㅜㅡ")
SPECIALS = "!@#$%^&*"


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def variants(pw: str) -> dict[str, str]:
    """{변형 비밀번호: 규칙 이름}. 원본은 제외."""
    out: dict[str, str] = {}
    # 1) 특수문자 교체
    for i, ch in enumerate(pw):
        if ch in SPECIALS:
            for s in SPECIALS:
                if s != ch:
                    out[pw[:i] + s + pw[i + 1:]] = "특수문자 교체"
    # 2) 끝자리 숫자/연도
    stripped = pw.rstrip(SPECIALS)
    tail = pw[len(stripped):]
    digits = ""
    while stripped and stripped[-1].isdigit():
        digits = stripped[-1] + digits
        stripped = stripped[:-1]
    if digits:
        n = int(digits)
        for d in range(-2, 3):
            if d and 0 <= n + d:
                out[f"{stripped}{str(n + d).zfill(len(digits))}{tail}"] = "숫자 증감"
    for y in ("2023", "2024", "2025", "2026"):
        out[f"{stripped}{digits}{y}{tail}"] = "연도 접미사"
        out[f"{stripped}{y}{tail}"] = "연도 접미사"
    # 3) 한/영 전환
    ko = pw.translate(KO_EN)
    if ko != pw:
        out[ko] = "한/영 전환"
    # 4) 첫 글자 대소문자
    if pw[:1].isalpha():
        out[pw[0].swapcase() + pw[1:]] = "대소문자 토글"
    out.pop(pw, None)
    return out


def detect(leak: list[dict], vault: list[dict], explain=False) -> list[dict]:
    leak_by_prefix: dict[str, list[dict]] = {}
    for row in leak:
        leak_by_prefix.setdefault(row["password_sha256"][:PREFIX], []).append(row)

    risk: dict[str, dict] = {}         # site → entry
    exact: list[dict] = []

    # 1) k-익명성 대조 → 정확 일치
    for v in vault:
        h = sha(v["password"])
        cands = leak_by_prefix.get(h[:PREFIX], [])
        if explain:
            print(f"[k-anon] {v['site']}: 앞{PREFIX}자리 {h[:PREFIX]} → 후보 {len(cands)}건")
        for row in cands:
            if row["password_sha256"] == h and row["email"].lower() == v["email"].lower():
                risk[v["site"]] = {"site": v["site"], "url": v["url"], "email": v["email"],
                                   "risk": "critical",
                                   "reason": f"유출 비밀번호와 정확히 일치 ({row['source']})",
                                   "action": "change"}
                exact.append(v)

    # 2) 연쇄 위험: 정확 일치 비밀번호의 변형 ↔ 다른 사이트
    for src in exact:
        var = {sha(p): rule for p, rule in variants(src["password"]).items()}
        for v in vault:
            if v["site"] in risk:
                continue
            h = sha(v["password"])
            if h in var:
                dormant = v.get("dormant_days", 0) >= DORMANT_DAYS
                risk[v["site"]] = {"site": v["site"], "url": v["url"], "email": v["email"],
                                   "risk": "high",
                                   "reason": f"{src['site']} 유출 비밀번호의 변형 패턴 ({var[h]})"
                                             + (f" · {v['dormant_days']}일 미사용" if dormant else ""),
                                   "action": "withdraw" if dormant else "change"}
                if explain:
                    print(f"[domino] {src['site']} → {v['site']}: {var[h]}")

    order = {"critical": 0, "high": 1, "medium": 2}
    return sorted(risk.values(), key=lambda r: order[r["risk"]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--explain", action="store_true")
    args = ap.parse_args()
    leak = json.loads((SHARED / "leak.json").read_text())
    vault = json.loads((SHARED / "vault.json").read_text())
    result = detect(leak, vault, explain=args.explain)
    (SHARED / "risk.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"유출 {len(leak)}건 대조 → 위험 사이트 {len(result)}곳")
    for r in result:
        print(f"  {r['risk']:<8} {r['site']:<8} {r['action']:<8} {r['reason']}")
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
