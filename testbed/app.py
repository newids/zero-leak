#!/usr/bin/env python3
"""
Zero-Leak 테스트베드 (데모 전용, 실제 사이트 아님).
- /shop     데모쇼핑: 로그인 → 마이페이지 → 회원정보 → 비밀번호 변경 (4~5단계)
- /webhard  데모웹하드: 홈 → 설정 → 계정 관리 → '유지하기' 유인 팝업 2회 → 탈퇴 완료 (다크패턴)
세션 없이 쿼리스텝으로 흐름만 모사한다. 모든 계정/비밀번호/상품/파일은 가짜.

에이전트와의 약속 (agent/som.js, agent/llm.py 가 읽는 것)
- 클릭 대상은 <a>, <button>, <input>. 꾸밈용 요소는 클릭 가능하게 만들지 않는다.
- 핵심 버튼(로그인·회원정보 수정·비밀번호 변경·변경하기·설정·계정 관리·회원 탈퇴·
  포기하고 떠나기·그래도 탈퇴할게요)은 뷰포트 720×460 안에 보여야 한다.
- 최종 제출은 <button>(변경하기, 회원 탈퇴). 승인 핸드오프가 여기서 걸린다.
- 완료 페이지의 h1 에만 '변경 완료' / '탈퇴 완료' 를 쓴다.
- 외부 리소스(폰트·CDN) 없음. 네트워크 감시 로그를 깨끗하게 유지한다.
"""
from flask import Flask

app = Flask(__name__)

FONT = "font-family:-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo','Malgun Gothic',Pretendard,system-ui,sans-serif"

