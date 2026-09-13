/* Static build — no backend. Everything filters client-side from data/*.json.
   Personal state (stars, applied, outreach notes) lives in localStorage only. */
const $ = s => document.querySelector(s);
const REPO = 'https://github.com/saikiran9185/design-jobs-india';

let JOBS = [], COMPANIES = [], shown = 0;
const PAGE = 60;
const sel = { remote: new Set(), job_type: new Set(), discipline: new Set(), source: new Set(), city: new Set() };

// --- local state (never leaves the browser) ---
const store = {
  read(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  write(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
};
let mine = store.read('dji:jobs', {});      // id -> {starred, applied}
let notes = store.read('dji:companies', {}); // name -> {status, notes, email}

const toast = m => { const t = $('#toast'); t.textContent = m; t.hidden = false;
                     clearTimeout(t._t); t._t = setTimeout(() => t.hidden = true, 2600); };
const esc = s => (s || '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const debounce = (fn, ms = 200) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const ago = d => { if (!d) return '';
  const n = Math.floor((Date.now() - new Date(d)) / 864e5);
  return isNaN(n) ? '' : n <= 0 ? 'today' : n === 1 ? '1d ago' : n < 30 ? n + 'd ago' : Math.floor(n / 30) + 'mo ago'; };
const money = j => { if (!j.salary_min) return '';
  const f = n => n >= 1e5 ? (n / 1e5).toFixed(n % 1e5 ? 1 : 0) + 'L' : n >= 1e3 ? Math.round(n / 1e3) + 'k' : n;
  const cur = j.salary_currency === 'INR' ? '₹' : (j.salary_currency || '') + ' ';
  return cur + f(j.salary_min) + (j.salary_max ? '–' + f(j.salary_max) : '') + (j.salary_period === 'monthly' ? '/mo' : '/yr'); };

// --- tabs ---
document.querySelectorAll('.tab').forEach(b => b.onclick = () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x === b));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + b.dataset.tab));
  if (b.dataset.tab === 'outreach') renderCompanies();
});

// --- filtering ---
function filtered() {
  const q = $('#q').value.trim().toLowerCase();
  const india = $('#india').value, days = +$('#days').value, minPay = +$('#salary').value;
  const hasSal = $('#hassal').checked, onlyStar = $('#starred').checked, hideApplied = $('#notapplied').checked;
  const cutoff = days ? Date.now() - days * 864e5 : 0;

  let out = JOBS.filter(j => {
    if (q && !(`${j.title} ${j.company || ''} ${j.location || ''}`.toLowerCase().includes(q))) return false;
    if (india === '1' && !j.is_india) return false;
    if (india === '0' && j.is_india) return false;
    if (sel.city.size && !sel.city.has(j.city)) return false;
    if (sel.remote.size && !sel.remote.has(j.remote)) return false;
    if (sel.job_type.size && !sel.job_type.has(j.job_type)) return false;
    if (sel.source.size && !sel.source.has(j.source)) return false;
    if (sel.discipline.size && !j.discipline.some(d => sel.discipline.has(d))) return false;
    if (hasSal && !j.salary_min) return false;
    if (minPay && (j.pay_inr_month || 0) < minPay) return false;
    if (cutoff && new Date(j.posted_at).getTime() < cutoff) return false;
    const m = mine[j.id] || {};
    if (onlyStar && !m.starred) return false;
    if (hideApplied && m.applied) return false;
    return true;
  });

  const s = $('#sort').value;
  out.sort((a, b) =>
    s === 'salary' ? (b.pay_inr_month || 0) - (a.pay_inr_month || 0)
    : s === 'company' ? (a.company || '').localeCompare(b.company || '')
    : s === 'title' ? a.title.localeCompare(b.title)
    : new Date(b.posted_at) - new Date(a.posted_at));
  return out;
}

