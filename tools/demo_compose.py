import subprocess, pathlib, glob, json
S=pathlib.Path("/tmp/zero-leak-demo")
PH=glob.glob(str(S/"demo_rec/*.webm"))[0]; AG=glob.glob("/home/claude/zlas/recordings_demo/*.webm")[0]
FONT="/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"; FONTR="/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
ev={e["e"]:e["t"] for e in json.loads((S/"demo_rec/events.json").read_text())}
AG_START=ev["run"]+1.4
cues=[(0,ev["click #pushGo"],"텔레그램에 유출 덤프가 올라왔습니다. 앱이 내 계정을 발견해 알림을 보냅니다."),
 (ev["click #pushGo"],ev["click .rule summary"],"데모쇼핑은 유출 자료와 그대로 일치. 웹하드는 유출된 적 없지만 비밀번호 끝 글자만 달라 함께 위험합니다."),
 (ev["click .rule summary"],ev["run"],"조치 기준: 그대로 일치 → 변경, 1년 이상 안 쓴 변형 일치 → 탈퇴. 사용자가 직접 바꿀 수 있습니다."),
 (ev["run"],ev["sheet 데모쇼핑"],"에이전트가 쇼핑몰에 로그인해 비밀번호 변경 페이지로 이동. 검은 사각형이 비밀번호 칸 — 클라우드는 이 화면만 받습니다."),
 (ev["sheet 데모쇼핑"],ev["sheet 데모쇼핑"]+5.5,"되돌릴 수 없는 제출 직전, 반드시 사용자가 확정합니다."),
 (ev["sheet 데모쇼핑"]+5.5,ev["sheet 데모웹하드"],"웹하드: ‘혜택을 유지하고 계속 이용하기’ 유인 버튼을 두 번 통과해 탈퇴로 진행합니다."),
 (ev["sheet 데모웹하드"],ev["done"],"탈퇴도 마지막은 사용자 확정. 사유 입력까지 에이전트가 처리합니다."),
 (ev["done"],ev["accounts"],"변경 1 · 탈퇴 1 · 외부로 나간 비밀번호 0건 — 실행마다 측정한 값입니다."),
 (ev["accounts"],ev["home"],"계정 등록: Chrome·암호 앱 CSV를 기기 안에서 해시로 변환하고 원본은 파기. 서버로 가지 않습니다."),
 (ev["home"],ev["end"]+1,"Zero-Leak — 복잡하고 귀찮은 작업은 에이전트가, 확정은 사용자가.")]
for i,(a,b,t) in enumerate(cues): (S/f"cue{i}.txt").write_text(t)
(S/"panel1.txt").write_text("Zero-Leak 시연"); (S/"panel2.txt").write_text("유출 탐지 → 연쇄 위험 → 에이전트 조치 → 사용자 확정")
(S/"panel3.txt").write_text("오른쪽: 에이전트가 보는 실제 브라우저 화면\n(비밀번호 칸은 가린 채 번호만 전송)")
(S/"label.txt").write_text("에이전트 시점 — 빨간 번호 = 클릭 후보 · 검은 사각형 = 비밀번호 칸(가림)")
draw=""
for i,(a,b,t) in enumerate(cues):
    draw+=f",drawtext=fontfile={FONT}:textfile={S}/cue{i}.txt:fontsize=34:fontcolor=white:x=(w-text_w)/2:y=1000:enable='between(t,{a},{b})'"
vf=(f"[0:v]scale=-2:920[ph];"
    f"[1:v]scale=1120:-2,tpad=stop_mode=clone:stop_duration=120,setpts=PTS+{AG_START}/TB[ag];"
    f"color=c=0x15191D:s=1920x1080:d={ev['end']+1.5}[bg];"
    f"[bg][ph]overlay=80:40[a];"
    f"[a]drawbox=x=720:y=120:w=1120:h=716:color=0x1F262C@1:t=fill,"
    f"drawtext=fontfile={FONT}:textfile={S}/panel1.txt:fontsize=64:fontcolor=0x9FE3D4:x=780:y=300:enable='lt(t,{AG_START})',"
    f"drawtext=fontfile={FONTR}:textfile={S}/panel2.txt:fontsize=34:fontcolor=white:x=780:y=400:enable='lt(t,{AG_START})',"
    f"drawtext=fontfile={FONTR}:textfile={S}/panel3.txt:fontsize=30:fontcolor=0xBFD8D5:x=780:y=480:line_spacing=10:enable='lt(t,{AG_START})'[b];"
    f"[b][ag]overlay=720:120:enable='gte(t,{AG_START})'[c];"
    f"[c]drawtext=fontfile={FONTR}:textfile={S}/label.txt:fontsize=26:fontcolor=0xBFD8D5:x=720:y=850:enable='gte(t,{AG_START})',"
    f"drawbox=x=0:y=975:w=1920:h=105:color=black@0.55:t=fill{draw}[v]")
main=S/"main.mp4"
subprocess.run(["ffmpeg","-y","-loglevel","error","-i",PH,"-i",AG,"-filter_complex",vf,"-map","[v]","-t",str(ev["end"]+1.5),"-r","30","-c:v","libx264","-pix_fmt","yuv420p","-preset","medium",str(main)],check=True)
# intro / outro
(S/"intro1.txt").write_text("Zero-Leak"); (S/"intro2.txt").write_text("유출된 비밀번호 탐지부터 변경·탈퇴 에이전트까지")
(S/"intro3.txt").write_text("코디세이 AI 해커톤 2026 · 시연 영상")
(S/"outro1.txt").write_text("“내 비밀번호는 내 기기 밖으로 나가지 않습니다”"); (S/"outro2.txt").write_text("변경 1 · 탈퇴 1 · 비밀번호 평문 전송 0건")
(S/"outro3.txt").write_text("github.com/newids/zero-leak")
def card(out,d,l1,l2,l3,s1=140):
    subprocess.run(["ffmpeg","-y","-loglevel","error","-f","lavfi","-i",f"color=c=0x0F1A20:s=1920x1080:d={d}:r=30","-vf",
        f"drawtext=fontfile={FONT}:textfile={S}/{l1}:fontsize={s1}:fontcolor=white:x=(w-text_w)/2:y=380,"
        f"drawtext=fontfile={FONTR}:textfile={S}/{l2}:fontsize=44:fontcolor=0x9FE3D4:x=(w-text_w)/2:y=580,"
        f"drawtext=fontfile={FONTR}:textfile={S}/{l3}:fontsize=30:fontcolor=0xBFD8D5:x=(w-text_w)/2:y=680,fade=t=in:d=0.6,fade=t=out:st={d-0.7}:d=0.7",
        "-c:v","libx264","-pix_fmt","yuv420p",str(S/out)],check=True)
card("intro.mp4",4,"intro1.txt","intro2.txt","intro3.txt"); card("outro.mp4",6.5,"outro1.txt","outro2.txt","outro3.txt",s1=72)
(S/"concat.txt").write_text(f"file '{S}/intro.mp4'\nfile '{main}'\nfile '{S}/outro.mp4'\n")
final=S/"zero-leak_demo_100s.mp4"
subprocess.run(["ffmpeg","-y","-loglevel","error","-f","concat","-safe","0","-i",str(S/"concat.txt"),"-c:v","libx264","-pix_fmt","yuv420p","-movflags","+faststart",str(final)],check=True)
print(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(final)],capture_output=True,text=True).stdout)