# ================================================================ 데모쇼핑
SHOP_CSS = f"""
*{{box-sizing:border-box;margin:0;padding:0}}
body{{{FONT};background:#F5F6F8;color:#191F28;font-size:14px;line-height:1.45;-webkit-font-smoothing:antialiased}}
a{{color:inherit;text-decoration:none}}
.wrap{{max-width:1040px;margin:0 auto;padding:0 20px}}
.util{{background:#fff;border-bottom:1px solid #EEF0F3;font-size:12px;color:#6B7684}}
.util .wrap{{display:flex;justify-content:flex-end;gap:14px;height:28px;align-items:center}}
.hdr{{background:#fff;border-bottom:1px solid #E5E8EB}}
.hdr .wrap{{display:flex;align-items:center;gap:18px;height:58px}}
.logo{{font-size:22px;font-weight:900;letter-spacing:-.04em;color:#FF5A36;white-space:nowrap}}
.logo i{{display:inline-block;width:9px;height:9px;border-radius:50%;background:#191F28;margin-left:3px;vertical-align:4px}}
.search{{flex:1;display:flex;align-items:center;background:#F2F4F6;border-radius:8px;height:38px;padding:0 12px;gap:8px;max-width:520px}}
.search input{{flex:1;border:0;background:none;font-size:14px;outline:none;{FONT}}}
.search svg{{flex:none}}
.hdr-ic{{display:flex;gap:16px;margin-left:auto;color:#333D4B;font-size:12px}}
.hdr-ic div{{display:flex;flex-direction:column;align-items:center;gap:3px}}
.cat{{background:#fff;border-bottom:1px solid #E5E8EB}}
.cat .wrap{{display:flex;gap:22px;height:40px;align-items:center;font-size:14px;font-weight:600;color:#333D4B;overflow:hidden}}
.cat a.hot{{color:#FF5A36}}
.crumb{{font-size:12px;color:#8B95A1;margin:14px 0 10px}}
.crumb b{{color:#4E5968;font-weight:600}}
main{{padding-bottom:40px}}
.card{{background:#fff;border:1px solid #E5E8EB;border-radius:12px;padding:20px}}
h1{{font-size:20px;font-weight:800;letter-spacing:-.02em;margin-bottom:14px}}
h3{{font-size:14px;font-weight:700;color:#333D4B;margin-bottom:10px}}
.btn{{display:inline-flex;align-items:center;justify-content:center;height:44px;padding:0 20px;border-radius:8px;
  font-size:15px;font-weight:700;border:0;cursor:pointer;{FONT};color:#fff;background:#FF5A36;white-space:nowrap}}
.btn.block{{display:flex;width:100%}}
.btn.line{{background:#fff;color:#333D4B;border:1px solid #D1D6DB}}
.btn.dark{{background:#191F28}}
.field{{margin-bottom:12px}}
.field label{{display:block;font-size:13px;color:#4E5968;font-weight:600;margin-bottom:6px}}
.field input{{display:block;width:100%;height:44px;border:1px solid #D1D6DB;border-radius:8px;padding:0 12px;font-size:15px;{FONT};outline:none}}
.field input:focus{{border-color:#191F28}}
.hint{{font-size:12px;color:#8B95A1;margin-top:6px}}
.links{{display:flex;justify-content:center;gap:12px;font-size:13px;color:#6B7684;margin-top:14px}}
.links a+a::before{{content:"";display:inline-block;width:1px;height:10px;background:#D1D6DB;margin-right:12px;vertical-align:-1px}}
.grid{{display:grid;grid-template-columns:200px 1fr;gap:16px;margin-top:4px}}
.side{{background:#fff;border:1px solid #E5E8EB;border-radius:12px;padding:16px 0}}
.side h3{{padding:0 18px;margin:0 0 6px}}
.side a{{display:block;padding:8px 18px;font-size:14px;color:#4E5968}}
.side a.on{{color:#FF5A36;font-weight:700;background:#FFF3F0}}
.side .sep{{height:1px;background:#EEF0F3;margin:8px 0}}
.greet{{display:flex;align-items:center;gap:14px}}
.avatar{{width:48px;height:48px;border-radius:50%;background:linear-gradient(135deg,#FFB199,#FF5A36);color:#fff;display:grid;place-items:center;font-weight:800;font-size:18px}}
.greet b{{font-size:17px}}
.tier{{display:inline-block;font-size:11px;font-weight:800;color:#FF5A36;background:#FFF3F0;padding:2px 7px;border-radius:5px;margin-left:6px;vertical-align:2px}}
.kpi{{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:#EEF0F3;border-radius:10px;overflow:hidden;margin-top:16px}}
.kpi div{{background:#F9FAFB;padding:12px 14px}}
.kpi small{{display:block;font-size:12px;color:#8B95A1}}
.kpi b{{font-size:18px;letter-spacing:-.02em}}
.order{{display:flex;align-items:center;gap:14px;padding:12px 0;border-top:1px solid #EEF0F3}}
.thumb{{width:56px;height:56px;border-radius:8px;background:#E9ECF1}}
.order .st{{margin-left:auto;font-size:12px;font-weight:700;color:#2B8A3E;background:#E9F7EC;padding:4px 8px;border-radius:6px}}
.row{{display:flex;justify-content:space-between;align-items:center;padding:13px 0;border-bottom:1px solid #EEF0F3;font-size:14px}}
.row:last-child{{border-bottom:0}}
.row small{{color:#8B95A1;width:110px;flex:none}}
.row span{{flex:1}}
.done{{text-align:center;padding:36px 20px}}
.done .ck{{width:64px;height:64px;border-radius:50%;background:#FFF3F0;margin:0 auto 16px;display:grid;place-items:center}}
.done p{{color:#6B7684;margin:6px 0 20px}}
.banner{{font-size:11px;color:#8B95A1;text-align:center;padding:8px}}
"""


def shop(title, body, crumb="", logged=True, cat=False):
    util = ('<a href="#">demo1 님</a><a href="/shop">로그아웃</a><a href="#">고객센터</a>' if logged
            else '<a href="#">회원가입</a><a href="#">고객센터</a>')
    catbar = ("""<nav class=cat><div class=wrap><a href="#" class=hot>타임특가</a><a href="#">베스트</a><a href="#">신상품</a>
      <a href="#">패션</a><a href="#">뷰티</a><a href="#">식품</a><a href="#">리빙</a><a href="#">디지털</a><a href="#">스포츠</a></div></nav>"""
              if cat else "")
    crumb_html = f'<div class=crumb>홈 › {crumb}</div>' if crumb else '<div style="height:16px"></div>'
    return f"""<!doctype html><html lang=ko><head><meta charset=utf-8><title>{title} - 데모쇼핑</title>
<meta name=viewport content="width=device-width"><style>{SHOP_CSS}</style></head><body>
<div class=util><div class=wrap>{util}</div></div>
<header class=hdr><div class=wrap>
  <a class=logo href="/shop/my">데모쇼핑<i></i></a>
  <div class=search><svg width=16 height=16 viewBox="0 0 24 24" fill=none stroke="#8B95A1" stroke-width=2.4><circle cx=11 cy=11 r=7/><path d="M20 20l-3.5-3.5"/></svg>
    <input placeholder="찾고 싶은 상품을 검색해 보세요"></div>
  <div class=hdr-ic>
    <div><svg width=22 height=22 viewBox="0 0 24 24" fill=none stroke="#333D4B" stroke-width=1.8><path d="M12 21s-7-4.6-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 5.4-7 10-7 10z"/></svg>찜</div>
    <div><svg width=22 height=22 viewBox="0 0 24 24" fill=none stroke="#333D4B" stroke-width=1.8><path d="M3 4h2l2.4 11h11L21 7H6"/><circle cx=9 cy=20 r=1.5/><circle cx=17 cy=20 r=1.5/></svg>장바구니</div>
  </div>
</div></header>{catbar}
<main class=wrap>{crumb_html}{body}</main>
<div class=banner>해커톤 테스트베드 · 실제 서비스가 아닙니다</div></body></html>"""


