const $ = s => document.querySelector(s);
const api = (p, o) => fetch(p, o).then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e)));
const toast = m => { const t = $('#toast'); t.textContent = m; t.hidden = false;
                     clearTimeout(t._t); t._t = setTimeout(() => t.hidden = true, 3200); };
const debounce = (fn, ms = 300) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

const sel = { remote: new Set(), job_type: new Set(), discipline: new Set(), source: new Set() };
let offset = 0;

// ---- tabs ----
document.querySelectorAll('.tab').forEach(b => b.onclick = () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x === b));
  document.querySelectorAll('.tab-panel').forEach(p =>
    p.classList.toggle('active', p.id === 'tab-' + b.dataset.tab));
  if (b.dataset.tab === 'outreach') loadCompanies();
  if (b.dataset.tab === 'sources') loadSources();
});

// ---- query building ----
function params(extra = {}) {
  const p = new URLSearchParams();
  const q = $('#q').value.trim();              if (q) p.set('q', q);
  const city = $('#city').value.trim();        if (city) p.set('city', city);
  const india = $('#india').value;             if (india) p.set('india', india);
  const days = $('#days').value;               if (days !== '0') p.set('days', days);
  const salary = +$('#salary').value;          if (salary) p.set('salary_min', salary);
  if ($('#hassal').checked)  p.set('has_salary', 'true');
  if ($('#starred').checked) p.set('starred', 'true');
  if ($('#notapplied').checked) p.set('applied', '0');
  for (const [k, v] of Object.entries(sel)) if (v.size) p.set(k, [...v].join(','));
  p.set('sort', $('#sort').value);
  for (const [k, v] of Object.entries(extra)) p.set(k, v);
  return p;
}

// ---- rendering ----
const money = j => {
  if (!j.salary_min) return '';
  const f = n => n >= 100000 ? (n / 100000).toFixed(n % 100000 ? 1 : 0) + 'L'
             : n >= 1000 ? Math.round(n / 1000) + 'k' : n;
  const cur = j.salary_currency === 'INR' ? '₹' : (j.salary_currency || '') + ' ';
  const per = j.salary_period === 'monthly' ? '/mo' : '/yr';
  return cur + f(j.salary_min) + (j.salary_max ? '–' + f(j.salary_max) : '') + per;
};

const esc = s => (s || '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const ago = d => {
  if (!d) return '';
  const days = Math.floor((Date.now() - new Date(d)) / 864e5);
  return isNaN(days) ? '' : days <= 0 ? 'today' : days === 1 ? '1d ago' : days < 30 ? days + 'd ago'
       : Math.floor(days / 30) + 'mo ago';
};

