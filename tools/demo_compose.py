import subprocess, pathlib, glob, json
S=pathlib.Path("/tmp/zero-leak-demo")
PH=glob.glob(str(S/"demo_rec/*.webm"))[0]; AG=glob.glob("/home/claude/zlas/recordings_demo/*.webm")[0]
FONT="/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"; FONTR="/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
ev={}
for e in json.loads((S/"demo_rec/events.json").read_text()): ev.setdefault(e["e"], e["t"])
AG_START=ev["run"]+1.4; END=ev["end"]+1.5
# 짧은 자막: 한 줄 24자 이내, 최대 2줄, 4~7초
cues=[(0,ev["click #pushGo"]-0.3,"다크웹에 개인 계정 유출 덤프 등장\n“내 계정이 발견됐습니다”"),
 (ev["click #pushGo"],ev["risk"]+3.2,"앱이 알림을 보냅니다"),
 (ev["risk"]+3.4,ev["scroll .rule"]-0.2,"쇼핑몰: 유출과 그대로 일치\n웹하드: 끝 글자만 다른 변형"),
 (ev["scroll .rule"],ev["scroll #protectBtn"]-0.2,"사용자의 비밀번호는 온디바이스에서 처리되므로 안전\n비밀번호를 변경할지 사이트를 탈퇴할지 사용자가 선택할 수 있습니다"),
 (ev["scroll #protectBtn"],ev["run"]+5.5,"Zero-Leak이 쇼핑몰에 로그인\n사이트마다 다른 ‘비밀번호 변경 페이지’ 접근은 VLM이 담당"),
 (ev["run"]+5.7,ev["sheet 데모쇼핑"]-0.2,"검은 사각형 = 비밀번호 칸\n이때 개인정보가 유출되지 않도록 마스킹 처리"),
 (ev["sheet 데모쇼핑"],ev["auto 데모쇼핑"]+0.8,"제출 직전 5초, 그대로 두면 자동 확정\n2FA·거부 응답 등 예외만 사용자 개입"),
 (ev["auto 데모쇼핑"]+1.0,ev["auto 데모쇼핑"]+4.0,"쇼핑몰 비밀번호 변경 완료"),
 (ev["auto 데모쇼핑"]+4.2,ev["sheet 데모웹하드"]-0.2,"웹하드 탈퇴 과정 예시\n보관 파일을 미끼로 탈퇴를 만류하는 팝업 등 자동 처리"),
 (ev["sheet 데모웹하드"],ev["done"]-0.2,"탈퇴 사유까지 Zero-Leak이 입력\n제출 직전 5초 뒤 자동 확정"),
 (ev["done"],ev["accounts"]-0.2,"비밀번호 변경은 온디바이스에서 처리되므로\n유출 위험 방지"),
 (ev["accounts"],ev["csv"]+1.2,"계정 등록: 내보낸 CSV 선택"),
 (ev["csv"]+1.4,ev["home"]-0.2,"기기 안에서 해시로 변환, 원본 파기\n서버로 가지 않습니다"),
 (ev["home"],END,"수백 개 사이트 비밀번호 변경도 1시간 안에\n(동시 처리 확장 시 목표)")]