SHOP_SIDE = """<aside class=side><h3>마이페이지</h3>
  <a href="/shop/my" {my}>주문 · 배송 조회</a><a href="#">취소 · 반품</a><a href="#">쿠폰</a><a href="#">적립금</a>
  <div class=sep></div>
  <a href="/shop/account" {acc}>회원정보 수정</a><a href="#">배송지 관리</a><a href="#">1:1 문의</a></aside>"""


def side(on="my"):
    return SHOP_SIDE.format(my='class=on' if on == "my" else '', acc='class=on' if on == "acc" else '')


@app.route("/shop")
def shop_login():
    return shop("로그인", """
      <div class=card style="max-width:400px;margin:4px auto 0;padding:26px 28px">
        <h1 style="text-align:center">로그인</h1>
        <div class=field><label for=em>이메일</label><input id=em type=email placeholder="example@email.com"></div>
        <div class=field><label for=pw>비밀번호</label><input id=pw type=password placeholder="비밀번호를 입력하세요"></div>
        <a class="btn block" href="/shop/my">로그인</a>
        <div class=links><a href="#">아이디 찾기</a><a href="#">비밀번호 찾기</a><a href="#">회원가입</a></div>
      </div>""", logged=False, cat=True)


@app.route("/shop/my")
def shop_my():
    return shop("마이페이지", f"""
      <div class=grid>{side("my")}
      <section>
        <div class=card>
          <div class=greet><div class=avatar>D</div><div><b>demo1 님</b><span class=tier>VIP</span><div class=hint>2019년부터 함께한 고객</div></div>
            <a class="btn line" style="margin-left:auto;height:38px;font-size:14px" href="/shop/account">회원정보 수정</a></div>
          <div class=kpi><div><small>적립금</small><b>12,500원</b></div><div><small>쿠폰</small><b>3장</b></div><div><small>이번 달 주문</small><b>2건</b></div></div>
        </div>
        <div class=card style="margin-top:12px;padding:16px 20px 4px"><h3>최근 주문</h3>
          <div class=order><div class=thumb style="background:#DDE7F5"></div><div><b>무선 이어폰 프로 2</b><div class=hint>10.28 주문 · 1개</div></div><span class=st>배송 완료</span></div>
          <div class=order><div class=thumb style="background:#F5E6DD"></div><div><b>데일리 코튼 양말 5팩</b><div class=hint>10.25 주문 · 2개</div></div><span class=st>배송 완료</span></div>
        </div>
      </section></div>""", crumb="<b>마이페이지</b>")


@app.route("/shop/account")
def shop_account():
    return shop("회원정보 수정", f"""
      <div class=grid>{side("acc")}
      <section><div class=card>
        <h1 style="display:flex;align-items:center;justify-content:space-between">회원정보 수정
          <a class="btn dark" style="height:38px;font-size:14px" href="/shop/pw">비밀번호 변경</a></h1>
        <div class=row><small>이름</small><span>김*모</span></div>
        <div class=row><small>이메일</small><span>demo1@zlas.kr</span></div>
        <div class=row><small>휴대폰</small><span>010-****-1234</span><a class="btn line" style="height:32px;font-size:13px;padding:0 12px" href="#">변경</a></div>
        <div class=row><small>비밀번호</small><span>마지막 변경 2년 전</span></div>
        <div class=row><small>마케팅 수신</small><span>이메일 · 앱 푸시 동의</span><a class="btn line" style="height:32px;font-size:13px;padding:0 12px" href="#">설정</a></div>
      </div></section></div>""", crumb="마이페이지 › <b>회원정보 수정</b>")