function card(j) {
  const m = mine[j.id] || {};
  const el = document.createElement('div');
  el.className = 'job';
  el.innerHTML = `
    <div class="top">
      <h3><a href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a></h3>
      <span class="sal">${money(j)}</span>
    </div>
    <div class="meta">
      ${j.company ? `<span class="co">${esc(j.company)}</span>` : ''}
      ${j.location ? `<span class="tag">${esc(j.location)}</span>` : ''}
      <span class="tag ${j.remote === 'remote' ? 'remote' : ''}">${j.remote}</span>
      <span class="tag ${j.job_type === 'internship' ? 'intern' : ''}">${j.job_type}</span>
      ${j.discipline.map(d => `<span class="tag disc">${d}</span>`).join('')}
      <span class="tag">${esc(j.source)}</span><span class="tag">${ago(j.posted_at)}</span>
      <span class="jbtns">
        <button class="icon ${m.starred ? 'on' : ''}" data-f="starred">★</button>
        <button class="icon ${m.applied ? 'on' : ''}" data-f="applied">applied</button>
      </span>
    </div>`;
  el.querySelectorAll('.icon').forEach(b => b.onclick = () => {
    const f = b.dataset.f;
    mine[j.id] = { ...(mine[j.id] || {}), [f]: !(mine[j.id] || {})[f] };
    store.write('dji:jobs', mine);
    b.classList.toggle('on', mine[j.id][f]);
  });
  return el;
}

function render(reset = true) {
  const rows = filtered();
  if (reset) { shown = 0; $('#list').innerHTML = ''; }
  if (!rows.length) {
    $('#list').innerHTML = `<div class="empty"><h3>No jobs match</h3>
      <p class="muted">Try clearing a filter.</p></div>`;
    $('#count').textContent = '0 jobs'; $('#more').hidden = true; return;
  }
  const frag = document.createDocumentFragment();
  rows.slice(shown, shown + PAGE).forEach(j => frag.appendChild(card(j)));
  $('#list').appendChild(frag);
  shown = Math.min(shown + PAGE, rows.length);
  $('#count').textContent = `${rows.length.toLocaleString()} job${rows.length === 1 ? '' : 's'}`;
  $('#more').hidden = shown >= rows.length;
}

function buildFacets() {
  const counts = (key, get) => {
    const m = {};
    JOBS.forEach(j => [].concat(get(j) ?? []).forEach(v => { if (v) m[v] = (m[v] || 0) + 1; }));
    return Object.entries(m).sort((a, b) => b[1] - a[1]);
  };
  const groups = {
    remote: counts('remote', j => j.remote),
    job_type: counts('job_type', j => j.job_type),
    discipline: counts('discipline', j => j.discipline),
    source: counts('source', j => j.source),
    city: counts('city', j => j.is_india ? j.city : null).slice(0, 12),
  };
  for (const [key, entries] of Object.entries(groups)) {
    const box = $('#f-' + key); if (!box) continue;
    box.innerHTML = '';
    entries.forEach(([val, n]) => {
      const c = document.createElement('span');
      c.className = 'chip' + (sel[key].has(val) ? ' on' : '');
      c.innerHTML = `${esc(val)}<b>${n}</b>`;
      c.onclick = () => { sel[key].has(val) ? sel[key].delete(val) : sel[key].add(val);
                          c.classList.toggle('on'); render(); };
      box.appendChild(c);
    });
  }
  $('#srcbreak').innerHTML = groups.source
    .map(([s, n]) => `<span class="chip">${esc(s)}<b>${n}</b></span>`).join('');
}

