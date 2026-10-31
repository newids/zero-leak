#!/usr/bin/env python3
"""
Zero-Leak 테스트베드 (데모 전용, 실제 사이트 아님).
- /shop     데모쇼핑: 로그인 → 마이페이지 → 회원정보 → 비밀번호 변경 (4~5단계)
- /webhard  데모웹하드: 설정 → 계정 → '유지하기' 유인 팝업 2회 → 탈퇴 완료 (다크패턴)
세션 없이 쿼리스텝으로 흐름만 모사한다. 모든 계정/비밀번호는 가짜.
"""
from flask import Flask, request, redirect

app = Flask(__name__)

PAGE = """<!doctype html><html lang=ko><meta charset=utf-8>
<title>{title}</title>
<style>
 body{{font-family:system-ui,'Apple SD Gothic Neo',sans-serif;max-width:560px;
   margin:40px auto;padding:0 16px;color:#222}}
 h2{{border-bottom:2px solid #06c;padding-bottom:6px}}
 .btn{{display:inline-block;background:#06c;color:#fff;border:0;padding:10px 18px;
   border-radius:6px;font-size:15px;cursor:pointer;text-decoration:none;margin:6px 4px}}
 .muted{{background:#eee;color:#888}}
 .ghost{{background:none;color:#aaa;font-size:12px;text-decoration:underline}}
 input{{display:block;width:100%;padding:9px;margin:8px 0;font-size:14px;
   border:1px solid #bbb;border-radius:5px;box-sizing:border-box}}
 .ok{{color:#0a0;font-weight:bold;font-size:18px}}
 .nav{{color:#888;font-size:12px;margin-bottom:12px}}
</style>
<div class=nav>데모쇼핑/데모웹하드 — 해커톤 테스트베드 (실제 사이트 아님)</div>
<h2>{title}</h2>{body}</html>"""


def pg(title, body):
    return PAGE.format(title=title, body=body)


# ---------------------------------------------------------------- 데모쇼핑 (변경)
@app.route("/shop")
def shop_login():
    return pg("데모쇼핑 로그인", """
      <input type=email placeholder=이메일>
      <input type=password placeholder=비밀번호>
      <a class=btn href="/shop/my">로그인</a>""")

@app.route("/shop/my")
def shop_my():
    return pg("마이페이지", """
      <p>안녕하세요, demo1 님</p>
      <a class=btn href="/shop/account">회원정보 수정</a>
      <a class=btn muted href="/shop">주문내역</a>""")

@app.route("/shop/account")
def shop_account():
    return pg("회원정보 수정", """
      <a class=btn href="/shop/pw">비밀번호 변경</a>
      <a class=btn muted href="/shop/my">배송지 관리</a>""")

@app.route("/shop/pw")
def shop_pw():
    return pg("비밀번호 변경", """
      <form action="/shop/pw/done" method=get>
      <label>현재 비밀번호</label><input type=password name=cur>
      <label>새 비밀번호</label><input type=password name=new>
      <button class=btn type=submit>변경하기</button></form>""")

@app.route("/shop/pw/done")
def shop_done():
    return pg("완료", '<p class=ok>비밀번호 변경 완료</p>')


# ---------------------------------------------------------------- 데모웹하드 (탈퇴 + 다크패턴)
@app.route("/webhard")
def wh_home():
    return pg("데모웹하드", """
      <p>내 보관함 (1.2TB)</p>
      <a class=btn href="/webhard/settings">설정</a>""")

@app.route("/webhard/settings")
def wh_settings():
    return pg("설정", """
      <a class=btn href="/webhard/account">계정 관리</a>
      <a class=btn muted href="/webhard">알림 설정</a>""")

@app.route("/webhard/account")
def wh_account():
    # 탈퇴 링크는 작고 흐리게(다크패턴)
    return pg("계정 관리", """
      <a class=btn muted href="/webhard">비밀번호 변경</a>
      <a class=ghost href="/webhard/leave1">회원 탈퇴</a>""")

@app.route("/webhard/leave1")
def wh_leave1():
    # 유인 팝업 1: 큰 버튼 = 유지, 작은 글자 = 계속 탈퇴
    return pg("잠깐만요!", """
      <p>지금 탈퇴하면 보관 중인 1.2TB가 모두 삭제됩니다.</p>
      <a class=btn href="/webhard">혜택을 유지하고 계속 이용하기</a>
      <a class=ghost href="/webhard/leave2">포기하고 떠나기</a>""")

@app.route("/webhard/leave2")
def wh_leave2():
    # 유인 팝업 2
    return pg("정말 떠나시겠어요?", """
      <p>7일 안에 돌아오면 데이터를 복구할 수 있어요.</p>
      <a class=btn href="/webhard">조금 더 써볼게요</a>
      <a class=ghost href="/webhard/leave3">그래도 탈퇴할게요</a>""")

@app.route("/webhard/leave3")
def wh_leave3():
    return pg("탈퇴 사유", """
      <form action="/webhard/done" method=get>
      <input name=reason placeholder="탈퇴 사유를 입력하세요">
      <button class=btn type=submit>회원 탈퇴</button></form>""")

@app.route("/webhard/done")
def wh_done():
    return pg("완료", '<p class=ok>탈퇴 완료</p>')


@app.route("/")
def index():
    return pg("테스트베드", """
      <a class=btn href="/shop">데모쇼핑 (비밀번호 변경)</a>
      <a class=btn href="/webhard">데모웹하드 (탈퇴)</a>""")


if __name__ == "__main__":
    app.run(port=5001, debug=False)