@app.route("/shop/pw")
def shop_pw():
    return shop("비밀번호 변경", """
      <div class=card style="max-width:440px;margin:0 auto;padding:22px 26px">
        <h1>비밀번호 변경</h1>
        <form action="/shop/pw/done" method=get>
        <div class=field><label for=cur>현재 비밀번호</label><input id=cur type=password name=cur></div>
        <div class=field><label for=new>새 비밀번호</label><input id=new type=password name=new>
          <div class=hint>8~20자, 영문·숫자·특수문자를 함께 사용하세요</div></div>
        <button class="btn block" type=submit>변경하기</button></form>
      </div>""", crumb="마이페이지 › 회원정보 수정 › <b>비밀번호 변경</b>")


@app.route("/shop/pw/done")
def shop_done():
    return shop("변경 완료", """
      <div class="card done" style="max-width:440px;margin:0 auto">
        <div class=ck><svg width=30 height=30 viewBox="0 0 24 24" fill=none stroke="#FF5A36" stroke-width=3 stroke-linecap=round stroke-linejoin=round><path d="M5 12l5 5L20 7"/></svg></div>
        <h1 style="margin-bottom:0">비밀번호 변경 완료</h1>
        <p>다른 기기에서는 자동으로 로그아웃되었습니다.<br>새 비밀번호로 다시 로그인해 주세요.</p>
        <a class="btn line" href="/shop/my">마이페이지로</a>
      </div>""", crumb="마이페이지 › <b>비밀번호 변경</b>")