// --- companies ---
function renderCompanies() {
  const q = $('#coq').value.trim().toLowerCase();
  const kind = $('#cokind').value, status = $('#costatus').value;
  const STATUSES = ['new', 'contacted', 'replied', 'confirmed', 'declined'];
  const rows = COMPANIES.filter(c => {
    if (kind && c.kind !== kind) return false;
    if (q && !`${c.name} ${c.city || ''}`.toLowerCase().includes(q)) return false;
    if (status && (notes[c.name]?.status || 'new') !== status) return false;
    return true;
  });
  $('#cotable tbody').innerHTML = rows.map(c => {
    const n = notes[c.name] || {};
    const mail = n.email || c.email || '';
    const link = c.careers || (c.site ? 'https://' + c.site : '');
    return `<tr data-name="${esc(c.name)}">
      <td><b>${esc(c.name)}</b>${c.ats ? ` <span class="tag">${esc(c.ats)}</span>` : ''}
        ${link ? `<br><a href="${esc(link)}" target="_blank" rel="noopener">${esc(c.site || 'careers')}</a>` : ''}</td>
      <td>${esc(c.city || '')}</td>
      <td><input data-k="email" value="${esc(mail)}" placeholder="hr@…">
        ${mail ? `<a href="mailto:${esc(mail)}">email</a>` : ''}</td>
      <td><select data-k="status">${STATUSES.map(s =>
          `<option ${(n.status || 'new') === s ? 'selected' : ''}>${s}</option>`).join('')}</select></td>
      <td><input data-k="notes" value="${esc(n.notes || '')}" placeholder="notes…"></td></tr>`;
  }).join('') || '<tr><td colspan="5" class="muted">Nothing matches.</td></tr>';

  $('#cotable tbody').querySelectorAll('[data-k]').forEach(inp => inp.onchange = () => {
    const name = inp.closest('tr').dataset.name;
    notes[name] = { ...(notes[name] || {}), [inp.dataset.k]: inp.value };
    store.write('dji:companies', notes);
    toast('Saved in this browser');
  });
}

// --- export ---
$('#export').onclick = () => {
  const onJobs = $('#tab-jobs').classList.contains('active');
  const rows = onJobs
    ? [['title', 'company', 'location', 'remote', 'type', 'discipline', 'pay_inr_month', 'source', 'posted', 'url'],
       ...filtered().map(j => [j.title, j.company, j.location, j.remote, j.job_type,
         j.discipline.join(' '), j.pay_inr_month || '', j.source, j.posted_at, j.url])]
    : [['company', 'city', 'kind', 'site', 'email', 'status', 'notes'],
       ...COMPANIES.map(c => [c.name, c.city, c.kind, c.site,
         notes[c.name]?.email || c.email || '', notes[c.name]?.status || 'new', notes[c.name]?.notes || ''])];
  const csv = rows.map(r => r.map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(',')).join('\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  a.download = onJobs ? 'design-jobs.csv' : 'companies.csv';
  a.click(); URL.revokeObjectURL(a.href);
};

// --- wiring ---
$('#q').oninput = debounce(() => render());
['#india', '#days', '#sort'].forEach(s => $(s).onchange = () => render());
['#hassal', '#starred', '#notapplied'].forEach(s => $(s).onchange = () => render());
$('#salary').oninput = e => $('#salval').textContent = +e.target.value ? '₹' + (+e.target.value / 1000) + 'k/mo' : 'any';
$('#salary').onchange = () => render();
$('#more').onclick = () => render(false);
['#coq', '#cokind', '#costatus'].forEach(s => $(s).oninput = $(s).onchange = renderCompanies);
$('#clear').onclick = () => {
  Object.values(sel).forEach(s => s.clear());
  $('#q').value = ''; $('#salary').value = 0; $('#salval').textContent = 'any';
  ['#hassal', '#starred', '#notapplied'].forEach(s => $(s).checked = false);
  $('#days').value = '0'; $('#india').value = '';
  buildFacets(); render();
};
$('#repo').href = REPO;

// --- boot ---
(async () => {
  try {
    const [j, c] = await Promise.all([
      fetch('data/jobs.json').then(r => r.json()),
      fetch('data/companies.json').then(r => r.json()).catch(() => ({ companies: [] })),
    ]);
    JOBS = j.jobs; COMPANIES = c.companies || [];
    $('#stats').textContent =
      `${j.count.toLocaleString()} jobs · ${j.india} in India · ${COMPANIES.length} companies · updated ${ago(j.generated_at)}`;
    $('#gen').textContent = 'Last refreshed ' + new Date(j.generated_at).toLocaleString();
    buildFacets(); render();
  } catch (e) {
    $('#list').innerHTML = `<div class="empty"><h3>Could not load listings</h3>
      <p class="muted">${esc(e.message)}</p></div>`;
  }
})();
