#!/usr/bin/env python3
"""
Zero-Leak 테스트베드 (데모 전용, 실제 사이트 아님).
- /shop     데모쇼핑(전자책 서점 스타일): 로그인 → 마이페이지 → 정보 변경 → 비밀번호 변경
- /webhard  데모웹하드: 홈 → 설정 → 계정 관리 → '유지하기' 유인 팝업 2회 → 탈퇴 완료 (다크패턴)
세션 없이 쿼리스텝으로 흐름만 모사한다. 모든 계정/비밀번호/상품/파일은 가짜.

에이전트와의 약속 (agent/som.js, agent/llm.py 가 읽는 것)
- 클릭 대상은 <a>, <button>, <input>. 꾸밈용 요소는 클릭 가능하게 만들지 않는다.
- 핵심 버튼(로그인·정보 변경·비밀번호 변경·설정·계정 관리·회원 탈퇴·
  포기하고 떠나기·그래도 탈퇴할게요)은 뷰포트 720×460 안에 보여야 한다.
- 최종 제출은 <button>(비밀번호 변경, 회원 탈퇴). 승인 핸드오프가 여기서 걸린다.
- 완료 페이지의 h1 에만 '변경 완료' / '탈퇴 완료' 를 쓴다.
- 외부 리소스(폰트·CDN) 없음. 네트워크 감시 로그를 깨끗하게 유지한다.
"""
from flask import Flask, redirect, request

app = Flask(__name__)

FONT = "font-family:-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo','Malgun Gothic',Pretendard,system-ui,sans-serif"