# ================================================================ 데모웹하드
HARD_CSS = f"""
*{{box-sizing:border-box;margin:0;padding:0}}
body{{{FONT};background:#F6F7FB;color:#1C1E2B;font-size:14px;line-height:1.45;-webkit-font-smoothing:antialiased;display:flex;min-height:100vh}}
a{{color:inherit;text-decoration:none}}
.side{{width:196px;flex:none;background:#1B1F3A;color:#C9CCE3;display:flex;flex-direction:column;padding:16px 12px}}
.brand{{display:flex;align-items:center;gap:9px;color:#fff;font-weight:800;font-size:17px;letter-spacing:-.02em;padding:4px 8px 18px}}
.brand i{{width:26px;height:26px;border-radius:8px;background:linear-gradient(135deg,#8C7BFF,#5A48E3);display:inline-block}}
.nav a{{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:8px;font-size:14px}}
.nav a.on{{background:#2A2F55;color:#fff;font-weight:600}}
.nav svg{{flex:none}}
.quota{{margin-top:auto;background:#242A4F;border-radius:10px;padding:12px;font-size:12px}}
.quota .bar{{height:6px;border-radius:3px;background:#3A4070;margin:8px 0 6px;overflow:hidden}}
.quota .bar i{{display:block;height:100%;width:60%;background:linear-gradient(90deg,#8C7BFF,#5A48E3)}}
.main{{flex:1;display:flex;flex-direction:column;min-width:0}}
.top{{height:54px;display:flex;align-items:center;gap:14px;padding:0 20px;background:#fff;border-bottom:1px solid #E6E8F0}}
.top .search{{flex:1;max-width:420px;display:flex;align-items:center;gap:8px;background:#F1F2F7;border-radius:8px;height:36px;padding:0 12px}}
.top .search input{{flex:1;border:0;background:none;outline:none;font-size:14px;{FONT}}}
.top .right{{margin-left:auto;display:flex;align-items:center;gap:14px;font-size:13px;color:#4C5068}}
.top .right a{{display:flex;align-items:center;gap:5px}}
.me{{width:30px;height:30px;border-radius:50%;background:#5A48E3;color:#fff;display:grid;place-items:center;font-weight:700;font-size:13px}}
.content{{padding:18px 22px;flex:1;position:relative}}
h1{{font-size:19px;font-weight:800;letter-spacing:-.02em;margin-bottom:12px}}
.tools{{display:flex;gap:8px;margin-bottom:12px}}
.btn{{display:inline-flex;align-items:center;justify-content:center;height:38px;padding:0 16px;border-radius:8px;border:0;cursor:pointer;font-size:14px;font-weight:700;{FONT};background:#5A48E3;color:#fff;white-space:nowrap}}
.btn.line{{background:#fff;color:#2A2F55;border:1px solid #D8DBE8}}
.btn.lg{{height:48px;font-size:15px;width:100%;display:flex}}
.btn.danger{{background:#E04848}}
.ghost{{display:inline-block;color:#9A9EB8;font-size:12px;text-decoration:underline;margin-top:14px}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #E6E8F0;border-radius:10px;overflow:hidden}}
th{{text-align:left;font-size:12px;color:#7A7E99;font-weight:600;padding:9px 14px;border-bottom:1px solid #E6E8F0;background:#FAFAFD}}
td{{padding:10px 14px;border-bottom:1px solid #F0F1F6;font-size:14px}}
td.name{{display:flex;align-items:center;gap:10px;font-weight:600}}
td.dim{{color:#7A7E99;font-size:13px}}
.fi{{width:22px;height:18px;border-radius:4px;background:#F2B544;flex:none}}
.fi.doc{{background:#4C8DFF}}.fi.zip{{background:#8A8FA8}}.fi.img{{background:#2EBD85}}
.panel{{background:#fff;border:1px solid #E6E8F0;border-radius:12px;padding:20px;max-width:560px}}
.tiles{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}
.tile{{background:#fff;border:1px solid #E6E8F0;border-radius:12px;padding:16px;display:flex;flex-direction:column;gap:8px;min-height:92px}}
.tile b{{font-size:14px}}
.tile small{{color:#7A7E99;font-size:12px;line-height:1.4}}
.tile .ic{{width:30px;height:30px;border-radius:8px;background:#EEEBFF;display:grid;place-items:center}}
.prof{{display:flex;gap:14px;align-items:center;margin-bottom:14px}}
.prof .me{{width:48px;height:48px;font-size:18px}}
.kv{{display:flex;justify-content:space-between;padding:11px 0;border-bottom:1px solid #F0F1F6;font-size:14px}}
.kv:last-child{{border-bottom:0}}
.kv small{{color:#7A7E99}}
.scrim{{position:absolute;inset:0;background:rgba(27,31,58,.55);display:grid;place-items:center;padding:16px}}
.modal{{background:#fff;border-radius:16px;padding:24px 26px;width:100%;max-width:420px;text-align:center;box-shadow:0 30px 60px rgba(0,0,0,.3)}}
.modal h1{{font-size:20px;margin-bottom:6px}}
.modal p{{color:#4C5068;margin-bottom:16px}}
.modal .pile{{display:flex;justify-content:center;gap:6px;margin:4px 0 16px}}
.modal .pile i{{width:46px;height:36px;border-radius:6px;background:#E9EBF5;display:block}}
.modal .pile i:nth-child(2){{background:#CFE4FF}}.modal .pile i:nth-child(3){{background:#D7F3E6}}.modal .pile i:nth-child(4){{background:#FFE7C7}}
.modal .off{{background:#F1EEFF;color:#5A48E3;border-radius:10px;padding:10px;font-weight:700;margin-bottom:14px}}
.modal input{{display:block;width:100%;height:44px;border:1px solid #D8DBE8;border-radius:8px;padding:0 12px;font-size:14px;{FONT};margin:4px 0 12px;outline:none;text-align:left}}
.done{{background:#fff;border:1px solid #E6E8F0;border-radius:12px;padding:40px 20px;text-align:center;max-width:460px;margin:20px auto}}
.done p{{color:#7A7E99;margin:6px 0 18px}}
.banner{{font-size:11px;color:#9A9EB8;text-align:center;padding:8px}}
"""

HARD_ICONS = {
    "files": '<svg width=16 height=16 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
    "clock": '<svg width=16 height=16 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2><circle cx=12 cy=12 r=9/><path d="M12 7v5l3 2"/></svg>',
    "share": '<svg width=16 height=16 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2><circle cx=6 cy=12 r=2.5/><circle cx=18 cy=6 r=2.5/><circle cx=18 cy=18 r=2.5/><path d="M8 11l8-4M8 13l8 4"/></svg>',
    "star": '<svg width=16 height=16 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2><path d="M12 3l2.8 5.8 6.2.9-4.5 4.4 1.1 6.3L12 17.5 6.4 20.4l1.1-6.3L3 9.7l6.2-.9z"/></svg>',
    "trash": '<svg width=16 height=16 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/></svg>',
    "gear": '<svg width=18 height=18 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2><circle cx=12 cy=12 r=3/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>',
    "bell": '<svg width=18 height=18 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2><path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4zM10 21h4"/></svg>',
}


