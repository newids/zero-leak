#!/usr/bin/env python3
"""측정 리포트 (기획자 담당). shared/state.json → Markdown 표. 실행: python bench.py [state.json]"""
import json, pathlib, statistics, sys

p = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "shared/state.json")
d = json.loads(p.read_text())
s, steps = d["summary"], d["steps"]
sites = {}
for st in steps:
    x = sites.setdefault(st["site"], {"steps": 0, "handoff": 0, "ms": [], "done": False, "route": set()})
    x["steps"] = max(x["steps"], st["n"]); x["ms"].append(st["vlm_ms"]); x["route"].add(st.get("route", ""))
    x["handoff"] += st["status"] == "handoff"; x["done"] |= st["status"] == "done"
ms = [st["vlm_ms"] for st in steps]
print(f"# Zero-Leak 측정 리포트 — {d['run_id']} · 모델 경로 {d.get('provider')}\n")
print("| 지표 | 값 |\n| --- | --- |")
print(f"| 처리 사이트 | {s['sites']} (변경 {s['changed']} · 탈퇴 {s['withdrawn']}) |")
print(f"| 전체 소요 | {s['elapsed_s']} 초 |")
print(f"| 판단 호출 | {len(steps)} 회 · 평균 {statistics.mean(ms):.0f} ms · 최대 {max(ms)} ms |")
print(f"| 외부 전송 검사 | {s.get('outbound_checked', 0)} 건 |")
print(f"| **비밀번호 평문 전송** | **{s['plaintext_sent']} 건** |\n")
print("| 사이트 | 단계 | 승인 요청 | 완료 | 경로 |\n| --- | --- | --- | --- | --- |")
for k, x in sites.items():
    print(f"| {k} | {x['steps']} | {x['handoff']} | {'✅' if x['done'] else '❌'} | {', '.join(sorted(r for r in x['route'] if r))} |")
sys.exit(0 if s["plaintext_sent"] == 0 and s["changed"] + s["withdrawn"] == s["sites"] else 1)