# ================================================================ 데모쇼핑 (전자책 서점 스타일)
SHOP_CSS = f"""
:root{{--blue:#1f8ce6;--blue-dark:#1577c9;--blue-light:#e8f3fd;--text:#212529;--text-2:#495057;--muted:#808991;
  --line:#e6e8eb;--bg-2:#f2f4f5;--star:#ffb400;--red:#e64938;--radius:4px}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{background:#fff;color:var(--text);{FONT};font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}}
a{{color:inherit;text-decoration:none}}
button{{{FONT};cursor:pointer}}
input{{{FONT}}}
.wrap{{max-width:1000px;margin:0 auto;padding:0 20px}}
.gnb{{border-bottom:1px solid var(--line);background:#fff}}
.gnb-top{{display:flex;align-items:center;height:56px;gap:20px}}
.logo{{display:flex;align-items:center;color:var(--blue);font-weight:900;font-size:24px;letter-spacing:-1.5px;white-space:nowrap}}
.logo span{{color:var(--text);font-size:11px;font-weight:700;margin-left:5px;letter-spacing:0;align-self:flex-end;margin-bottom:5px}}
.search{{flex:1;max-width:340px;display:flex;align-items:center;background:var(--bg-2);border-radius:var(--radius);height:34px;padding:0 12px;gap:8px;color:var(--muted)}}
.search input{{flex:1;border:0;background:transparent;font-size:14px;outline:none;color:var(--text)}}
.gnb-right{{margin-left:auto;display:flex;align-items:center;gap:8px}}
.gnb-right a,.gnb-right button{{display:inline-flex;align-items:center;gap:6px;height:32px;padding:0 12px;border-radius:var(--radius);font-size:13px;font-weight:600;border:1px solid var(--line);background:#fff;color:var(--text-2)}}
.gnb-right a.primary{{background:var(--blue);border-color:var(--blue);color:#fff}}
.gnb-right .icon-btn{{width:34px;padding:0;justify-content:center;border:0;background:transparent;font-size:16px}}
.gnb-nav{{display:flex;align-items:flex-end;height:40px;gap:26px}}
.gnb-nav a{{font-size:15px;font-weight:700;color:var(--text-2);padding-bottom:10px;border-bottom:3px solid transparent;display:flex;align-items:center;gap:6px}}
.gnb-nav a.on{{color:var(--text);border-color:var(--text)}}
.gnb-nav a .new{{width:6px;height:6px;border-radius:50%;background:var(--red);margin-top:-10px}}
.snb{{border-bottom:1px solid var(--line)}}
.snb .wrap{{display:flex;gap:4px;height:40px;align-items:center;overflow:hidden}}
.snb a{{display:inline-block;padding:5px 12px;border-radius:999px;font-size:13.5px;font-weight:600;color:var(--text-2);white-space:nowrap}}
.snb a.on{{background:var(--text);color:#fff}}
.page-title{{font-size:20px;font-weight:800;margin:16px 0 12px}}
.my{{display:grid;grid-template-columns:210px 1fr;gap:20px;align-items:start;margin-bottom:40px}}
.side{{border:1px solid var(--line);border-radius:8px;overflow:hidden}}
.side .me{{padding:14px 16px;border-bottom:1px solid var(--line);display:flex;gap:10px;align-items:center}}
.avatar{{width:38px;height:38px;border-radius:50%;background:var(--blue);color:#fff;display:grid;place-items:center;font-weight:800;font-size:15px;flex:none}}
.side .me b{{display:block;font-size:14px}}
.side .me span{{font-size:11.5px;color:var(--muted)}}
.side .grp{{padding:6px 0;border-bottom:1px solid var(--line)}}
.side .grp:last-child{{border:0}}
.side .grp h4{{font-size:11px;color:var(--muted);padding:6px 16px 2px;font-weight:700}}
.side a{{display:flex;justify-content:space-between;align-items:center;padding:7px 16px;font-size:13.5px;color:var(--text-2);font-weight:600}}
.side a.on{{color:var(--blue);background:var(--blue-light)}}
.side a .cnt{{font-size:12px;color:var(--muted);font-weight:700}}
.panel{{border:1px solid var(--line);border-radius:8px;padding:18px 20px;margin-bottom:14px}}
.panel h3{{font-size:15.5px;font-weight:800;margin-bottom:12px;display:flex;align-items:center;justify-content:space-between}}
.panel h3 small{{font-size:12px;color:var(--muted);font-weight:600}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}
.stat{{background:var(--bg-2);border-radius:8px;padding:12px 14px}}
.stat span{{font-size:11.5px;color:var(--muted);font-weight:700;display:block}}
.stat b{{font-size:18px;display:block;margin-top:4px;letter-spacing:-.3px}}
.stat b small{{font-size:11px;color:var(--muted);margin-left:2px;font-weight:700}}
.info-list{{list-style:none;border-top:1px solid var(--line)}}
.info-list li{{display:grid;grid-template-columns:120px 1fr auto;align-items:center;gap:14px;padding:12px 4px;border-bottom:1px solid var(--line);font-size:14px}}
.info-list li .k{{color:var(--muted);font-weight:700;font-size:13px}}
.info-list li .v{{font-weight:600}}
.info-list li .v .badge{{font-size:11px;background:var(--blue-light);color:var(--blue);padding:2px 7px;border-radius:4px;margin-left:6px;font-weight:800}}
.act{{font-size:13px;color:var(--text-2);border:1px solid #d1d5d9;background:#fff;height:30px;padding:0 12px;border-radius:var(--radius);font-weight:700;display:inline-flex;align-items:center;white-space:nowrap}}
.act.blue{{color:var(--blue);border-color:var(--blue)}}
.shelf{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}}
.cover{{aspect-ratio:7/10;border-radius:4px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.18),0 0 0 1px rgba(0,0,0,.06) inset}}
.cover svg{{width:100%;height:100%;display:block}}
.book .t{{margin-top:7px;font-size:12.5px;font-weight:700;line-height:1.3}}
.prog{{height:4px;background:var(--line);border-radius:2px;margin-top:6px;overflow:hidden}}
.prog i{{display:block;height:100%;background:var(--blue)}}
.auth{{display:flex;flex-direction:column;align-items:center;padding:30px 20px 40px}}
.auth .logo{{font-size:34px;margin-bottom:22px}}
.card{{width:100%;max-width:400px}}
.field{{margin-bottom:10px}}
.field label{{display:block;font-size:12px;color:var(--text-2);font-weight:700;margin-bottom:5px}}
.field input{{width:100%;height:44px;border:1px solid #d1d5d9;border-radius:var(--radius);padding:0 14px;font-size:15px;outline:none;background:#fff;color:var(--text)}}
.field input:focus{{border-color:var(--blue);box-shadow:0 0 0 2px var(--blue-light)}}
.field .hint{{font-size:12px;color:var(--muted);margin-top:5px}}
.pw-wrap{{position:relative}}
.pw-wrap input{{padding-right:48px}}
.pw-wrap .eye{{position:absolute;right:10px;top:50%;transform:translateY(-50%);border:0;background:transparent;color:var(--muted);font-size:12px;font-weight:700;padding:6px}}
.check{{display:flex;align-items:center;gap:8px;font-size:14px;color:var(--text-2);margin:8px 0 12px}}
.check .cb{{width:17px;height:17px;border-radius:3px;background:var(--blue);color:#fff;font-size:11px;font-weight:900;display:grid;place-items:center}}
.btn{{display:inline-flex;align-items:center;justify-content:center;width:100%;height:46px;border-radius:var(--radius);font-size:15px;font-weight:800;border:1px solid transparent}}
.btn.blue{{background:var(--blue);color:#fff}}
.btn.ghost{{background:#fff;border-color:#d1d5d9;color:var(--text-2)}}
.btn.sm{{height:38px;font-size:14px;width:auto;padding:0 18px}}
.auth-links{{display:flex;justify-content:center;margin-top:16px;font-size:13px;color:var(--text-2)}}
.auth-links a{{padding:0 12px;border-right:1px solid var(--line)}}
.auth-links a:last-child{{border:0}}
.form{{max-width:420px}}
.form-actions{{display:flex;gap:10px;margin-top:14px}}
.success{{text-align:center;padding:16px 0 10px}}
.success .ic{{width:60px;height:60px;border-radius:50%;background:#e8f7ec;color:#2ea043;display:grid;place-items:center;font-size:28px;margin:0 auto 14px}}
.success h1{{font-size:18px;font-weight:800}}
.success p{{color:var(--muted);margin:8px 0 16px;font-size:13px}}
.banner{{font-size:11px;color:var(--muted);text-align:center;padding:10px;background:var(--bg-2);margin-top:10px}}
"""