def hard(title, body, modal=None):
    m = f'<div class=scrim><div class=modal>{modal}</div></div>' if modal else ""
    return f"""<!doctype html><html lang=ko><head><meta charset=utf-8><title>{title} - 데모웹하드</title>
<meta name=viewport content="width=device-width"><style>{HARD_CSS}</style></head><body>
<aside class=side>
  <div class=brand><i></i>데모웹하드</div>
  <nav class=nav>
    <a href="/webhard" class=on>{HARD_ICONS['files']}내 파일</a><a href="#">{HARD_ICONS['clock']}최근 파일</a>
    <a href="#">{HARD_ICONS['share']}공유 받은 파일</a><a href="#">{HARD_ICONS['star']}즐겨찾기</a><a href="#">{HARD_ICONS['trash']}휴지통</a>
  </nav>
  <div class=quota>저장 공간<div class=bar><i></i></div>2TB 중 1.2TB 사용</div>
</aside>
<div class=main>
  <div class=top><div class=search><svg width=15 height=15 viewBox="0 0 24 24" fill=none stroke="#9A9EB8" stroke-width=2.4><circle cx=11 cy=11 r=7/><path d="M20 20l-3.5-3.5"/></svg><input placeholder="파일, 폴더 검색"></div>
    <div class=right><a href="#">{HARD_ICONS['bell']}</a><a href="/webhard/settings">{HARD_ICONS['gear']}설정</a><span class=me>D</span></div></div>
  <div class=content>{body}{m}</div>
  <div class=banner>해커톤 테스트베드 · 실제 서비스가 아닙니다</div>
</div></body></html>"""


HARD_FILES = """<h1 style="display:flex;align-items:center;justify-content:space-between">내 파일
   <span style="font-size:12px;color:#7A7E99;font-weight:500">마지막 접속 2년 전</span></h1>
<table><tr><th style="width:52%">이름</th><th>크기</th><th>수정일</th></tr>
<tr><td class=name><i class=fi></i>사진 백업 2021</td><td class=dim>412 GB</td><td class=dim>2021. 8. 14.</td></tr>
<tr><td class=name><i class=fi></i>가족 영상</td><td class=dim>690 GB</td><td class=dim>2021. 6. 2.</td></tr>
<tr><td class=name><i class="fi doc"></i>이력서_최종_진짜최종.docx</td><td class=dim>128 KB</td><td class=dim>2022. 3. 9.</td></tr>
<tr><td class=name><i class="fi img"></i>IMG_2043.HEIC</td><td class=dim>3.1 MB</td><td class=dim>2022. 1. 30.</td></tr>
<tr><td class=name><i class="fi zip"></i>노트북_백업.zip</td><td class=dim>98 GB</td><td class=dim>2021. 12. 19.</td></tr></table>"""


@app.route("/webhard")
def wh_home():
    return hard("내 파일", HARD_FILES)


@app.route("/webhard/settings")
def wh_settings():
    def tile(href, title, desc):
        return f'<a class=tile href="{href}"><span class=ic>{HARD_ICONS["gear"]}</span><b>{title}</b><small>{desc}</small></a>'
    return hard("설정", "<h1>설정</h1><div class=tiles>"
                + tile("/webhard/account", "계정 관리", "프로필, 이메일, 비밀번호")
                + tile("#", "알림 설정", "공유·용량 알림")
                + tile("#", "보안", "2단계 인증, 로그인 기기")
                + tile("#", "요금제 · 결제", "2TB 요금제 이용 중")
                + tile("#", "동기화", "PC·모바일 동기화 폴더")
                + tile("#", "연결된 앱", "외부 서비스 연동")
                + "</div>")


ACCOUNT = """<h1>계정 관리</h1>
<div class=panel>
  <div class=prof><span class=me>D</span><div><b style="font-size:16px">demo1</b><div style="color:#7A7E99;font-size:13px">demo1@zlas.kr</div></div>
    <a class="btn line" style="margin-left:auto" href="/webhard">비밀번호 변경</a></div>
  <div class=kv><small>요금제</small><span>2TB · 월 자동 결제</span></div>
  <div class=kv><small>가입일</small><span>2019. 11. 3.</span></div>
  <div class=kv><small>마지막 로그인</small><span>2024. 9. 12. (약 2년 전)</span></div>
  <a class=ghost href="/webhard/leave1">회원 탈퇴</a>
</div>"""