steps=[("① 알림",0,ev["risk"]),("② 연쇄 위험",ev["risk"],ev["run"]),("③ Zero-Leak 조치",ev["run"],ev["done"]),("④ 완료 리포트",ev["done"],ev["accounts"]),("⑤ 계정 등록",ev["accounts"],END)]
for i,(t,a,b) in enumerate(steps): (S/f"step{i}.txt").write_text(t)
(S/"panel1.txt").write_text("Zero-Leak 시연"); (S/"panel2.txt").write_text("유출 탐지 → 연쇄 위험 → Zero-Leak 조치 → 사용자 확정")
(S/"panel3.txt").write_text("오른쪽: Zero-Leak이 보는 실제 브라우저 화면\n(비밀번호 칸은 가린 채 번호만 전송)")
(S/"label.txt").write_text("Zero-Leak 시점 — 빨간 번호 = 클릭 후보 · 검은 사각형 = 비밀번호 칸(가림)")
(S/"note.txt").write_text("화면 녹화: 규칙(mock) 모드 · 실측 수치는 다음 카드(네이버클라우드 vLLM 주행)")
def fade(a,b,d=0.35): return f"if(lt(t-{a},{d}),(t-{a})/{d},if(lt({b}-t,{d}),({b}-t)/{d},1))"
FS=68; Y0=900; Y1=985; YC=942   # 2줄: 윗줄 Y0, 아랫줄 Y1 / 1줄: YC
def fs(line): return 68 if len(line)<=24 else (56 if len(line)<=30 else 48)
draw=""
for i,(a,b,txt) in enumerate(cues):
    lines=txt.split("\n")
    if len(lines)==1:
        (S/f"cue{i}_0.txt").write_text(lines[0])
        draw+=(f",drawtext=fontfile={FONT}:textfile={S}/cue{i}_0.txt:fontsize={fs(lines[0])}:fontcolor=white:x=(w-text_w)/2"
               f":y='{YC}+22*(1-min(1,(t-{a})/0.35))':alpha='{fade(a,b)}':enable='between(t,{a},{b})'")
    else:
        d2=min(1.5,(b-a)/3)                       # 둘째 줄이 나타나기까지
        (S/f"cue{i}_0.txt").write_text(lines[0]); (S/f"cue{i}_1.txt").write_text(lines[1])
        # 첫 줄: 아래 자리(Y1)에 등장 → 둘째 줄이 올 때 위(Y0)로 올라감
        draw+=(f",drawtext=fontfile={FONT}:textfile={S}/cue{i}_0.txt:fontsize={fs(lines[0])}:fontcolor=white:x=(w-text_w)/2"
               f":y='{Y1}+22*(1-min(1,(t-{a})/0.35))-{Y1-Y0}*max(0,min(1,(t-{a}-{d2})/0.35))':alpha='{fade(a,b)}':enable='between(t,{a},{b})'")
        # 둘째 줄: d2 뒤 아래 자리(Y1)에 등장
        draw+=(f",drawtext=fontfile={FONT}:textfile={S}/cue{i}_1.txt:fontsize={fs(lines[1])}:fontcolor=white:x=(w-text_w)/2"
               f":y='{Y1}+22*(1-min(1,(t-{a}-{d2})/0.35))':alpha='{fade(a+d2,b)}':enable='between(t,{a+d2},{b})'")
stepdraw=""
STEP_X=[740,870,1060,1330,1540]; STEP_W=[90,150,230,170,150]
for i,(t,a,b) in enumerate(steps):
    x=STEP_X[i]
    stepdraw+=(f",drawtext=fontfile={FONTR}:textfile={S}/step{i}.txt:fontsize=26:fontcolor=0x6E7B84:x={x}:y=44"
               f",drawtext=fontfile={FONT}:textfile={S}/step{i}.txt:fontsize=26:fontcolor=0x9FE3D4:x={x}:y=44:enable='between(t,{a},{b})'"
               f",drawbox=x={x}:y=84:w={STEP_W[i]}:h=4:color=0x0E7C6B@0.95:t=fill:enable='between(t,{a},{b})'")
vf=(f"[0:v]scale=-2:840[ph];"
    f"[1:v]scale=1120:-2,tpad=stop_mode=clone:stop_duration=150,setpts=PTS+{AG_START}/TB[ag];"
    f"color=c=0x15191D:s=1920x1080:d={END}[bg];"
    f"[bg][ph]overlay=90:25[a];"
    f"[a]drawbox=x=720:y=120:w=1120:h=716:color=0x1F262C@1:t=fill,"
    f"drawtext=fontfile={FONT}:textfile={S}/panel1.txt:fontsize=64:fontcolor=0x9FE3D4:x=780:y=300:enable='lt(t,{AG_START})',"
    f"drawtext=fontfile={FONTR}:textfile={S}/panel2.txt:fontsize=34:fontcolor=white:x=780:y=400:enable='lt(t,{AG_START})',"
    f"drawtext=fontfile={FONTR}:textfile={S}/panel3.txt:fontsize=30:fontcolor=0xBFD8D5:x=780:y=480:line_spacing=10:enable='lt(t,{AG_START})'[b];"
    f"[b][ag]overlay=720:120:enable='gte(t,{AG_START})'[c];"
    f"[c]drawtext=fontfile={FONTR}:textfile={S}/label.txt:fontsize=26:fontcolor=0xBFD8D5:x=720:y=850:enable='gte(t,{AG_START})*not(between(t,{ev['done']},{ev['accounts']}))',"
    f"drawtext=fontfile={FONTR}:textfile={S}/note.txt:fontsize=26:fontcolor=0xF2B544:x=720:y=850:enable='between(t,{ev['done']},{ev['accounts']})'{stepdraw},"
    f"drawbox=x=0:y=880:w=1920:h=200:color=black@0.62:t=fill,"
    f"drawbox=x=0:y=877:w='1920*t/{END}':h=4:color=0x0E7C6B@0.95:t=fill{draw}[v]")
