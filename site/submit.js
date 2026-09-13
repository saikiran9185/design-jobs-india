/* Public submissions.
 *
 * Anyone can add a listing without an account. Nothing they send is published:
 * rows land as 'pending' and row-level security makes them invisible until a
 * human approves. So the worst a bot achieves is a longer moderation queue.
 */
(() => {
  const $ = s => document.querySelector(s);
  const cfg = window.DJI_CONFIG || {};
  const ready = Boolean(cfg.SUPABASE_URL && cfg.SUPABASE_ANON_KEY);
  let opened = 0;

  const toast = m => {
    const t = $('#toast'); t.textContent = m; t.hidden = false;
    clearTimeout(t._t); t._t = setTimeout(() => t.hidden = true, 3200);
  };

  // ---------- modal ----------
  const wrap = $('#submitwrap');
  const open = () => { wrap.hidden = false; opened = Date.now(); $('#s_title').focus(); };
  const close = () => { wrap.hidden = true; };

  $('#addjob').onclick = open;
  $('#mclose').onclick = close;
  wrap.onclick = e => { if (e.target === wrap) close(); };
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !wrap.hidden) close(); });

  document.querySelectorAll('.mtab').forEach(b => b.onclick = () => {
    document.querySelectorAll('.mtab').forEach(x => x.classList.toggle('active', x === b));
    document.querySelectorAll('.mpane').forEach(p =>
      p.classList.toggle('active', p.dataset.m === b.dataset.m));
  });

  // ---------- screenshot -> text, entirely in the browser ----------
  // Tesseract is rough on stylised Instagram type, so this prefills the form for
  // the person to correct rather than pretending to be authoritative.
  const RE = {
    salary: /(?:₹|rs\.?|inr)\s?[\d,]+(?:\s?(?:-|to|–)\s?(?:₹|rs\.?|inr)?\s?[\d,]+)?(?:\s?(?:lpa|per month|\/month|pm|monthly|per annum|\/year))?|\b\d+(?:\.\d+)?\s?-\s?\d+(?:\.\d+)?\s?lpa\b/i,
    email: /[\w.+-]+@[\w-]+\.[\w.]+/,
    url: /https?:\/\/[^\s)]+/,
    city: /\b(new delhi|delhi|gurugram|gurgaon|noida|ghaziabad|faridabad|mumbai|bengaluru|bangalore|hyderabad|chennai|pune|kolkata|ahmedabad|gandhinagar|jaipur|surat|indore|chandigarh|kochi|coimbatore|lucknow|nagpur|goa|remote)\b/i,
    role: /\b(intern(ship)?|designer|design|artist|animator|illustrator|editor|motion|graphic|ux|ui|3d|vfx)\b/i,
    // banner text that looks like a company name but is not
    banner: /^(we('| a)?re |now )?(hiring|recruiting|vacancy|vacancies|opening|openings|join us|apply now|we are hiring|urgent|immediate joiner|job alert|internship alert)\b/i,
  };

  function parseText(text) {
    const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 2);
    const out = {};
    // the title is usually the first line that names a role
    out.title = (lines.find(l => RE.role.test(l) && l.length < 90) || lines[0] || '').slice(0, 120);
    const hay = text.replace(/\s+/g, ' ');
    out.salary = (hay.match(RE.salary) || [''])[0].trim();
    out.location = (hay.match(RE.city) || [''])[0].trim();
    out.url = (hay.match(RE.url) || hay.match(RE.email) || [''])[0].trim();
    // a short ALL-CAPS or @handle line is usually the studio
    out.company = (lines.find(l =>
      /^@?[A-Z][\w&.\- ]{2,28}$/.test(l) && !RE.role.test(l) && !RE.banner.test(l)
    ) || '').replace(/^@/, '');
    out.desc = lines.slice(0, 12).join('\n').slice(0, 1500);
    return out;
  }

  $('#s_image').onchange = async e => {
    const file = e.target.files[0];
    if (!file) return;
    if (!window.Tesseract) return toast('OCR library failed to load — type it in instead');
    const status = $('#ocrstatus');
    status.textContent = 'Reading the image…';
    try {
      const { data } = await Tesseract.recognize(file, 'eng', {
        logger: m => {
          if (m.status === 'recognizing text')
            status.textContent = `Reading the image… ${Math.round(m.progress * 100)}%`;
        },
      });
      const got = parseText(data.text || '');
      if (got.title && !$('#s_title').value) $('#s_title').value = got.title;
      if (got.company && !$('#s_company').value) $('#s_company').value = got.company;
      if (got.location && !$('#s_location').value) $('#s_location').value = got.location;
      if (got.salary && !$('#s_salary').value) $('#s_salary').value = got.salary;
      if (got.url && !$('#s_url').value) $('#s_url').value = got.url;
      if (got.desc && !$('#s_desc').value) $('#s_desc').value = got.desc;
      wrap._ocr = data.text || '';
      status.textContent = 'Read it — check the fields below and fix anything wrong.';
    } catch (err) {
      status.textContent = 'Could not read that image. Type the details in instead.';
    }
  };

  // ---------- send ----------
  $('#s_submit').onclick = async () => {
    const title = $('#s_title').value.trim();
    const sourceUrl = $('#s_sourceurl').value.trim();
    if (!title && !sourceUrl) return toast('Add a title, or paste a link');
    if (title && title.length < 3) return toast('That title is too short');

    const mode = document.querySelector('.mtab.active').dataset.m;
    const row = {
      title: title || sourceUrl.slice(0, 120),
      company: $('#s_company').value.trim() || null,
      location: $('#s_location').value.trim() || null,
      city: $('#s_location').value.trim() || null,
      url: $('#s_url').value.trim() || sourceUrl || null,
      description: $('#s_desc').value.trim() || null,
      salary_text: $('#s_salary').value.trim() || null,
      kind: $('#s_kind').value,
      job_type: $('#s_kind').value === 'internship' ? 'internship' : null,
      deadline: $('#s_deadline').value || null,
      submitted_by: $('#s_by').value.trim() || null,
      source_kind: mode,
      source_url: sourceUrl || null,
      raw_ocr: wrap._ocr ? wrap._ocr.slice(0, 4000) : null,
      fill_seconds: Math.round((Date.now() - opened) / 1000),
      honeypot: $('#s_hp').value,        // RLS rejects the row if a bot filled this
      status: 'pending',
    };

    if (!ready) {
      // Not configured yet — fall back to the issue tracker so nothing is lost.
      const body = encodeURIComponent(
        Object.entries(row).filter(([k, v]) => v && !['honeypot', 'raw_ocr'].includes(k))
          .map(([k, v]) => `**${k}:** ${v}`).join('\n'));
      window.open(`${window.REPO_URL || 'https://github.com/saikiran9185/design-jobs-india'}`
        + `/issues/new?title=${encodeURIComponent('[submission] ' + row.title)}&body=${body}`, '_blank');
      toast('Submissions backend not connected yet — opening GitHub instead');
      return;
    }

    $('#s_submit').disabled = true;
    $('#s_msg').textContent = 'Sending…';
    try {
      const r = await fetch(`${cfg.SUPABASE_URL}/rest/v1/submissions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          apikey: cfg.SUPABASE_ANON_KEY,
          Authorization: `Bearer ${cfg.SUPABASE_ANON_KEY}`,
          Prefer: 'return=minimal',
        },
        body: JSON.stringify(row),
      });
      if (!r.ok) throw new Error(await r.text());
      $('#s_msg').textContent = '';
      toast('Sent — it appears once a human has reviewed it. Thank you.');
      ['#s_title', '#s_company', '#s_location', '#s_salary', '#s_url', '#s_desc',
       '#s_by', '#s_sourceurl', '#s_deadline'].forEach(s => $(s).value = '');
      wrap._ocr = null;
      close();
    } catch (err) {
      $('#s_msg').textContent = 'Could not send. Try again in a moment.';
      console.error(err);
    } finally {
      $('#s_submit').disabled = false;
    }
  };
})();
