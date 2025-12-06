// static/js/calendar.js — 公開用（表示のみ）
(async () => {
  const ROOT1 = document.getElementById('calendar');
  const ROOT2 = document.getElementById('calendar2');

  const WJ = ['日','月','火','水','木','金','土'];
  const ymKey = (y, m) => `${y}-${String(m).padStart(2,'0')}`;
  const daysInMonth = (y, m) => new Date(y, m, 0).getDate();

  function closedSetForMonth(map, y, m) {
    const key = ymKey(y, m);
    const set = new Set();
    if (map[key] && Array.isArray(map[key])) map[key].forEach(ds => set.add(ds));
    for (const [k,v] of Object.entries(map)) {
      if (/^\d{4}-\d{2}-\d{2}$/.test(k) && v && k.startsWith(key+'-')) set.add(k);
    }
    return set;
  }

  function renderMonth(targetEl, y, m, map) {
    if (!targetEl) return;
    const first = new Date(y, m - 1, 1);
    const last = daysInMonth(y, m);
    const startW = first.getDay();
    const closedSet = closedSetForMonth(map, y, m);

    let html = `<table class="cal"><caption>${y}年${m}月</caption><thead><tr>${WJ.map(d=>`<th>${d}</th>`).join('')}</tr></thead><tbody>`;
    let d=1;
    for (let r=0;r<6;r++){
      html += '<tr>';
      for (let c=0;c<7;c++){
        if (r===0 && c<startW) { html += '<td class="empty"></td>'; continue; }
        if (d>last) { html += '<td class="empty"></td>'; continue; }
        const ds = `${y}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
        const closed = closedSet.has(ds);
        html += `<td class="${closed?'closed':''}" data-date="${ds}">${d}</td>`;
        d++;
      }
      html += '</tr>';
      if (d>last) break;
    }
    html += '</tbody></table>';
    targetEl.innerHTML = html;
  }

  try {
    const res = await fetch('/api/holidays', { cache: 'no-store' });
    const map = await res.json();

    const today = new Date();
    const y1 = today.getFullYear(), m1 = today.getMonth()+1;
    const y2 = m1===12 ? y1+1 : y1, m2 = m1===12 ? 1 : m1+1;

    renderMonth(ROOT1, y1, m1, map);
    renderMonth(ROOT2, y2, m2, map);
  } catch (e) {
    console.error(e);
    if (ROOT1) ROOT1.innerHTML = `<div class="cal-error">読み込みに失敗しました。</div>`;
  }
})();