main=S/"main.mp4"
subprocess.run(["ffmpeg","-y","-loglevel","error","-i",PH,"-i",AG,"-filter_complex",vf,"-map","[v]","-t",str(END),"-r","30","-c:v","libx264","-pix_fmt","yuv420p","-preset","medium",str(main)],check=True)
(S/"intro1.txt").write_text("Zero-Leak"); (S/"intro2.txt").write_text("유출된 비밀번호 탐지부터 변경·탈퇴까지, Zero-Leak이 직접")
(S/"intro3.txt").write_text("코디세이 AI 해커톤 2026 · 시연 영상")
(S/"outro1.txt").write_text("“내 비밀번호는 내 기기 밖으로 나가지 않습니다”"); (S/"outro2.txt").write_text("변경 1 · 탈퇴 1 · 비밀번호 평문 전송 0건")
(S/"outro3.txt").write_text("github.com/newids/zero-leak")
def card(out,d,l1,l2,l3,s1=140,eyebrow=None):
    eb=""
    if eyebrow:
        (S/f"{out}_eyebrow.txt").write_text(eyebrow)
        eb=f"drawtext=fontfile={FONTR}:textfile={S}/{out}_eyebrow.txt:fontsize=30:fontcolor=0x9FE3D4:x=(w-text_w)/2:y=300:alpha='min(1,t/0.5)',"
    subprocess.run(["ffmpeg","-y","-loglevel","error","-f","lavfi","-i",f"color=c=0x0F1A20:s=1920x1080:d={d}:r=30","-vf",
        eb+f"drawtext=fontfile={FONT}:textfile={S}/{l1}:fontsize={s1}:fontcolor=white:x=(w-text_w)/2:y='380-12*(1-min(1,t/0.6))',"
        f"drawtext=fontfile={FONTR}:textfile={S}/{l2}:fontsize=44:fontcolor=0x9FE3D4:x=(w-text_w)/2:y=580:alpha='min(1,max(0,(t-0.5)/0.8))',"
        f"drawtext=fontfile={FONTR}:textfile={S}/{l3}:fontsize=30:fontcolor=0xBFD8D5:x=(w-text_w)/2:y=680:alpha='min(1,max(0,(t-1.0)/0.8))',fade=t=out:st={d-0.7}:d=0.7",
        "-c:v","libx264","-pix_fmt","yuv420p",str(S/out)],check=True)
card("intro.mp4",4,"intro1.txt","intro2.txt","intro3.txt"); (S/"thanks1.txt").write_text("감사합니다."); (S/"thanks2.txt").write_text("Zero-Leak — 변경 1 · 탈퇴 1 · 비밀번호 평문 전송 0건"); (S/"thanks3.txt").write_text("github.com/newids/zero-leak")
subprocess.run(["ffmpeg","-y","-loglevel","error","-f","lavfi","-i","color=c=0x0F1A20:s=1920x1080:d=5.6:r=30","-vf",
    f"drawtext=fontfile={FONT}:textfile={S}/thanks1.txt:fontsize=150:fontcolor=white:x=(w-text_w)/2:y='(h-text_h)/2-60-12*(1-min(1,t/0.6))',"
    f"drawtext=fontfile={FONTR}:textfile={S}/thanks2.txt:fontsize=40:fontcolor=0x9FE3D4:x=(w-text_w)/2:y=(h-text_h)/2+120:alpha='min(1,max(0,(t-0.5)/0.6))',"
    f"drawtext=fontfile={FONTR}:textfile={S}/thanks3.txt:fontsize=30:fontcolor=0xBFD8D5:x=(w-text_w)/2:y=(h-text_h)/2+190:alpha='min(1,max(0,(t-0.9)/0.6))'",
    "-c:v","libx264","-pix_fmt","yuv420p",str(S/"outro.mp4")],check=True)
