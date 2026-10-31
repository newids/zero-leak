#!/usr/bin/env python3
"""
Z-LAS 관제 대시보드 (마케터 담당, Streamlit 1페이지).
3열: [왼쪽] 유출 탐지 → 도미노 위험 지도  [가운데] 에이전트가 보는 화면  [오른쪽] 승인·리포트
폴더 간 통신은 파일로만: risk.json / state.json / shots/*.png 읽기, approve.flag 쓰기.
detect.py 와 agent.py 는 subprocess 로 실행한다(함수 import 금지).

실행: cd dashboard && streamlit run app.py
"""
from __future__ import annotations
import json, pathlib, subprocess, sys, time

import streamlit as st

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHARED, SHOTS = ROOT / "shared", ROOT / "shots"
DETECT = ROOT / "testbed" / "detect.py"
AGENT = ROOT / "agent" / "agent.py"
PROVIDER = st.sidebar.selectbox("모델 경로", ["mock", "vllm", "claude", "openai"], index=0)

st.set_page_config(page_title="Z-LAS", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
 .block-container{padding-top:1.2rem}
 .risk-critical{background:#fde8e8;border-left:5px solid #d33;padding:8px 12px;border-radius:6px;margin:6px 0}
 .risk-high{background:#fff4e0;border-left:5px solid #e90;padding:8px 12px;border-radius:6px;margin:6px 0}
 .ok{background:#e6f7e6;border-left:5px solid #2a2;padding:8px 12px;border-radius:6px;margin:6px 0}
 .big{font-size:2rem;font-weight:700}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- helpers
def load_json(p: pathlib.Path, default):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def latest_shots(n=2) -> list[pathlib.Path]:
    """사이트별 가장 최근 단계 PNG, 최대 n개."""
    by_site: dict[str, pathlib.Path] = {}
    for p in sorted(SHOTS.glob("*_step_*.png")):
        by_site[p.name.rsplit("_step_", 1)[0]] = p
    return sorted(by_site.values(), key=lambda p: p.stat().st_mtime)[-n:]


def domino_dot(risk: list[dict]) -> str:
    color = {"critical": "#d33", "high": "#e90", "medium": "#cc3"}
    lines = ['digraph G { rankdir=LR; node [shape=box, style="rounded,filled", fontname="sans-serif"];',
             ' leak [label="유출 덤프\\n(텔레그램 시뮬)", fillcolor="#333", fontcolor="white"];']
    for i, r in enumerate(risk):
        lines.append(f' s{i} [label="{r["site"]}\\n{r["risk"]} · {r["action"]}", '
                     f'fillcolor="{color.get(r["risk"], "#ccc")}", fontcolor="white"];')
        src = "leak" if r["risk"] == "critical" else "s0"
        edge = "정확 일치" if r["risk"] == "critical" else "변형 패턴"
        lines.append(f' {src} -> s{i} [label="{edge}", color="{color.get(r["risk"], "#999")}"];')
    return "\n".join(lines) + "\n}"


def agent_running() -> bool:
    proc = st.session_state.get("agent_proc")
    return proc is not None and proc.poll() is None


# ---------------------------------------------------------------- header
st.markdown("## 🛡️ Z-LAS — 유출 탐지 · 자율 조치 · 승인")
left, mid, right = st.columns([1.1, 1.6, 1.1], gap="large")


# ---------------------------------------------------------------- 왼쪽: 탐지
with left:
    st.markdown("#### ① 유출 탐지")
    if st.button("🚨 유출 발생 (시뮬레이션)", use_container_width=True, type="primary"):
        r = subprocess.run([sys.executable, str(DETECT)], capture_output=True, text=True)
        st.session_state["detect_log"] = r.stdout + r.stderr
        st.session_state["detected_at"] = time.strftime("%H:%M:%S")
    risk = load_json(SHARED / "risk.json", [])
    if "detected_at" in st.session_state:
        st.caption(f"탐지 {st.session_state['detected_at']} · 해시 앞 5자리 k-익명성 대조")
    for r in risk:
        st.markdown(f'<div class="risk-{r["risk"]}"><b>{r["site"]}</b> · {r["risk"].upper()} → '
                    f'{"비밀번호 변경" if r["action"]=="change" else "서비스 탈퇴"}<br>'
                    f'<small>{r["reason"]}</small></div>', unsafe_allow_html=True)
    if risk:
        st.graphviz_chart(domino_dot(risk), use_container_width=True)
        if st.button("⚡ 원클릭 일괄 방어", use_container_width=True, disabled=agent_running()):
            (SHARED / "approve.flag").unlink(missing_ok=True)
            st.session_state["agent_proc"] = subprocess.Popen(
                [sys.executable, str(AGENT), "--all", "--provider", PROVIDER],
                cwd=str(AGENT.parent), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            st.session_state["started_at"] = time.time()
            st.rerun()
    else:
        st.info("유출 발생 버튼을 누르면 볼트와 대조합니다.")


# ---------------------------------------------------------------- 가운데: 에이전트 화면 (1초 갱신)
@st.fragment(run_every=1.0)
def live_screens():
    state = load_json(SHARED / "state.json", {})
    cur = state.get("current", {})
    if agent_running():
        st.markdown(f"**🤖 자율 조작 중** — {cur.get('site','')} · {cur.get('step','')}단계 · "
                    f"{'비밀번호 변경' if cur.get('action')=='change' else '탈퇴'}")
    elif cur:
        st.markdown(f"**조작 종료** — 마지막: {cur.get('site','')} · {cur.get('status','')}")
    shots = latest_shots(2)
    cols = st.columns(2)
    for c, p in zip(cols, shots):
        site, step = p.stem.rsplit("_step_", 1)
        c.image(str(p), caption=f"{site} · {int(step)}단계 (비밀번호 입력란은 가려진 채 전송)",
                use_container_width=True)
    steps = state.get("steps", [])[-5:]
    if steps:
        st.caption(" → ".join(f"{s['n']}:{s['action_json']['tool']}"
                              + (f"({s['action_json'].get('n')})" if s['action_json'].get('n') else "")
                              for s in steps))

with mid:
    st.markdown("#### ② 에이전트가 보는 화면")
    live_screens()


# ---------------------------------------------------------------- 오른쪽: 승인·리포트 (1초 갱신)
@st.fragment(run_every=1.0)
def approval_and_report():
    state = load_json(SHARED / "state.json", {})
    cur, summ = state.get("current", {}), state.get("summary", {})
    waiting = cur.get("status") == "running" and state.get("steps") and \
              state["steps"][-1]["status"] == "handoff" and agent_running()
    if waiting:
        reason = state["steps"][-1]["action_json"].get("reason", "")
        st.warning(f"**{cur.get('site')}** 에서 확인 요청\n\n{reason}")
        if st.button("✅ 변경 확정 (승인)", type="primary", use_container_width=True):
            (SHARED / "approve.flag").write_text(cur.get("site", ""))
            st.toast("승인 전달")
    else:
        st.markdown('<div class="ok">인증·최종 확인이 필요하면 여기에 승인 버튼이 뜹니다.</div>',
                    unsafe_allow_html=True)

    st.markdown("#### ③ 조치 리포트")
    c1, c2, c3 = st.columns(3)
    c1.metric("비밀번호 변경", summ.get("changed", 0))
    c2.metric("서비스 탈퇴", summ.get("withdrawn", 0))
    c3.metric("소요(초)", summ.get("elapsed_s", 0))
    pt = summ.get("plaintext_sent", 0)
    chk = summ.get("outbound_checked", 0)
    if state:
        if pt == 0:
            st.success(f"🔒 비밀번호 평문 전송 **0건** (외부 전송 {chk}건 검사)")
        else:
            st.error(f"평문 전송 {pt}건 — 즉시 중단")
    done = [s for s in state.get("steps", []) if s["status"] == "done"]
    for s in done:
        st.markdown(f"- **{s['site']}** 완료 · {s['n']}단계 · [{pathlib.Path(s['shot']).name}]")
    if not agent_running() and done:
        st.caption(f"모델 경로: {state.get('provider','')} · run {state.get('run_id','')}")

with right:
    approval_and_report()
