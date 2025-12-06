// static/js/calendar_admin.js — 管理用 完全版
(() => {
  const ROOT1 = document.getElementById('calendar');   // 当月
  const ROOT2 = document.getElementById('calendar2');  // 翌月（任意）

  // 小さなUIヘルパ
  function toast(msg, isErr=false) {
    let el = document.getElementById('cal-toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'cal-toast';
      el.style.cssText = `
        position:fixed; right:16px; bottom:16px; z-index:9999;
        background:${isErr?'#ffebee':'#ecfdf5'}; color:${isErr?'#a40000':'#065f46'};
        border:1px solid ${isErr?'#ffcdd2':'#a7f3d0'};
        padding:10px 14px; border-radius:10px; box-shadow:0 6px 20px rgba(0,0,0,.15);
        font-size:.92rem;`;
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.style.display = 'block';
    setTimeout(()=>{ el.style.display='none'; }, 1600);
  }

  const WJ = ['日','月','火','水','木','金','土'];
  const ymKey = (y, m) => `${y}-${String(m).padStart(2,'0')}`;
  const daysInMonth = (y, m) => new Date(y, m, 0).getDate();

  // 両形式吸収: { "YYYY-MM":[..] } or { "YYYY-MM-DD": true }
  function closedSetForMonth(map, y, m) {
    const key = ymKey(y, m);
    const set = new Set();
    if (map[key] && Array.isArray(map[key])) map[key].forEach(ds => set.add(ds));
    for (const [k,v] of Object.entries(map)) {
      if (/^\d{4}-\d{2}-\d{2}$/.test(k) && v && k.startsWith(key+'-')) set.add(k);
    }
    return set;
  }

  async function fetchHolidays() {
    const res = await fetch('/api/holidays', { cache: 'no-store' });
    if (!res.ok) throw new Error(`/api/holidays ${res.status}`);
    return res.json();
  }

  function renderMonth(targetEl, y, m, map) {
    if (!targetEl) return;
    const first = new Date(y, m - 1, 1);
    const last = daysInMonth(y, m);
    const startW = first.getDay();
    const closedSet = closedSetForMonth(map, y, m);

    let html = `<table class="cal"><caption>${y}年${m}月</caption><thead><tr>${WJ.map(d=>`<th>${d}</th>`).join('')}</tr></thead><tbody>`;
    let d = 1;
    for (let r=0;r<6;r++){
      html += '<tr>';
      for (let c=0;c<7;c++){
        if (r===0 && c<startW) { html += '<td class="empty"></td>'; continue; }
        if (d>last) { html += '<td class="empty"></td>'; continue; }
        const ds = `${y}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
        const closed = closedSet.has(ds);
        html += `<td class="${closed?'closed':''}" data-clickable="1" data-date="${ds}">${d}</td>`;
        d++;
      }
      html += '</tr>';
      if (d>last) break;
    }
    html += '</tbody></table>';
    targetEl.innerHTML = html;
  }

  async function toggleDay(ds, isClosedNow) {
    const body = { date: ds, status: isClosedNow ? null : "休業日" };
    const res = await fetch('/api/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',     // ← セッション（ログイン）送る
      body: JSON.stringify(body)
    });
    if (!res.ok) throw new Error(`/api/toggle ${res.status}`);
  }

  function wireClicks(container, getMap, rerender) {
    container.addEventListener('click', async (ev) => {
      const td = ev.target.closest('td[data-clickable="1"]');
      if (!td) return;
      const ds = td.dataset.date;
      const isClosedNow = td.classList.contains('closed');

      // 見た目を先に反映（失敗時は戻す）
      td.classList.toggle('closed', !isClosedNow);

      try {
        await toggleDay(ds, isClosedNow);
        toast(isClosedNow ? '解除しました' : '休業日に登録しました');
        await rerender(); // 再フェッチして整合
      } catch (e) {
        td.classList.toggle('closed', isClosedNow); // 元に戻す
        console.error(e);
        toast('保存に失敗しました（ログイン状態/ネットワークを確認）', true);
      }
    });
  }

  async function init() {
    try {
      let map = await fetchHolidays();
      const today = new Date();
      const y1 = today.getFullYear(), m1 = today.getMonth()+1;
      const y2 = m1===12 ? y1+1 : y1,  m2 = m1===12 ? 1 : m1+1;

      const rerender = async () => {
        map = await fetchHolidays();
        renderMonth(ROOT1, y1, m1, map);
        if (ROOT2) renderMonth(ROOT2, y2, m2, map);
      };

      renderMonth(ROOT1, y1, m1, map);
      if (ROOT2) renderMonth(ROOT2, y2, m2, map);
      if (ROOT1) wireClicks(ROOT1, () => map, rerender);
      if (ROOT2) wireClicks(ROOT2, () => map, rerender);
    } catch (e) {
      console.error(e);
      if (ROOT1) ROOT1.innerHTML = `<div class="cal-error">読み込みに失敗しました。</div>`;
    }
  }

  init();
})();
