// Set-of-Mark 주입 + 비밀번호 마스킹.
// 반환: { path, title, headings:[...], elements:[{n, label, kind, x, y}] }
// - 클릭 가능한 요소마다 [번호] 배지를 붙이고, 중심 좌표를 돌려준다.
// - 비밀번호 입력란은 검은 사각형으로 가린다(캡처 전에). 입력 값은 화면에 남지 않는다.
// - 입력란 라벨은 <label for>, 직전 <label>, placeholder, aria-label 순으로 찾는다.
() => {
  document.querySelectorAll('.zlas-badge,.zlas-mask').forEach(e => e.remove());

  const clickable = 'a, button, input, select, textarea, [role=button], [onclick]';
  const els = [...document.querySelectorAll(clickable)];
  const out = [];
  let n = 0;

  const labelFor = (el) => {
    if (el.id) {
      const l = document.querySelector(`label[for="${el.id}"]`);
      if (l && l.innerText.trim()) return l.innerText.trim();
    }
    let p = el.previousElementSibling;
    while (p) {
      if (p.tagName === 'LABEL') return p.innerText.trim();
      if (p.matches(clickable)) break;
      p = p.previousElementSibling;
    }
    if (el.closest('label')) return el.closest('label').innerText.trim();
    return '';
  };

  let covered = 0;
  for (const el of els) {
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) continue;
    if (r.bottom < 0 || r.top > innerHeight) continue;
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none') continue;
    // 팝업·오버레이에 가려진 요소는 제외한다. 클릭 좌표에 실제로 놓인 요소가 자기 자신(또는 자식·부모)이 아니면
    // 눌러도 막(overlay)에 먹힌다. 가려진 요소에 번호를 주면 모델이 헛클릭을 반복한다.
    const cx = Math.min(innerWidth - 1, Math.max(0, r.left + r.width / 2));
    const cy = Math.min(innerHeight - 1, Math.max(0, r.top + r.height / 2));
    const hit = document.elementFromPoint(cx, cy);
    if (hit && hit !== el && !el.contains(hit) && !hit.contains(el)) { covered++; continue; }
    n++;

    let kind = 'button';
    let label = '';
    if (el.tagName === 'A') {
      kind = 'link';
      label = el.innerText || el.getAttribute('aria-label') || '';
    } else if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') {
      const t = (el.type || '').toLowerCase();
      kind = (t === 'submit' || t === 'button' || t === 'checkbox' || t === 'radio') ? 'button' : 'input';
      label = (kind === 'button' ? el.value : '') || labelFor(el) || el.placeholder ||
              el.getAttribute('aria-label') || '';
      if (!label) label = (t === 'password') ? '비밀번호 입력란'
                        : (t === 'email') ? '이메일 입력란' : (el.name || '입력란');
      if (t === 'password' && !/비밀번호|password/i.test(label)) label += ' (비밀번호)';
    } else {
      label = el.innerText || el.value || el.getAttribute('aria-label') || '';
    }
    label = label.replace(/\s+/g, ' ').trim().slice(0, 40);
    // 입력란에 값이 있으면 라벨에 표시한다. 비밀번호 칸은 캡처에서 가려져 모델이 채움 여부를 알 수 없어
    // 같은 칸을 반복 입력하는 문제가 있었다. 값 자체는 보내지 않고 "채워짐" 사실만 알린다.
    if (kind === 'input' && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') && el.value) label += ' (입력됨)';

    if (el.tagName === 'INPUT' && el.type === 'password') {
      const m = document.createElement('div');
      m.className = 'zlas-mask';
      Object.assign(m.style, {
        position: 'fixed', left: r.left + 'px', top: r.top + 'px',
        width: r.width + 'px', height: r.height + 'px',
        background: '#000', zIndex: 2147483646, pointerEvents: 'none'
      });
      document.body.appendChild(m);
    }

    const b = document.createElement('div');
    b.className = 'zlas-badge';
    b.textContent = n;
    Object.assign(b.style, {
      position: 'fixed', left: Math.max(0, r.left - 18) + 'px', top: Math.max(0, r.top - 2) + 'px',
      background: '#e11', color: '#fff', font: 'bold 11px monospace',
      padding: '0 4px', borderRadius: '3px', zIndex: 2147483647, pointerEvents: 'none'
    });
    document.body.appendChild(b);

    out.push({ n, label, kind,
               x: Math.round(r.left + r.width / 2),
               y: Math.round(r.top + r.height / 2) });
  }

  const headings = [...document.querySelectorAll('h1,h2,h3,.ok,[role=alert],[role=status]')]
    .map(h => (h.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean).slice(0, 8);
  if (covered > 0) headings.unshift(`(팝업이 화면을 덮고 있어 ${covered}개 요소가 가려짐 — 먼저 닫아야 함)`);

  return { path: location.pathname, title: document.title, headings, elements: out };
}
