"""시연 영상 녹화: 사용자 앱(폰 프레임, 1080x1920) + 클릭 위치 표시 + 이벤트 타임라인(JSON)."""
import time, json, pathlib, shutil
from playwright.sync_api import sync_playwright
S=pathlib.Path("/tmp/zero-leak-demo")
REC=S/"demo_rec"; shutil.rmtree(REC, ignore_errors=True); REC.mkdir()
csv=S/"demo_export.csv"
RIPPLE="""([x,y])=>{const d=document.createElement('div');d.style.cssText=`position:fixed;left:${x}px;top:${y}px;width:56px;height:56px;margin:-28px 0 0 -28px;border-radius:50%;background:rgba(216,80,58,.45);box-shadow:0 0 0 6px rgba(255,255,255,.95),0 0 0 10px rgba(216,80,58,.9);z-index:99999;pointer-events:none;animation:zlr 1.1s ease-out forwards`;
if(!document.getElementById('zlr')){const s=document.createElement('style');s.id='zlr';s.textContent='@keyframes zlr{0%{transform:scale(.5);opacity:1}60%{transform:scale(1.6);opacity:.9}100%{transform:scale(2.4);opacity:0}}';document.head.appendChild(s)}
document.body.appendChild(d);setTimeout(()=>d.remove(),1150)}"""
ev=[]
with sync_playwright() as p:
    b=p.chromium.launch()
    ctx=b.new_context(viewport={"width":1080,"height":1920},record_video_dir=str(REC),record_video_size={"width":1080,"height":1920})
    pg=ctx.new_page(); t0=time.time()
    def mark(name): ev.append({"t":round(time.time()-t0,2),"e":name}); print(f"{ev[-1]['t']:6.1f}s {name}")
    def click(sel, hold=1.0):
        el=pg.locator(sel).first; bb=el.bounding_box()
        x,y=bb["x"]+bb["width"]/2, bb["y"]+bb["height"]/2
        pg.evaluate(RIPPLE,[x,y]); pg.wait_for_timeout(int(hold*1000)); el.click(); mark("click "+sel); pg.evaluate(RIPPLE,[x,y])
    pg.goto("http://localhost:8502"); pg.add_style_tag(content="body{align-items:flex-start;padding-top:86px} .phone{transform:scale(2);transform-origin:top center}"); pg.wait_for_timeout(300)
    pg.click("#resetBtn", force=True); pg.wait_for_timeout(1500); mark("push")
    pg.wait_for_timeout(5000)
    click("#pushGo"); pg.wait_for_timeout(2500); mark("risk")
    pg.wait_for_timeout(5500)
    click(".rule summary"); pg.wait_for_timeout(5500)
    click("#protectBtn"); mark("run"); t_run=time.time()
    while time.time()-t_run<150:
        pg.wait_for_timeout(500)
        if pg.locator("#sheet.on").count():
            mark("sheet "+pg.get_attribute("#approveBtn","data-site")); pg.wait_for_timeout(3500)
            click("#approveBtn"); pg.wait_for_timeout(1500)
        if pg.locator("#s-done.on").count(): mark("done"); break
    pg.wait_for_timeout(7000)
    click(".tabbar [data-tab=accounts]"); mark("accounts"); pg.wait_for_timeout(2500)
    pg.set_input_files("#csvFile", str(csv)); mark("csv"); pg.wait_for_timeout(6000)
    click(".tabbar [data-tab=home]"); mark("home"); pg.wait_for_timeout(4000); mark("end")
    ctx.close(); b.close()
(REC/"events.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1))