function jobCard(j) {
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
      <span class="tag">${esc(j.source)}</span>
      <span class="tag">${ago(j.posted_at)}</span>
      <span class="jbtns">
        <button class="icon ${j.starred ? 'on' : ''}" data-f="starred">★</button>
        <button class="icon ${j.applied ? 'on' : ''}" data-f="applied">applied</button>
        <button class="icon" data-f="hidden">hide</button>
      </span>
    </div>
    ${j.description ? `<p class="snip">${esc(j.description)}</p>` : ''}`;

  el.querySelectorAll('.icon').forEach(b => b.onclick = async () => {
    const f = b.dataset.f, next = b.classList.contains('on') ? 0 : 1;
    await api(`/api/jobs/${j.id}/${f}?value=${next}`, { method: 'POST' });
    if (f === 'hidden') { el.remove(); toast('Hidden'); }
    else b.classList.toggle('on', !!next);
  });
  return el;
}

async function load(append = false) {
  if (!append) offset = 0;
  const d = await api('/api/jobs?' + params({ offset, limit: 100 }));
  const list = $('#list');
  if (!append) list.innerHTML = '';
  if (!d.jobs.length && !append) {
    list.innerHTML = `<div class="empty"><h3>No jobs match</h3>
      <p class="muted">Loosen the filters, or hit Refresh to pull new listings.</p></div>`;
  }
  d.jobs.forEach(j => list.appendChild(jobCard(j)));
  offset += d.jobs.length;
  $('#count').textContent = `${d.total.toLocaleString()} jobs`;
  $('#more').hidden = offset >= d.total;
}

async function loadFacets() {
  const f = await api('/api/facets');
  const label = { remote: 'remote', job_type: 'job_type', discipline: 'discipline', source: 'source' };
  for (const key of Object.keys(label)) {
    const box = $('#f-' + key);
    box.innerHTML = '';
    for (const [val, n] of Object.entries(f[key] || {})) {
      const c = document.createElement('span');
      c.className = 'chip' + (sel[key].has(val) ? ' on' : '');
      c.innerHTML = `${val}<b>${n}</b>`;
      c.onclick = () => {
        sel[key].has(val) ? sel[key].delete(val) : sel[key].add(val);
        c.classList.toggle('on');
        load();
      };
      box.appendChild(c);
    }
  }
}

async function loadStats() {
  const s = await api('/api/stats');
  $('#stats').textContent =
    `${(s.total || 0).toLocaleString()} jobs · ${(s.india || 0).toLocaleString()} in India · ` +
    `${(s.with_salary || 0).toLocaleString()} list pay · ${s.starred || 0} starred`;
}

// ---- outreach ----
async function loadCompanies() {
  const d = await api('/api/companies?status=' + $('#ostatus').value);
  const tb = $('#cotable tbody');
  tb.innerHTML = '';
  const STATUSES = ['new', 'contacted', 'replied', 'confirmed', 'declined'];
  d.companies.forEach(c => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><b>${esc(c.name)}</b>${c.site ? `<br><a href="https://${esc(c.site)}" target="_blank" rel="noopener">${esc(c.site)}</a>` : ''}</td>
      <td>${esc(c.city || '')}</td>
      <td>${esc(c.kind || '')}</td>
      <td><input value="${esc(c.email || '')}" placeholder="hr@…" data-k="email"></td>
      <td><select data-k="status">${STATUSES.map(s =>
            `<option ${c.status === s ? 'selected' : ''}>${s}</option>`).join('')}</select></td>
      <td><input value="${esc(c.notes || '')}" placeholder="notes…" data-k="notes"></td>`;
    tr.querySelectorAll('[data-k]').forEach(inp => inp.onchange = async () => {
      await api('/api/companies/' + c.id, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [inp.dataset.k]: inp.value })
      });
      toast('Saved');
    });
    tb.appendChild(tr);
  });
}

async function loadSources() {
  const s = await api('/api/stats');
  $('#srctable tbody').innerHTML = s.runs.map(r => `<tr>
    <td><b>${esc(r.source)}</b></td><td>${ago(r.ran_at)}</td><td>${r.found ?? ''}</td>
    <td>${r.ok ? (r.error ? `<span class="muted">${esc(r.error)}</span>` : 'ok')
               : `<span style="color:var(--accent)">${esc(r.error || 'failed')}</span>`}</td></tr>`).join('')
    || '<tr><td colspan="4" class="muted">No runs yet — hit Refresh.</td></tr>';
}

// ---- wiring ----
['#q', '#city'].forEach(s => $(s).oninput = debounce(load));
['#india', '#days', '#sort'].forEach(s => $(s).onchange = () => load());
['#hassal', '#starred', '#notapplied'].forEach(s => $(s).onchange = () => load());
$('#salary').oninput = e => {
  const v = +e.target.value;
  $('#salval').textContent = v ? '₹' + (v / 1000) + 'k/mo' : 'any';
};
$('#salary').onchange = () => load();
$('#more').onclick = () => load(true);
$('#ostatus').onchange = loadCompanies;

$('#clear').onclick = () => {
  Object.values(sel).forEach(s => s.clear());
  ['#q', '#city'].forEach(s => $(s).value = '');
  $('#salary').value = 0; $('#salval').textContent = 'any';
  ['#hassal', '#starred', '#notapplied'].forEach(s => $(s).checked = false);
  $('#days').value = '0'; $('#india').value = '1';
  loadFacets(); load();
};

$('#refresh').onclick = async () => {
  await api('/api/ingest', { method: 'POST' });
  toast('Refreshing — watch the terminal. Reload in a minute.');
};

$('#csv').onchange = async e => {
  const file = e.target.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  try {
    const r = await api('/api/upload', { method: 'POST', body: fd });
    toast(`Added ${r.new} new of ${r.parsed} parsed`);
    loadStats(); loadFacets(); load();
  } catch (err) { toast(err.detail || 'Upload failed'); }
  e.target.value = '';
};

$('#addco').onclick = async () => {
  const name = prompt('Company name');
  if (!name) return;
  await api('/api/companies', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, city: prompt('City') || '', email: prompt('Email') || '' })
  });
  loadCompanies();
};

loadStats(); loadFacets(); load();