COVERS = [("#8e2a2a", "#d9775c", "달빛 아래 서점", "정수민"), ("#1b2440", "#4a5f9e", "느리게 걷는 법", "박도윤"),
          ("#2f3a1e", "#7f9a4c", "회계 첫걸음", "이서진"), ("#3b1f5e", "#9b59d6", "밤의 정원사", "김하늘"),
          ("#0f4c5c", "#3fa7b8", "작은 습관의 힘", "최민호")]


def cover(i, c1, c2, title, author):
    return (f'<svg viewBox="0 0 140 200" role=img><defs><linearGradient id=g{i} x1=0 y1=0 x2=1 y2=1>'
            f'<stop offset=0 stop-color="{c1}"/><stop offset=1 stop-color="{c2}"/></linearGradient></defs>'
            f'<rect width=140 height=200 fill="url(#g{i})"/><rect width=8 height=200 fill="rgba(0,0,0,.25)"/>'
            f'<circle cx=110 cy=150 r=34 fill="rgba(255,255,255,.08)"/>'
            f'<text x=14 y=60 font-size=14 font-weight=800 fill="#fff" font-family="Apple SD Gothic Neo,Pretendard,Malgun Gothic,sans-serif">{title}</text>'
            f'<text x=14 y=182 font-size=9 fill="rgba(255,255,255,.75)" font-family="Apple SD Gothic Neo,Pretendard,Malgun Gothic,sans-serif">{author}</text></svg>')


def shop(title, body, logged=True, page=""):
    right = ('<button class=icon-btn type=button aria-label="알림">🔔</button><button class=icon-btn type=button aria-label="장바구니">🛒</button>'
             '<a href="/shop/my" class=primary>마이페이지</a>' if logged else '<a href="#">회원가입</a>')
    nav = "".join(f'<a href="#"{" class=on" if n == "도서" else ""}>{n}{"<i class=new></i>" if n == "데모샵" else ""}</a>'
                  for n in ["만화", "웹툰", "웹소설", "도서", "데모샵"])
    return f"""<!doctype html><html lang=ko><head><meta charset=utf-8><title>{title} - 데모쇼핑</title>
<meta name=viewport content="width=device-width"><style>{SHOP_CSS}</style></head><body>
<header class=gnb><div class="wrap gnb-top">
  <a class=logo href="/shop/my">DEMO<span>SHOP</span></a>
  <div class=search role=search>🔍<input type=search placeholder="제목, 출판사, 작가를 검색하세요"></div>
  <div class=gnb-right>{right}</div></div>
  <nav class="wrap gnb-nav">{nav}</nav></header>
<main class=wrap>{body}</main>
<div class=banner>해커톤 테스트베드 · 실제 서비스가 아닙니다 (데모쇼핑은 가상의 전자책 서점입니다)</div></body></html>"""


def side(on):
    def a(label, href, key, cnt=""):
        return f'<a href="{href}"{" class=on" if key == on else ""}>{label}{f"<span class=cnt>{cnt}</span>" if cnt else ""}</a>'
    return ('<aside class=side><div class=me><span class=avatar>D</span><div><b>demo1</b><span>demo1@zlas.kr</span></div></div>'
            '<div class=grp><h4>내 서재</h4>' + a("구매 목록", "#", "buy", "128") + a("대여 목록", "#", "rent", "4") + a("찜한 책", "#", "wish", "19") + '</div>'
            '<div class=grp><h4>결제·혜택</h4>' + a("캐시 충전", "#", "cash") + a("쿠폰함", "#", "coupon", "3") + a("포인트", "#", "point") + '</div>'
            '<div class=grp><h4>계정</h4>' + a("정보 변경", "/shop/account", "account") + a("알림 설정", "#", "noti") + a("기기 관리", "#", "device") + '</div></aside>')


