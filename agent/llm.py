#!/usr/bin/env python3
"""
LLM 호출 계층.
- provider: mock | vllm | claude | openai  (환경변수 LLM_PROVIDER, 인자로 덮어쓰기)
- 입력: 화면(마스킹 PNG) + 페이지 제목/헤딩 + SoM 요소 목록 + 목표
- 출력: 액션 하나. 도구 스키마는 click / fill / handoff / done 네 개만.
- 가드레일: 1차 액션을 2차 검증. 결제·송금·외부 URL·동의 범위 확대는 차단.
- 평문 감시: 외부 모델로 나가는 모든 텍스트에서 비밀번호 문자열을 검색해 건수를 기록.
  (화면 PNG는 som.js 가 캡처 전에 비밀번호 입력란을 가린다)

mock 공급자는 키 없이 전체 파이프라인을 돌리기 위한 규칙 기반 판단기.
실제 데모는 vllm(A100 1차) → claude(승격·검증) 로 전환.
"""
from __future__ import annotations
import base64, json, os, re, time
from dataclasses import dataclass, field as dc_field

TOOLS = ["click", "fill", "handoff", "done"]
FIELDS = ["email", "current_password", "new_password", "reason"]

# 가드레일: 액션이 가리키는 라벨에 이 단어가 있으면 차단
BLOCK_WORDS = ["결제", "송금", "구매", "충전", "pay", "구독", "포인트 사용",
               "외부", "http://", "https://", "동의하고 계속", "전체 동의", "유지하고"]

# 완료 판정 문구 (헤딩·상태 영역에서 찾음)
DONE_MARKERS = ["변경 완료", "탈퇴 완료", "처리되었습니다", "완료되었습니다"]


@dataclass
class Action:
    tool: str
    n: int | None = None
    field: str | None = None
    reason: str | None = None
    confidence: float = 1.0
    raw: dict = dc_field(default_factory=dict)

    def as_dict(self):
        d = {"tool": self.tool}
        if self.n is not None: d["n"] = self.n
        if self.field: d["field"] = self.field
        if self.reason: d["reason"] = self.reason
        return d


@dataclass
class Screen:
    """som.js 반환값."""
    path: str
    title: str
    headings: list[str]
    elements: list[dict]      # [{"n","label","kind","x","y"}]

    @classmethod
    def from_js(cls, d: dict) -> "Screen":
        return cls(d.get("path", ""), d.get("title", ""), d.get("headings", []),
                   d.get("elements", []))

    def is_done(self) -> bool:
        text = " ".join([self.title, *self.headings])
        return any(m in text for m in DONE_MARKERS)


# ---------------------------------------------------------------- 평문 감시
class OutboundMonitor:
    """외부 모델로 나가는 텍스트에 비밀번호가 섞이는지 감시한다."""
    def __init__(self):
        self.secrets: set[str] = set()
        self.checked = 0
        self.violations: list[str] = []

    def add_secrets(self, *values: str):
        self.secrets.update(v for v in values if v and len(v) >= 4)

    def scan(self, text: str, where: str):
        self.checked += 1
        for s in self.secrets:
            if s in text:
                self.violations.append(f"{where}: '{s[:2]}***' 포함")

MONITOR = OutboundMonitor()