(S/"mid1.txt").write_text("유출 1건 → 2개 사이트 조치 완료"); (S/"mid2.txt").write_text("변경 1 · 탈퇴 1 · 사용자 확정 2회 · 비밀번호 평문 전송 0건")
(S/"mid3.txt").write_text("다음 — 계정은 어떻게 등록하나?")
card("mid.mp4",5.5,"mid1.txt","mid2.txt","mid3.txt",s1=84,eyebrow="실제 실행 결과")
# 네이버클라우드 GPU 서버 — VLM 화면 판단 (실측 기록: docs/zero-leak 코드 분석 메모.md)
def card_lines(out,d,eyebrow,title,lines):
    (S/f"{out}_e.txt").write_text(eyebrow); (S/f"{out}_t.txt").write_text(title)
    vf=(f"drawtext=fontfile={FONTR}:textfile={S}/{out}_e.txt:fontsize=30:fontcolor=0x9FE3D4:x=160:y=200:alpha='min(1,t/0.5)',"
        f"drawtext=fontfile={FONT}:textfile={S}/{out}_t.txt:fontsize={72 if len(title)<=24 else 58}:fontcolor=white:x=160:y='250-16*(1-min(1,t/0.6))':alpha='min(1,t/0.6)'")
    for i,l in enumerate(lines):
        (S/f"{out}_{i}.txt").write_text(l); s=0.9+i*0.55
        vf+=(f",drawbox=x=160:y={430+i*96}:w=10:h=56:color=0x0E7C6B@0.95:t=fill:enable='gte(t,{s})',"
             f"drawtext=fontfile={FONTR}:textfile={S}/{out}_{i}.txt:fontsize=38:fontcolor=0xE8ECEA:x=196:y='{436+i*96}+14*(1-min(1,max(0,(t-{s})/0.5)))':alpha='min(1,max(0,(t-{s})/0.5))'")
    vf+=f",fade=t=out:st={d-0.6}:d=0.6"
    subprocess.run(["ffmpeg","-y","-loglevel","error","-f","lavfi","-i",f"color=c=0x0F1A20:s=1920x1080:d={d}:r=30","-vf",vf,"-c:v","libx264","-pix_fmt","yuv420p",str(S/f"{out}.mp4")],check=True)
card_lines("vlmA",9,"네이버클라우드 GPU 서버 · NVIDIA L4 23GB","VLM이 ‘비밀번호 변경’ 페이지 경로를 화면만 보고 탐색",
    ["vLLM + Qwen2.5-VL-7B-Instruct-AWQ 서빙, OpenAI 호환 API · GPU 17.2GB 사용",
     "입력: 비밀번호 칸을 가린 PNG + 번호 목록 → 출력: click(n) / fill(n) JSON 하나",
     "응답 0.4~1.2초 (목표 3초) · 게이트웨이가 토큰 확률로 confidence 계산",
     "confidence 0.8 미만 → Claude 승격 · 결제·송금·유지하기 등 금지어는 가드레일 차단"])
card_lines("vlmC",9,"실측 — 테스트베드 전체 주행 (vllm 경로, 승격 임계값 0.8)","메뉴 이동은 Qwen 단독, 입력은 Claude 승격",
    ["데모쇼핑 비밀번호 변경 9단계 완료 · 데모웹하드 탈퇴 8단계 완료 (유인 팝업 2회 통과)",
     "메뉴 이동 confidence 0.94~1.00 → Qwen 단독 · 입력 칸 0.42~0.67 → Claude 승격 (17단계 중 6)",
     "전체 37.3초 · 외부 전송 검사 33건 · 비밀번호 평문 전송 0건",
     "실제 전자책 서점에서도 로그인 → 내 정보 관리 → 비밀번호 변경 12단계·63초 성공 (본인 계정)"])
tcut=ev["accounts"]-0.4
subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(main),"-t",str(tcut),"-c:v","libx264","-pix_fmt","yuv420p",str(S/"mainA.mp4")],check=True)
subprocess.run(["ffmpeg","-y","-loglevel","error","-ss",str(tcut),"-i",str(main),"-c:v","libx264","-pix_fmt","yuv420p",str(S/"mainB.mp4")],check=True)
(S/"concat.txt").write_text(f"file '{S}/intro.mp4'\nfile '{S}/mainA.mp4'\nfile '{S}/vlmA.mp4'\nfile '{S}/vlmC.mp4'\nfile '{S}/mid.mp4'\nfile '{S}/mainB.mp4'\nfile '{S}/outro.mp4'\n")
final=S/"zero-leak_demo_100s.mp4"
subprocess.run(["ffmpeg","-y","-loglevel","error","-f","concat","-safe","0","-i",str(S/"concat.txt"),"-c:v","libx264","-pix_fmt","yuv420p","-movflags","+faststart",str(final)],check=True)
print(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(final)],capture_output=True,text=True).stdout)