@app.route("/shop")
def shop_login():
    return f"""<!doctype html><html lang=ko><head><meta charset=utf-8><title>로그인 - 데모쇼핑</title>
<meta name=viewport content="width=device-width"><style>{SHOP_CSS}</style></head><body>
<main class=auth>
  <a class=logo href="/shop">DEMO</a>
  <div class=card>
    <div class=field><input type=text placeholder="아이디" autocomplete=username></div>
    <div class=field><div class=pw-wrap><input type=password placeholder="비밀번호" autocomplete=current-password><button type=button class=eye>표시</button></div></div>
    <div class=check><span class=cb>✓</span> 로그인 상태 유지</div>
    <a class="btn blue" href="/shop/my">로그인</a>
    <div class=auth-links><a href="#">아이디 찾기</a><a href="#">비밀번호 찾기</a><a href="#">회원가입</a></div>
  </div>
</main>
<div class=banner>해커톤 테스트베드 · 실제 서비스가 아닙니다</div></body></html>"""


@app.route("/shop/my")
def shop_my():
    shelf = "".join(f'<div class=book><div class=cover>{cover(i, *c)}</div><div class=t>{c[2]}</div><div class=prog><i style="width:{p}%"></i></div></div>'
                    for i, (c, p) in enumerate(zip(COVERS, [82, 35, 100, 12, 58])))
    return shop("마이페이지", f"""
      <h1 class=page-title>마이페이지</h1>
      <div class=my>{side("my")}
      <section>
        <div class=panel><h3>내 자산 <small>2026.10.31 기준</small></h3>
          <div class=stats><div class=stat><span>캐시</span><b>12,500<small>원</small></b></div><div class=stat><span>포인트</span><b>3,210<small>P</small></b></div>
          <div class=stat><span>쿠폰</span><b>3<small>장</small></b></div><div class=stat><span>읽은 책</span><b>128<small>권</small></b></div></div></div>
        <div class=panel><h3>계정 정보 <a class="act blue" href="/shop/account">정보 변경 ›</a></h3>
          <ul class=info-list><li><span class=k>아이디</span><span class=v>demo1</span></li>
          <li><span class=k>이메일</span><span class=v>demo1@zlas.kr <span class=badge>인증됨</span></span></li></ul></div>
        <div class=panel><h3>최근 읽은 책 <small>내 서재 ›</small></h3><div class=shelf>{shelf}</div></div>
      </section></div>""")


@app.route("/shop/account")
def shop_account():
    return shop("정보 변경", f"""
      <h1 class=page-title>정보 변경</h1>
      <div class=my>{side("account")}
      <section>
        <div class=panel><h3>보안</h3>
          <ul class=info-list>
          <li><span class=k>비밀번호</span><span class=v>•••••••• <small style="color:var(--muted);font-weight:600">마지막 변경 2년 전</small></span><a class="act blue" href="/shop/pw">비밀번호 변경</a></li>
          <li><span class=k>2단계 인증</span><span class=v>사용 안 함</span><a class=act href="#">설정</a></li>
          <li><span class=k>회원 탈퇴</span><span class=v><small style="color:var(--muted);font-weight:600">구매한 책·캐시가 모두 삭제됩니다</small></span><a class=act href="/shop/leave" style="color:var(--muted)">회원 탈퇴</a></li></ul></div>
        <div class=panel><h3>기본 정보</h3>
          <ul class=info-list>
          <li><span class=k>아이디</span><span class=v>demo1</span></li>
          <li><span class=k>이메일</span><span class=v>demo1@zlas.kr <span class=badge>인증됨</span></span><a class=act href="#">변경</a></li>
          <li><span class=k>휴대폰</span><span class=v>010-****-1234</span><a class=act href="#">변경</a></li></ul></div>
      </section></div>""")