def _b64(png_path: str) -> str:
    with open(png_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


# ---------------------------------------------------------------- mock
def _mock_decide(goal: str, scr: Screen, history: list[str]) -> Action:
    """규칙 기반. 실제 모델이 할 판단을 흉내낸다. history = ['<path>|<label>', ...]"""
    if scr.is_done():
        return Action("done", confidence=0.95)

    def seen(el): return f"{scr.path}|{el['label']}" in history
    els = [e for e in scr.elements if not seen(e)]
    inputs = [e for e in els if e["kind"] == "input" and "(입력됨)" not in e["label"]]   # 채운 칸은 제외
    buttons = [e for e in els if e["kind"] != "input"]

    # 1) 빈 입력란 먼저 채운다
    for el in inputs:
        lab = el["label"]
        if "인증번호" in lab or "SMS" in lab or "캡차" in lab.lower():
            return Action("handoff", reason="본인인증 필요", confidence=0.9)
        if "이메일" in lab or "아이디" in lab:
            return Action("fill", n=el["n"], field="email", confidence=0.85)
        if "비밀번호" in lab:
            fld = "new_password" if ("새" in lab or "신규" in lab or "new" in lab.lower()) \
                  else "current_password"
            return Action("fill", n=el["n"], field=fld, confidence=0.85)
        if "사유" in lab or "reason" in lab.lower():
            return Action("fill", n=el["n"], field="reason", confidence=0.85)

    # 2) 목표로 가는 버튼/링크
    if goal == "change":
        wants = ["비밀번호 변경", "변경하기", "회원정보", "정보 변경", "계정", "마이페이지", "보안", "로그인",
                 "저장", "확인", "제출"]
    else:
        wants = ["그래도 탈퇴", "포기하고 떠나기", "회원 탈퇴", "탈퇴", "계정 관리", "계정",
                 "설정", "확인", "제출"]
    for w in wants:
        for el in buttons:
            if w in el["label"]:
                return Action("click", n=el["n"], confidence=0.8)

    return Action("handoff", reason="다음 단계를 찾지 못함", confidence=0.3)


# ---------------------------------------------------------------- prompts
def _system_prompt() -> str:
    return (
        "너는 웹 화면에서 '비밀번호 변경' 또는 '회원 탈퇴'를 끝내는 자율 에이전트다. "
        "화면에는 클릭 가능한 요소마다 [번호] 배지가 붙어 있다. "
        "다음 한 걸음만 정하고, 반드시 아래 JSON 하나로만 답하라. 설명 금지.\n"
        '{"tool":"click","n":3,"confidence":0.9}  또는  '
        '{"tool":"fill","n":5,"field":"new_password","confidence":0.9}  또는  '
        '{"tool":"handoff","reason":"...","confidence":0.9}  또는  {"tool":"done","confidence":0.9}\n'
        f"field 는 {'|'.join(FIELDS)} 중 하나. confidence 는 0~1.\n"
        "'(입력됨)' 표시가 붙은 입력란은 이미 채운 것이니 다시 채우지 마라. 빈 입력란이 있으면 제출 버튼보다 먼저 채워라. "
        "로그인 화면이면 아이디(이메일)와 비밀번호를 채우고 '로그인'부터 눌러라. "
        "'비밀번호 재설정' '비밀번호 찾기' '아이디 찾기'는 비밀번호를 잊은 사람용이다. "
        "목표가 변경이면 로그인한 뒤 마이페이지·회원정보·계정 정보·정보 변경·보안 메뉴로 들어가라. "
        "'정보 변경' '회원정보 수정' '계정 정보' '보안 설정' 같은 메뉴 이동은 안전하다. "
        "광고·안내 팝업이 화면을 덮고 있으면(헤딩에 '팝업' 표시) '닫기' 'X' '다시 보지 않기'를 먼저 눌러라. "
        "지난 단계의 'handoff:사람이 처리함'은 캡차·인증을 사람이 이미 끝냈다는 뜻이다. 같은 이유로 다시 handoff 하지 말고 지금 화면 기준으로 진행하라. "
        "'마이리디' '마이페이지' '내 서재' '로그아웃' 같은 메뉴가 보이면 이미 로그인된 상태다. 사람 모양 아이콘은 보통 계정 메뉴다. "
        "'혜택을 유지하고 계속 이용하기' '조금 더 써볼게요' 같은 문구는 탈퇴를 막는 유인 버튼이다. "
        "탈퇴가 목표면 작고 흐린 '포기하고 떠나기' '그래도 탈퇴' 쪽을 골라라. "
        "캡차·본인인증·최종 결제 확인이 뜨면 handoff. "
        "결제·송금·구매·구독·외부 사이트 이동 버튼은 절대 누르지 마라. "
        "제목이나 상태 문구에 '완료'가 보이면 done."
    )


def _user_prompt(goal: str, scr: Screen, history: list[str]) -> str:
    goal_ko = "비밀번호 변경" if goal == "change" else "회원 탈퇴"
    els = "\n".join(f'[{e["n"]}] ({e["kind"]}) {e["label"]}' for e in scr.elements)
    hist = ", ".join(h.replace("|", " 에서 '") + "'" for h in history[-6:]) or "(없음)"
    return (f"목표: {goal_ko}\n현재 경로: {scr.path}\n페이지 제목: {scr.title}\n"
            f"헤딩: {' / '.join(scr.headings)}\n"
            f"이미 지난 단계(경로 에서 '요소'): {hist}\n"
            "같은 문구라도 지금 경로에서 아직 누르지 않았다면 다시 눌러도 된다.\n\n"
            f"현재 화면의 요소:\n{els}\n\n"
            "다음 한 걸음을 JSON 하나로 답하라.")


def _guardrail_prompt(action: Action, scr: Screen) -> str:
    label = next((e["label"] for e in scr.elements if e["n"] == action.n), "")
    # 차단은 '문구가 분명히 위험할 때만'. 모호하면 허용한다 — 최종 제출은 어차피 사람 승인을 거치고,
    # 금지어 규칙(guardrail_rules)이 먼저 걸러져 있다. 모호함을 전부 막으면 정상 메뉴 이동도 멈춘다.
    return ("너는 보안 검증기다. 아래 클릭의 대상 문구가 결제·송금·구매·충전·구독·외부 사이트 이동·"
            "마케팅 동의·탈퇴 철회(유지하기) 중 하나를 분명히 뜻할 때만 {\"allow\":false,\"why\":\"...\"} 로 답하라. "
            "'정보 변경' '회원정보 수정' '계정 정보' '보안 설정' '비밀번호 변경' '계정 관리' 같은 메뉴 이동과 "
            "'회원 탈퇴' '포기하고 떠나기' '그래도 탈퇴' 같은 탈퇴 진행은 허용한다. "
            "문구가 비어 있거나 모호하면 {\"allow\":true} 다. JSON 하나로만 답하라.\n"
            f"액션: {json.dumps(action.as_dict(), ensure_ascii=False)}\n"
            f"대상 요소 문구: {label}\n페이지 제목: {scr.title}")


def _parse(text: str) -> Action:
    m = re.search(r"\{.*?\}", text or "", re.S)
    if not m:
        return Action("handoff", reason="모델 응답 파싱 실패", confidence=0.0)
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return Action("handoff", reason="JSON 파싱 실패", confidence=0.0)
    tool = d.get("tool")
    if tool not in TOOLS:
        return Action("handoff", reason=f"알 수 없는 tool: {tool}", confidence=0.0)
    fld = d.get("field")
    if tool == "fill" and fld not in FIELDS:
        return Action("handoff", reason=f"알 수 없는 field: {fld}", confidence=0.0)
    return Action(tool, n=d.get("n"), field=fld, reason=d.get("reason"),
                  confidence=float(d.get("confidence", 0.8)), raw=d)


# ---------------------------------------------------------------- providers
def _openai_compatible(messages_text: str, system: str, img_path: str | None, *,
                       base_url: str, api_key: str, model: str, max_tokens=300) -> str:
    from openai import OpenAI
    MONITOR.scan(system + messages_text, f"{model}@{base_url}")
    client = OpenAI(base_url=base_url, api_key=api_key or "EMPTY")
    content = [{"type": "text", "text": messages_text}]
    if img_path and os.path.exists(img_path):
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{_b64(img_path)}"}})
    resp = client.chat.completions.create(
        model=model, temperature=0, max_tokens=max_tokens,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": content}])
    return resp.choices[0].message.content or ""


def _claude(messages_text: str, system: str, img_path: str | None, *,
            api_key: str, model: str, max_tokens=300) -> str:
    import anthropic
    MONITOR.scan(system + messages_text, f"claude:{model}")
    client = anthropic.Anthropic(api_key=api_key)
    blocks = [{"type": "text", "text": messages_text}]
    if img_path and os.path.exists(img_path):
        blocks.insert(0, {"type": "image", "source": {
            "type": "base64", "media_type": "image/png", "data": _b64(img_path)}})
    # temperature 는 보내지 않는다 — claude-opus-4-8 등 4.6+ 모델은 이 인자를 400 으로 거부한다
    msg = client.messages.create(model=model, max_tokens=max_tokens, system=system,
                                 messages=[{"role": "user", "content": blocks}])
    return "".join(b.text for b in msg.content if b.type == "text")


# ---------------------------------------------------------------- guardrail
def guardrail_rules(action: Action, scr: Screen) -> tuple[bool, str]:
    """규칙 기반 1차 차단. 통과=(True,'') / 차단=(False, 사유)."""
    if action.tool != "click" or action.n is None:
        return True, ""
    label = next((e["label"] for e in scr.elements if e["n"] == action.n), "")
    low = label.lower()
    for w in BLOCK_WORDS:
        if w.lower() in low:
            return False, f"가드레일 차단: '{label}' (금지어 '{w}')"
    return True, ""


# ---------------------------------------------------------------- public API
class LLM:
    PROMOTE_BELOW = float(os.getenv("PROMOTE_BELOW", "0.6"))   # 신뢰도가 이보다 낮으면 Claude 로 승격 (.env 로 조정)
    REPEAT_LIMIT = 2        # 같은 경로에서 같은 요소를 이 횟수 이상 다뤘는데 또 고르면 막힌 것으로 본다

    def __init__(self, provider: str | None = None):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "mock")).lower()
        self.last_ms = 0
        self.last_route = ""   # 어느 모델이 최종 판단했는지

    # -- 1차 판단
    def decide(self, goal: str, screen: dict | Screen, history: list[str],
               img_path: str | None = None) -> Action:
        scr = screen if isinstance(screen, Screen) else Screen.from_js(screen)
        t0 = time.time()
        p = self.provider
        if p == "mock":
            act, self.last_route = _mock_decide(goal, scr, history), "mock"
        elif p == "vllm":
            txt = _openai_compatible(
                _user_prompt(goal, scr, history), _system_prompt(), img_path,
                base_url=os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1"),
                api_key=os.getenv("VLLM_API_KEY", "EMPTY"),
                model=os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct"))
            act, self.last_route = _parse(txt), "vllm"
            if act.confidence < self.PROMOTE_BELOW and os.getenv("ANTHROPIC_API_KEY"):
                act, self.last_route = self._claude_decide(goal, scr, history, img_path), "vllm→claude"
        elif p == "openai":
            txt = _openai_compatible(
                _user_prompt(goal, scr, history), _system_prompt(), img_path,
                base_url="https://api.openai.com/v1",
                api_key=os.getenv("OPENAI_API_KEY", ""),
                model=os.getenv("OPENAI_MODEL", "gpt-4o"))
            act, self.last_route = _parse(txt), "openai"
        elif p == "claude":
            act, self.last_route = self._claude_decide(goal, scr, history, img_path), "claude"
        else:
            act, self.last_route = Action("handoff", reason=f"알 수 없는 provider: {p}"), "none"
        self.last_ms = int((time.time() - t0) * 1000)

        # -- 반복 감지: 확신하며 틀리는 경우(신뢰도 높음)는 승격으로 못 잡는다. 같은 동작이 반복되면 승격 또는 handoff.
        if act.tool in ("click", "fill") and act.n is not None:
            label = next((e["label"] for e in scr.elements if e["n"] == act.n), "")
            # 사람이 개입한(handoff 승인) 뒤로는 상황이 바뀌었으니 그 이후 기록만 센다
            cut = max((i for i, h in enumerate(history) if "|handoff:" in h), default=-1)
            recent = history[cut + 1:]
            if recent.count(f"{scr.path}|{label}") >= self.REPEAT_LIMIT:
                if p in ("vllm", "openai") and os.getenv("ANTHROPIC_API_KEY"):
                    act, self.last_route = self._claude_decide(goal, scr, history, img_path), f"{p}→claude(반복)"
                    label2 = next((e["label"] for e in scr.elements if e["n"] == act.n), "") if act.n is not None else ""
                    if act.tool in ("click", "fill") and recent.count(f"{scr.path}|{label2}") >= self.REPEAT_LIMIT:
                        act = Action("handoff", reason=f"'{label2}' 반복 — 승격 후에도 같은 선택", confidence=0.0)
                else:
                    act = Action("handoff", reason=f"'{label}' 을(를) {self.REPEAT_LIMIT}번 넘게 반복", confidence=0.0)

        # -- 2차 가드레일: 규칙 → (키가 있으면) 모델 검증
        ok, why = guardrail_rules(act, scr)
        if ok and act.tool == "click" and p != "mock":
            ok, why = self._guardrail_model(act, scr)
        if not ok:
            return Action("handoff", reason=why, confidence=0.0)
        return act

    def _claude_decide(self, goal, scr, history, img_path) -> Action:
        txt = _claude(_user_prompt(goal, scr, history), _system_prompt(), img_path,
                      api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                      model=os.getenv("CLAUDE_MODEL", "claude-opus-4-8"))
        return _parse(txt)

    def _guardrail_model(self, act: Action, scr: Screen) -> tuple[bool, str]:
        """2차 호출. 별도 시스템 프롬프트, 이미지 없음, 텍스트만."""
        prompt = _guardrail_prompt(act, scr)
        try:
            if os.getenv("ANTHROPIC_API_KEY"):
                txt = _claude(prompt, "보안 검증기. JSON 으로만 답한다.", None,
                              api_key=os.getenv("ANTHROPIC_API_KEY"),
                              model=os.getenv("CLAUDE_GUARD_MODEL",
                                              os.getenv("CLAUDE_MODEL", "claude-opus-4-8")),
                              max_tokens=120)
            elif self.provider in ("vllm", "openai"):
                base = (os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
                        if self.provider == "vllm" else "https://api.openai.com/v1")
                txt = _openai_compatible(prompt, "보안 검증기. JSON 으로만 답한다.", None,
                                         base_url=base,
                                         api_key=os.getenv("VLLM_API_KEY" if self.provider == "vllm"
                                                           else "OPENAI_API_KEY", "EMPTY"),
                                         model=os.getenv("VLLM_MODEL") if self.provider == "vllm"
                                               else os.getenv("OPENAI_MODEL", "gpt-4o"),
                                         max_tokens=120)
            else:
                return True, ""
            m = re.search(r"\{.*?\}", txt, re.S)
            d = json.loads(m.group(0)) if m else {"allow": True}
            return bool(d.get("allow", True)), d.get("why", "가드레일 모델 차단")
        except Exception as e:          # 검증기 장애 시에는 통과시키지 않고 사람에게 넘긴다 (fail-closed)
            return False, f"검증기 장애로 보류: {e}"


if __name__ == "__main__":
    llm = LLM("mock")
    MONITOR.add_secrets("Test1234!", "N9#mK2$pLq7!")
    login = Screen("/shop", "데모쇼핑 로그인", ["데모쇼핑 로그인"], [
        {"n": 1, "label": "이메일", "kind": "input"},
        {"n": 2, "label": "비밀번호", "kind": "input"},
        {"n": 3, "label": "로그인", "kind": "link"},
    ])
    h = []
    for _ in range(4):
        a = llm.decide("change", login, h)
        print("login:", a.as_dict())
        if a.tool == "fill" or a.tool == "click":
            lab = next(e["label"] for e in login.elements if e["n"] == a.n)
            h.append(f"/shop|{lab}")
        if a.tool == "click": break
    trap = Screen("/webhard/leave1", "잠깐만요!", ["잠깐만요!"], [
        {"n": 1, "label": "혜택을 유지하고 계속 이용하기", "kind": "link"},
        {"n": 2, "label": "포기하고 떠나기", "kind": "link"}])
    print("darkpattern:", llm.decide("withdraw", trap, []).as_dict())
    pay = Screen("/x", "결제", [], [{"n": 1, "label": "결제하기", "kind": "button"}])
    g = llm.decide("change", pay, [])
    print("guardrail:", g.as_dict())
    done = Screen("/shop/pw/done", "완료", ["완료", "비밀번호 변경 완료"], [])
    print("done:", llm.decide("change", done, []).as_dict())
    # 평문 감시 자가 테스트
    _user = _user_prompt("change", login, h)
    MONITOR.scan(_user, "selftest")
    print("outbound checked:", MONITOR.checked, "violations:", MONITOR.violations)
