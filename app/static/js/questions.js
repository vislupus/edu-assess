/* Рендериране на всички типове въпроси – режим „решаване“ (play) и „преглед“ (review). */
(function () {
  const { h, icon, icons, esc, renderMath, mathText, htmlBlock, api, toast } = App;

  function norm(s) { return String(s ?? '').replace(/\s+/g, ' ').trim().toLowerCase().replace(/[„“”]/g, '"'); }
  function normLoose(s) { return norm(s).replace(/[.,;:!?]+$/, ''); }
  function mark(ok) { return h('span', { class: 'mark' }, icon(ok ? 'check' : 'x')); }
  function splitBlanks(text) { return String(text || '').split(/(\[\[\w+\]\])/g); }

  /* ---------- избор ---------- */
  function renderChoice(q, ctx, multi) {
    const d = q.data; const r = ctx.response; const chosen = new Set(multi ? (Array.isArray(r) ? r : []) : (r ? [r] : []));
    const correct = new Set(multi ? (d.correct || []) : (d.correct ? [d.correct] : []));
    const list = h('div', { class: 'opt-list' });
    for (const o of d.options) {
      const input = h('input', { type: multi ? 'checkbox' : 'radio', name: `q${ctx.key}`, value: o.id, checked: chosen.has(o.id) || null, disabled: ctx.review || null });
      const row = h('label', { class: 'opt' + (chosen.has(o.id) ? ' selected' : '') }, input, h('span', { class: 'opt-text' }, mathText(o.text)));
      if (ctx.review) {
        if (correct.has(o.id)) { row.classList.add('is-correct'); row.append(mark(true)); }
        else if (chosen.has(o.id)) { row.classList.add('is-wrong'); row.append(mark(false)); }
      } else {
        input.addEventListener('change', () => {
          if (multi) { if (input.checked) chosen.add(o.id); else chosen.delete(o.id); ctx.onChange(Array.from(chosen)); }
          else ctx.onChange(o.id);
          list.querySelectorAll('.opt').forEach(el => el.classList.toggle('selected', el.querySelector('input').checked));
        });
      }
      list.append(row);
    }
    return list;
  }

  /* ---------- вярно/грешно ---------- */
  function renderTrueFalse(q, ctx) {
    const r = ctx.response && typeof ctx.response === 'object' ? { ...ctx.response } : {};
    const box = h('div');
    for (const s of q.data.statements) {
      const seg = h('div', { class: 'segment' });
      const mk = (val, lab, cls) => h('button', { type: 'button', class: (r[s.id] === val ? 'active ' + cls : ''), disabled: ctx.review || null, onClick: () => { r[s.id] = val; ctx.onChange(r); seg.querySelectorAll('button').forEach(b => b.classList.remove('active', 't', 'f')); } }, lab);
      const bt = mk(true, 'Вярно', 't'), bf = mk(false, 'Грешно', 'f');
      bt.addEventListener('click', () => bt.classList.add('active', 't')); bf.addEventListener('click', () => bf.classList.add('active', 'f'));
      seg.append(bt, bf);
      const row = h('div', { class: 'tf-row' }, h('div', {}, mathText(s.text)), h('div', { class: 'row gap' }, seg));
      if (ctx.review) {
        const ok = r[s.id] !== undefined && r[s.id] === s.answer;
        row.lastChild.append(h('span', { class: `badge ${ok ? 'success' : 'danger'}` }, icon(ok ? 'check' : 'x'), `Вярно: ${s.answer ? 'Вярно' : 'Грешно'}`));
      }
      box.append(row);
    }
    return box;
  }

  /* ---------- попълване / падащо меню ---------- */
  function renderBlanks(q, ctx, dropdown) {
    const r = ctx.response && typeof ctx.response === 'object' ? { ...ctx.response } : {};
    const p = h('p', { class: 'inline-text' });
    for (const part of splitBlanks(q.data.text)) {
      const m = part.match(/^\[\[(\w+)\]\]$/);
      if (!m) { p.append(mathText(part)); continue; }
      const key = m[1]; const b = q.data.blanks[key] || {};
      let field;
      if (dropdown) {
        field = h('select', { disabled: ctx.review || null }, h('option', { value: '' }, '— избери —'), ...(b.options || []).map(o => h('option', { value: o, selected: r[key] === o || null }, o)));
      } else {
        field = h('input', { type: 'text', value: r[key] || '', placeholder: '…', disabled: ctx.review || null, size: Math.max(6, (b.answers && b.answers[0] ? b.answers[0].length : 8) + 2) });
      }
      if (!ctx.review) field.addEventListener(dropdown ? 'change' : 'input', () => { r[key] = field.value; ctx.onChange(r); });
      else {
        const ok = dropdown ? norm(r[key]) === norm(b.correct) : (b.answers || []).some(a => normLoose(a) === normLoose(r[key]));
        field.classList.add(ok ? 'blank-ok' : 'blank-bad');
        p.append(field);
        if (!ok) p.append(' ', h('span', { class: 'ans-key' }, `(${dropdown ? b.correct : (b.answers || []).join(' / ')})`));
        continue;
      }
      p.append(field);
    }
    return p;
  }

  /* ---------- подреждане ---------- */
  function renderOrdering(q, ctx) {
    const items = q.data.items; const byId = Object.fromEntries(items.map(i => [i.id, i]));
    let order = Array.isArray(ctx.response) && ctx.response.length === items.length ? ctx.response.filter(id => byId[id]) : items.map(i => i.id);
    if (order.length !== items.length) order = items.map(i => i.id);
    const list = h('div', { class: 'sortable' });
    function draw() {
      list.innerHTML = '';
      order.forEach((id, idx) => {
        const it = byId[id];
        const row = h('div', { class: 'item', draggable: !ctx.review, dataset: { id } }, h('span', { class: 'handle' }, icon('grip-vertical')), h('span', { class: 'idx' }, idx + 1 + '.'), h('span', {}, mathText(it.text)));
        if (ctx.review) {
          const ok = q.data.correct_order && q.data.correct_order[idx] === id;
          row.classList.add(ok ? 'ok' : 'bad'); row.style.borderColor = ok ? 'var(--success)' : 'var(--danger-strong)';
          if (!ok && q.data.correct_order) row.append(h('span', { class: 'badge right' }, `вярно: ${q.data.correct_order.indexOf(id) + 1}`));
        } else {
          row.append(h('span', { class: 'move' }, h('button', { type: 'button', class: 'icon-btn sm', disabled: idx === 0 || null, onClick: () => move(idx, idx - 1) }, icon('chevron-up')), h('button', { type: 'button', class: 'icon-btn sm', disabled: idx === order.length - 1 || null, onClick: () => move(idx, idx + 1) }, icon('chevron-down'))));
          row.addEventListener('dragstart', e => { row.classList.add('dragging'); e.dataTransfer.setData('text/plain', id); e.dataTransfer.effectAllowed = 'move'; });
          row.addEventListener('dragend', () => row.classList.remove('dragging'));
          row.addEventListener('dragover', e => { e.preventDefault(); });
          row.addEventListener('drop', e => { e.preventDefault(); const from = order.indexOf(e.dataTransfer.getData('text/plain')); const to = idx; if (from >= 0 && from !== to) move(from, to); });
        }
        list.append(row);
      });
      icons(list);
    }
    function move(from, to) { const [x] = order.splice(from, 1); order.splice(to, 0, x); ctx.onChange(order.slice()); draw(); }
    draw();
    return list;
  }

  /* ---------- свързване ---------- */
  function renderMatching(q, ctx) {
    const r = ctx.response && typeof ctx.response === 'object' ? { ...ctx.response } : {};
    const grid = h('div', { class: 'match-grid' });
    for (const l of q.data.left) {
      const sel = h('select', { disabled: ctx.review || null }, h('option', { value: '' }, '— избери —'), ...q.data.right.map(rr => h('option', { value: rr.id, selected: r[l.id] === rr.id || null }, rr.text)));
      sel.addEventListener('change', () => { r[l.id] = sel.value; ctx.onChange(r); });
      const cell = h('div', {}, sel);
      if (ctx.review) {
        const ok = q.data.pairs && q.data.pairs[l.id] === r[l.id];
        sel.classList.add(ok ? 'blank-ok' : 'blank-bad');
        if (!ok && q.data.pairs) { const c = q.data.right.find(x => x.id === q.data.pairs[l.id]); cell.append(h('div', { class: 'ans-key small' }, 'Вярно: ' + (c ? c.text : '?'))); }
      }
      grid.append(h('div', { class: 'm-left' }, mathText(l.text)), h('span', { class: 'm-arrow' }, icon('arrow-right')), cell);
    }
    return grid;
  }

  /* ---------- групиране ---------- */
  function renderGrouping(q, ctx) {
    const r = ctx.response && typeof ctx.response === 'object' ? { ...ctx.response } : {};
    const wrap = h('div');
    const groups = q.data.groups; const items = q.data.items;
    const pool = h('div', { class: 'group-box', dataset: { g: '' } }, h('h4', { class: 'pool-title' }, 'Елементи'), h('div', { class: 'group-items' }));
    const boxes = { '': pool };
    const area = h('div', { class: 'groups' });
    for (const g of groups) { const b = h('div', { class: 'group-box', dataset: { g: g.id } }, h('h4', {}, g.name), h('div', { class: 'group-items' })); boxes[g.id] = b; area.append(b); }
    function place() {
      Object.values(boxes).forEach(b => b.querySelector('.group-items').innerHTML = '');
      for (const it of items) {
        const g = r[it.id] && boxes[r[it.id]] ? r[it.id] : '';
        const el = h('span', { class: 'g-item', draggable: !ctx.review, dataset: { id: it.id } }, mathText(it.text));
        if (ctx.review) { el.classList.add(it.group === r[it.id] ? 'ok' : 'bad'); if (it.group !== r[it.id]) { const cg = groups.find(x => x.id === it.group); el.append(h('small', { class: 'ans-key' }, `→ ${cg ? cg.name : ''}`)); } }
        else {
          el.addEventListener('dragstart', e => { el.classList.add('dragging'); e.dataTransfer.setData('text/plain', it.id); });
          el.addEventListener('dragend', () => el.classList.remove('dragging'));
          const sel = h('select', { title: 'Избери група' }, h('option', { value: '' }, '…'), ...groups.map(gg => h('option', { value: gg.id, selected: g === gg.id || null }, gg.name)));
          sel.addEventListener('change', () => { r[it.id] = sel.value; ctx.onChange({ ...r }); place(); });
          el.append(sel);
        }
        boxes[g].querySelector('.group-items').append(el);
      }
    }
    if (!ctx.review) Object.values(boxes).forEach(b => {
      b.addEventListener('dragover', e => { e.preventDefault(); b.classList.add('over'); });
      b.addEventListener('dragleave', () => b.classList.remove('over'));
      b.addEventListener('drop', e => { e.preventDefault(); b.classList.remove('over'); const id = e.dataTransfer.getData('text/plain'); if (!id) return; if (b.dataset.g) r[id] = b.dataset.g; else delete r[id]; ctx.onChange({ ...r }); place(); });
    });
    place();
    const unplaced = ctx.review && items.some(it => !(r[it.id] && boxes[r[it.id]]));
    if (unplaced) pool.querySelector('h4').textContent = 'Неразпределени';
    wrap.append(ctx.review && !unplaced ? area : h('div', { class: 'stack' }, pool, area));
    if (!ctx.review) wrap.append(h('p', { class: 'subtle mt-s' }, 'Плъзнете елементите в групите или изберете група от менюто.'));
    return wrap;
  }

  /* ---------- числов ---------- */
  function renderNumeric(q, ctx) {
    const d = q.data; const wrap = h('div', { class: 'numeric-wrap' });
    const val = ctx.response !== null && ctx.response !== undefined && ctx.response !== '' ? ctx.response : '';
    if (d.widget === 'slider') {
      const min = d.min ?? 0, max = d.max ?? 100, step = d.step ?? 1;
      const range = h('input', { type: 'range', min, max, step, value: val === '' ? min : val, disabled: ctx.review || null });
      const out = h('div', {}, h('strong', {}, 'Избрана стойност: '), h('span', { class: 'cur' }, val === '' ? '—' : `${val} ${d.unit || ''}`));
      range.addEventListener('input', () => { out.querySelector('.cur').textContent = `${range.value} ${d.unit || ''}`; ctx.onChange(Number(range.value)); });
      wrap.append(range, h('div', { class: 'range-labels' }, h('span', {}, `${min} ${d.unit || ''}`), h('span', {}, `${max} ${d.unit || ''}`)), out);
    } else {
      const inp = h('input', { type: 'number', step: 'any', value: val, placeholder: 'число', disabled: ctx.review || null });
      inp.addEventListener('input', () => ctx.onChange(inp.value === '' ? null : Number(inp.value.replace(',', '.'))));
      wrap.append(h('div', { class: 'num-input' }, inp, d.unit ? h('span', { class: 'muted' }, d.unit) : null));
    }
    if (ctx.review) {
      const ok = val !== '' && Math.abs(Number(val) - Number(d.answer)) <= (Number(d.tolerance) || 0) + 1e-9;
      wrap.append(h('div', { class: `badge ${ok ? 'success' : 'danger'}` }, icon(ok ? 'check' : 'x'), `Верен отговор: ${d.answer}${d.tolerance ? ' ± ' + d.tolerance : ''} ${d.unit || ''}`));
    }
    return wrap;
  }

  /* ---------- открий грешките ---------- */
  function renderFindErrors(q, ctx) {
    const r = ctx.response && typeof ctx.response === 'object' ? { ...ctx.response } : {};
    const tokens = String(q.data.text || '').split(/\s+/).filter(Boolean);
    const errIdx = new Map((q.data.errors || []).map(e => [String(e.index), e.correct]));
    const box = h('div', { class: 'tokens' });
    let editing = null;
    function draw() {
      box.innerHTML = '';
      tokens.forEach((t, i) => {
        const k = String(i); const fixed = r[k];
        const el = h('span', { class: 'tok', dataset: { i: k } });
        if (ctx.review) {
          if (errIdx.has(k)) { const ok = fixed !== undefined && norm(fixed) === norm(errIdx.get(k)); el.classList.add(ok ? 'ok' : 'missed'); el.append(t); if (fixed !== undefined) el.append(h('span', { class: 'fix' }, ' → ' + fixed)); if (!ok) el.append(h('span', { class: 'ans-key' }, ' (' + errIdx.get(k) + ')')); }
          else if (fixed !== undefined && norm(fixed) !== norm(t)) { el.classList.add('bad'); el.append(t, h('span', { class: 'fix' }, ' → ' + fixed)); }
          else el.append(t);
        } else if (editing === k) {
          const inp = h('input', { type: 'text', value: fixed !== undefined ? fixed : t });
          const ok = h('button', { type: 'button', class: 'icon-btn sm', onClick: () => { const v = inp.value.trim(); if (!v || v === t) delete r[k]; else r[k] = v; editing = null; ctx.onChange({ ...r }); draw(); } }, icon('check'));
          const cancel = h('button', { type: 'button', class: 'icon-btn sm', onClick: () => { editing = null; draw(); } }, icon('x'));
          inp.addEventListener('keydown', e => { if (e.key === 'Enter') ok.click(); if (e.key === 'Escape') cancel.click(); });
          el.append(h('span', { class: 'tok-editor' }, inp, ok, cancel)); setTimeout(() => inp.focus(), 0);
        } else {
          if (fixed !== undefined) { el.classList.add('edited'); el.append(t, h('span', { class: 'fix' }, fixed)); } else el.append(t);
          el.addEventListener('click', () => { editing = k; draw(); });
        }
        box.append(el, ' ');
      });
      icons(box);
    }
    draw();
    const wrap = h('div', {}, box);
    if (!ctx.review) wrap.append(h('p', { class: 'subtle mt-s' }, icon('info'), ' Кликнете върху дума, която смятате за грешна, и въведете правилната (заедно с препинателния знак след нея, ако трябва).'));
    icons(wrap);
    return wrap;
  }

  /* ---------- отворен ---------- */
  function renderOpen(q, ctx) {
    const r = ctx.response && typeof ctx.response === 'object' ? ctx.response : { text: typeof ctx.response === 'string' ? ctx.response : '' };
    const wrap = h('div', { class: 'open-editor' });
    if (ctx.review) {
      wrap.append(r.text ? htmlBlock(r.text, 'passage') : h('p', { class: 'muted' }, 'Няма отговор.'));
      if (q.data.model_answer && ctx.teacherView) wrap.append(h('details', { class: 'panel' }, h('summary', {}, icon('key-round'), 'Модел на отговор'), htmlBlock(q.data.model_answer, 'panel-body')));
      return wrap;
    }
    if (window.Quill) {
      const ed = h('div'); wrap.append(ed);
      const quill = new Quill(ed, { theme: 'snow', placeholder: 'Напишете отговора си…', modules: { toolbar: [['bold', 'italic', 'underline'], [{ list: 'ordered' }, { list: 'bullet' }], ['formula', 'clean']] } });
      if (r.text) quill.clipboard.dangerouslyPasteHTML(r.text);
      quill.on('text-change', App.debounce(() => ctx.onChange({ text: quill.getSemanticHTML() }), 400));
    } else {
      const ta = h('textarea', { rows: 6, placeholder: 'Напишете отговора си…' }, App.stripHtml(r.text || ''));
      ta.addEventListener('input', () => ctx.onChange({ text: '<p>' + esc(ta.value).replace(/\n/g, '<br>') + '</p>' }));
      wrap.append(ta);
    }
    if (q.data.min_words) wrap.append(h('p', { class: 'subtle mt-s' }, `Препоръчителен минимум: ${q.data.min_words} думи.`));
    return wrap;
  }

  /* ---------- файл ---------- */
  function renderFile(q, ctx) {
    const r = ctx.response && typeof ctx.response === 'object' ? ctx.response : null;
    const d = q.data; const wrap = h('div');
    if (d.instructions) wrap.append(htmlBlock(d.instructions, 'mb-s'));
    const box = h('div', { class: 'file-answer' + (r && r.upload_id ? ' has-file' : '') });
    function draw() {
      box.innerHTML = '';
      if (r && r.upload_id) box.append(icon('file-check-2'), ' ', h('a', { href: r.url, target: '_blank' }, r.filename));
      else box.append(icon('upload'), ' ', ctx.review ? 'Няма качен файл.' : `Качете файл (${(d.allowed_ext || []).join(', ')}; до ${d.max_mb} MB)`);
      if (!ctx.review) {
        const inp = h('input', { type: 'file', accept: (d.allowed_ext || []).map(e => '.' + e).join(','), class: 'hidden' });
        inp.addEventListener('change', async () => {
          const f = inp.files[0]; if (!f) return;
          if (f.size > d.max_mb * 1024 * 1024) { toast(`Файлът надвишава ${d.max_mb} MB`, 'error'); return; }
          const fd = new FormData(); fd.append('file', f);
          try { const up = await api('POST', '/api/uploads', fd); ctx.onChange({ upload_id: up.id, filename: up.filename, url: up.url }); Object.assign(r || (ctx.response = {}), up); box.classList.add('has-file'); ctx.response = { upload_id: up.id, filename: up.filename, url: up.url }; drawWith(ctx.response); }
          catch (e) { toast(e.message, 'error'); }
        });
        box.append(h('div', { class: 'mt-s' }, h('button', { type: 'button', class: 'btn sm', onClick: () => inp.click() }, icon('paperclip'), r && r.upload_id ? 'Смени файла' : 'Избери файл'), inp));
      }
      icons(box);
    }
    function drawWith(nr) { box.innerHTML = ''; box.append(icon('file-check-2'), ' ', h('a', { href: nr.url, target: '_blank' }, nr.filename)); box.append(h('div', { class: 'mt-s' }, h('button', { type: 'button', class: 'btn sm', onClick: () => { ctx.response = null; box.classList.remove('has-file'); draw(); } }, icon('refresh-cw'), 'Смени файла'))); icons(box); }
    draw(); wrap.append(box);
    return wrap;
  }

  /* ---------- маркирай и назови ---------- */
  function renderHotspot(q, ctx) {
    const r = ctx.response && typeof ctx.response === 'object' ? { ...ctx.response } : {};
    const d = q.data; const wrap = h('div', { class: 'hotspot-wrap' });
    const imgBox = h('div', { class: 'hotspot-img' });
    if (d.image_url) imgBox.append(h('img', { src: d.image_url, alt: '' })); else imgBox.append(h('div', { class: 'empty' }, icon('image-off'), h('div', {}, 'Няма изображение')));
    const list = h('div', { class: 'hotspot-list' });
    d.markers.forEach((m, i) => {
      const mk = h('span', { class: 'marker', style: { left: m.x + '%', top: m.y + '%' }, title: `Маркер ${i + 1}` }, i + 1);
      imgBox.append(mk);
      const sel = h('select', { disabled: ctx.review || null }, h('option', { value: '' }, '— избери —'), ...d.labels.map(l => h('option', { value: l.id, selected: r[m.id] === l.id || null }, l.text)));
      sel.addEventListener('change', () => { r[m.id] = sel.value; ctx.onChange(r); });
      const row = h('div', { class: 'hotspot-row' }, h('span', { class: 'mk' }, i + 1), sel);
      if (ctx.review) { const ok = m.label_id && r[m.id] === m.label_id; mk.classList.add(ok ? 'ok' : 'bad'); sel.classList.add(ok ? 'blank-ok' : 'blank-bad'); if (!ok) { const l = d.labels.find(x => x.id === m.label_id); row.append(h('span'), h('span', { class: 'ans-key small' }, 'Вярно: ' + (l ? l.text : '?'))); } }
      list.append(row);
    });
    wrap.append(imgBox, h('div', {}, h('p', { class: 'small muted' }, 'Изберете кое наименование отговаря на всеки маркер.'), list));
    return wrap;
  }

  /* ---------- комплексни ---------- */
  function renderComposite(q, ctx, kind) {
    const r = ctx.response && typeof ctx.response === 'object' ? { ...ctx.response } : {};
    const d = q.data; const wrap = h('div');
    if (kind === 'reading') wrap.append(htmlBlock(d.passage, 'passage'));
    else {
      if (d.audio_url) wrap.append(h('div', { class: 'passage' }, h('audio', { controls: true, src: d.audio_url, controlsList: 'nodownload' })));
      else wrap.append(h('div', { class: 'passage muted' }, icon('headphones'), ' Аудио файлът ще бъде пуснат от учителя.'));
      if (ctx.review && ctx.teacherView && d.transcript) wrap.append(h('details', { class: 'panel' }, h('summary', {}, icon('file-text'), 'Транскрипция'), h('div', { class: 'panel-body' }, d.transcript)));
    }
    d.sub_questions.forEach((sq, i) => {
      const sub = h('div', { class: 'sub-q' });
      sub.append(h('div', { class: 'sub-stem' }, h('span', { class: 'q-num' }, `${ctx.n || ''}.${i + 1} `), htmlBlock(sq.stem, 'inline')));
      const per = ctx.review && ctx.details && ctx.details.per ? ctx.details.per[sq.id] : undefined;
      sub.append(renderBody({ ...sq, type: sq.type, data: sq.data }, { ...ctx, key: `${ctx.key}_${sq.id}`, response: r[sq.id], onChange: v => { r[sq.id] = v; ctx.onChange({ ...r }); }, n: null }));
      if (ctx.review && per !== undefined) sub.append(h('div', { class: 'subtle mt-s' }, `${(per * (sq.points || 1)).toFixed(2)} / ${sq.points || 1} т.`));
      wrap.append(sub);
    });
    return wrap;
  }

  function renderBody(q, ctx) {
    switch (q.type) {
      case 'single_choice': return renderChoice(q, ctx, false);
      case 'multi_choice': return renderChoice(q, ctx, true);
      case 'true_false': return renderTrueFalse(q, ctx);
      case 'dropdown_blank': return renderBlanks(q, ctx, true);
      case 'fill_blank': return renderBlanks(q, ctx, false);
      case 'ordering': return renderOrdering(q, ctx);
      case 'matching': return renderMatching(q, ctx);
      case 'grouping': return renderGrouping(q, ctx);
      case 'numeric': return renderNumeric(q, ctx);
      case 'find_errors': return renderFindErrors(q, ctx);
      case 'open': return renderOpen(q, ctx);
      case 'file_upload': return renderFile(q, ctx);
      case 'hotspot': return renderHotspot(q, ctx);
      case 'reading': return renderComposite(q, ctx, 'reading');
      case 'listening': return renderComposite(q, ctx, 'listening');
      default: return h('p', { class: 'muted' }, 'Неподдържан тип въпрос.');
    }
  }

  function isAnswered(type, r) {
    if (r === null || r === undefined || r === '') return false;
    if (Array.isArray(r)) return r.length > 0;
    if (typeof r === 'object') { if (type === 'open') return !!(r.text && App.stripHtml(r.text)); if (type === 'file_upload') return !!r.upload_id; return Object.keys(r).length > 0; }
    return true;
  }

  /* Пълна карта на въпрос: заглавие + тяло (+ резултат при преглед). */
  function renderCard(q, ctx) {
    const card = h('div', { class: 'q-card', dataset: { qid: q.id } }, h('div', { class: 'q-card-top' }));
    const pts = h('span', { class: 'badge' }, `${q.points} т.`);
    const head = h('div', { class: 'q-head' }, h('span', { class: 'q-num' }, `${ctx.n}.`), htmlBlock(q.stem, 'q-stem'), h('span', { class: 'q-pts' }, pts));
    const body = h('div', { class: 'q-body' }, renderBody(q, ctx));
    card.append(head, body);
    if (ctx.review) {
      const fs = ctx.final_score ?? 0;
      let status = 'wrong';
      if (ctx.needs_manual && ctx.manual_score === null) status = 'manual'; else if (fs >= q.points - 1e-6) status = 'correct'; else if (fs > 0) status = 'partial';
      card.classList.add(status);
      pts.textContent = status === 'manual' ? `– / ${q.points} т.` : `${Number(fs.toFixed(2))} / ${q.points} т.`;
      pts.className = 'badge ' + ({ correct: 'success', partial: 'warning', wrong: 'danger', manual: 'info' }[status]);
      if (ctx.feedback) card.append(h('div', { class: 'q-feedback' }, icon('message-square'), ' ', ctx.feedback));
    }
    const foot = h('div', { class: 'q-foot' }, h('span', { class: 'subtle' }, q.type_label || ''), App.diffBadge(q.difficulty || 2));
    card.append(foot);
    icons(card); renderMath(card);
    return card;
  }

  window.Questions = { renderBody, renderCard, isAnswered };
})();