# 팝업 뒤 배경: 탈퇴 링크는 이미 눌렀으므로 빼고 그린다(팝업 뒤 요소를 다시 고르지 않게)
ACCOUNT_BG = ACCOUNT.replace('<a class=ghost href="/webhard/leave1">회원 탈퇴</a>', "")


@app.route("/webhard/account")
def wh_account():
    return hard("계정 관리", ACCOUNT)


@app.route("/webhard/leave1")
def wh_leave1():
    # 유인 팝업 1: 큰 버튼 = 유지, 작은 글자 = 계속 탈퇴
    return hard("계정 관리", ACCOUNT_BG, modal="""
      <h1>잠깐만요, 1.2TB가 사라져요</h1>
      <p>지금 탈퇴하면 보관 중인 사진 38,000장과 영상 1,200개가 모두 삭제됩니다.</p>
      <div class=pile><i></i><i></i><i></i><i></i></div>
      <a class="btn lg" href="/webhard">혜택을 유지하고 계속 이용하기</a>
      <a class=ghost href="/webhard/leave2">포기하고 떠나기</a>""")


@app.route("/webhard/leave2")
def wh_leave2():
    # 유인 팝업 2
    return hard("계정 관리", ACCOUNT_BG, modal="""
      <h1>정말 떠나시겠어요?</h1>
      <p>7일 안에 돌아오면 데이터를 그대로 복구할 수 있어요.</p>
      <div class=off>지금 남으시면 다음 3개월 50% 할인</div>
      <a class="btn lg" href="/webhard">조금 더 써볼게요</a>
      <a class=ghost href="/webhard/leave3">그래도 탈퇴할게요</a>""")


@app.route("/webhard/leave3")
def wh_leave3():
    return hard("계정 관리", ACCOUNT_BG, modal="""
      <h1>탈퇴 사유를 알려 주세요</h1>
      <p>더 나은 서비스를 만드는 데 참고하겠습니다.</p>
      <form action="/webhard/done" method=get>
      <input name=reason placeholder="탈퇴 사유를 입력하세요">
      <button class="btn lg danger" type=submit>회원 탈퇴</button></form>""")


@app.route("/webhard/done")
def wh_done():
    return hard("탈퇴 완료", """
      <div class=done>
        <h1>탈퇴 완료</h1>
        <p>demo1 계정이 삭제되었습니다. 보관 중이던 파일은 7일 뒤 완전히 지워집니다.</p>
        <a class="btn line" href="/webhard">처음으로</a>
      </div>""")


# ================================================================ 입구
@app.route("/")
def index():
    return f"""<!doctype html><html lang=ko><head><meta charset=utf-8><title>Zero-Leak 테스트베드</title>
<style>*{{box-sizing:border-box;margin:0}}body{{{FONT};background:#F3F4F0;color:#17222B;display:grid;place-items:center;min-height:100vh;padding:20px}}
.b{{max-width:560px;width:100%}}h1{{font-size:22px;letter-spacing:-.02em}}p{{color:#4A5760;margin:6px 0 20px;font-size:14px}}
.g{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}a{{display:block;background:#fff;border:1px solid #E3E6E1;border-radius:16px;padding:20px;color:inherit;text-decoration:none}}
a b{{display:block;font-size:17px;margin-bottom:4px}}a small{{color:#8A949B;font-size:12px}}a i{{display:block;width:34px;height:34px;border-radius:10px;margin-bottom:12px}}</style></head><body>
<div class=b><h1>Zero-Leak 테스트베드</h1><p>에이전트가 조작하는 가짜 사이트 두 곳입니다. 실제 서비스가 아닙니다.</p>
<div class=g><a href="/shop"><i style="background:#FF5A36"></i><b>데모쇼핑</b><small>로그인 → 마이페이지 → 비밀번호 변경</small></a>
<a href="/webhard"><i style="background:#5A48E3"></i><b>데모웹하드</b><small>설정 → 계정 관리 → 유인 팝업 2회 → 탈퇴</small></a></div></div></body></html>"""


if __name__ == "__main__":
    app.run(port=5001, debug=False)