@app.route("/shop/pw")
def shop_pw():
    # 빈 폼을 제출하면 여기로 되돌아온다. role=alert 는 som.js 가 헤딩으로 읽어 모델에 전달한다.
    err = ('<p role=alert style="color:var(--red);font-weight:600;margin:0 0 10px">현재 비밀번호와 새 비밀번호를 모두 입력하세요.</p>'
           if request.args.get("err") else "")
    return shop("비밀번호 변경", f"""
      <h1 class=page-title>비밀번호 변경</h1>
      <div class=my>{side("account")}
      <section><div class=panel><h3>새 비밀번호 설정 <small>안전을 위해 주기적으로 변경해 주세요</small></h3>{err}
        <form class=form action="/shop/pw/done" method=get>
        <div class=field><label for=cur>현재 비밀번호</label><input id=cur type=password name=cur placeholder="현재 비밀번호 입력" autocomplete=current-password></div>
        <div class=field><label for=new>새 비밀번호</label><input id=new type=password name=new placeholder="새 비밀번호 입력" autocomplete=new-password>
          <div class=hint>8~32자 · 영문, 숫자, 특수문자 중 2가지 이상 · 공백 없이 · 아이디 미포함</div></div>
        <div class=form-actions><a class="btn ghost sm" href="/shop/account">취소</a><button type=submit class="btn blue sm">비밀번호 변경</button></div>
        </form></div></section></div>""")


@app.route("/shop/leave")
def shop_leave():
    return shop("회원 탈퇴", f"""
      <h1 class=page-title>회원 탈퇴</h1>
      <div class=my>{side("account")}
      <section><div class=panel><h3>정말 탈퇴하시겠어요? <small>구매 목록 128권 · 캐시 12,500원이 삭제됩니다</small></h3>
        <form class=form action="/shop/leave/done" method=get>
        <div class=field><label for=reason>탈퇴 사유</label><input id=reason type=text name=reason placeholder="탈퇴 사유를 입력하세요"></div>
        <div class=form-actions><a class="btn ghost sm" href="/shop/account">취소</a><button type=submit class="btn blue sm" style="background:var(--red)">회원 탈퇴</button></div>
        </form></div></section></div>""")


@app.route("/shop/leave/done")
def shop_leave_done():
    return shop("탈퇴 완료", f"""
      <h1 class=page-title>회원 탈퇴</h1>
      <div class=my>{side("account")}
      <section><div class="panel success"><div class=ic>✓</div><h1>탈퇴 완료</h1>
        <p>demo1 계정이 삭제되었습니다. 구매 내역은 복구할 수 없습니다.</p>
        <a class="btn ghost sm" href="/shop">처음으로</a></div></section></div>""")


@app.route("/shop/pw/done")
def shop_done():
    # 실제 사이트처럼 빈 비밀번호는 거부한다. 입력을 건너뛰고 제출해도 '완료'가 뜨는 가짜 성공을 막는다.
    if not request.args.get("cur") or not request.args.get("new"):
        return redirect("/shop/pw?err=1")
    return shop("변경 완료", f"""
      <h1 class=page-title>비밀번호 변경</h1>
      <div class=my>{side("account")}
      <section><div class="panel success"><div class=ic>✓</div><h1>비밀번호 변경 완료</h1>
        <p>다른 기기에서는 자동으로 로그아웃되었습니다. 새 비밀번호로 다시 로그인해 주세요.</p>
        <a class="btn ghost sm" href="/shop/my">마이페이지로</a></div></section></div>""")


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
    <a class="btn line" style="margin-left:auto" href="/webhard/pw">비밀번호 변경</a></div>
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


@app.route("/webhard/pw")
def wh_pw():
    return hard("비밀번호 변경", """<h1>비밀번호 변경</h1>
<div class=panel><form action="/webhard/pw/done" method=get>
  <label for=cur style="display:block;font-size:13px;color:#7A7E99;font-weight:600;margin-bottom:6px">현재 비밀번호</label>
  <input id=cur type=password name=cur style="display:block;width:100%;height:42px;border:1px solid #D8DBE8;border-radius:8px;padding:0 12px;margin-bottom:12px">
  <label for=new style="display:block;font-size:13px;color:#7A7E99;font-weight:600;margin-bottom:6px">새 비밀번호</label>
  <input id=new type=password name=new style="display:block;width:100%;height:42px;border:1px solid #D8DBE8;border-radius:8px;padding:0 12px;margin-bottom:14px">
  <button class=btn type=submit>변경하기</button> <a class="btn line" href="/webhard/account">취소</a></form></div>""")


@app.route("/webhard/pw/done")
def wh_pw_done():
    return hard("변경 완료", """<div class=done><h1>비밀번호 변경 완료</h1>
        <p>모든 기기에서 다시 로그인해야 합니다.</p><a class="btn line" href="/webhard">처음으로</a></div>""")


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
