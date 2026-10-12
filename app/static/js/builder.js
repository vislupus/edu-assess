/* Конструктор на тест: контейнери (секции), въпроси, AI генериране, банка. */
(function () {
  const { h, icon, icons, api, toast, modal, confirmDialog, renderMath, debounce } = App;
  const root = document.getElementById('builder'); if (!root) return;
  const testId = Number(root.dataset.test); const aiMode = root.dataset.ai;
  let test = null; let busy = false;

  async function load() { test = await api('GET', `/api/tests/${testId}`); render(); }
  const saveMeta = debounce(async (patch) => { try { test = await api('PATCH', `/api/tests/${testId}`, { title: test.title, description: test.description, curriculum_id: test.curriculum_id, ...patch }); document.getElementById('crumbTitle').textContent = test.title; } catch (e) { toast(e.message, 'error'); } }, 500);

  function qItem(q, idx) {
    const meta = Editor.TYPE_META[q.type] || {};
    const el = h('div', { class: 'q-item', draggable: true, dataset: { qid: q.id } },
      h('span', { class: 'drag' }, icon('grip-vertical')), h('span', { class: 'q-num' }, `${idx}.`),
      h('div', { class: 'q-item-body' }, App.htmlBlock(q.stem || '<em>(без условие)</em>', 'q-item-stem'), h('div', { class: 'q-item-meta' }, h('span', {}, icon(meta.icon || 'help-circle'), ' ', meta.label || q.type), App.diffBadge(q.difficulty), h('span', {}, `${q.points} т.`), q.topic ? h('span', {}, icon('tag'), ' ', q.topic) : null, q.source === 'ai' ? h('span', { class: 'badge' }, icon('sparkles'), 'AI') : q.source === 'bank' ? h('span', { class: 'badge' }, icon('library'), 'банка') : null)),
      h('div', { class: 'q-item-actions' },
        h('button', { class: 'icon-btn sm', title: 'Преглед', onClick: () => Editor.preview(q) }, icon('eye')),
        h('button', { class: 'icon-btn sm', title: 'Редакция', onClick: () => Editor.open({ question: q, testId, onSave: load }) }, icon('pencil')),
        aiMode !== 'off' && test.curriculum_id ? h('button', { class: 'icon-btn sm', title: 'Генерирай нов вариант с AI', onClick: () => regenerate(q) }, icon('refresh-cw')) : null,
        h('button', { class: 'icon-btn sm', title: 'Дублирай', onClick: async () => { await api('POST', `/api/questions/${q.id}/duplicate`); load(); } }, icon('copy')),
        h('button', { class: 'icon-btn sm', title: 'Копирай в банката', onClick: async () => { await api('POST', `/api/questions/${q.id}/to-bank`); toast('Копирано в банката', 'success'); } }, icon('library')),
        h('button', { class: 'icon-btn sm danger', title: 'Премахни', onClick: async () => { if (await confirmDialog('Премахване на въпроса от теста?', { danger: true, okText: 'Премахни' })) { await api('DELETE', `/api/questions/${q.id}`); load(); } } }, icon('trash-2'))));
    el.addEventListener('dragstart', e => { e.dataTransfer.setData('text/plain', 'q:' + q.id); el.classList.add('dragging'); });
    el.addEventListener('dragend', () => el.classList.remove('dragging'));
    el.addEventListener('dragover', e => { e.preventDefault(); });
    el.addEventListener('drop', e => { e.preventDefault(); e.stopPropagation(); const d = e.dataTransfer.getData('text/plain'); if (!d.startsWith('q:')) return; moveQuestion(Number(d.slice(2)), q.section_key, q.id); });
    return el;
  }
  async function moveQuestion(qid, sectionKey, beforeId) {
    const qs = test.questions.filter(q => q.id !== qid); const moving = test.questions.find(q => q.id === qid); if (!moving) return;
    moving.section_key = sectionKey;
    const idx = beforeId ? qs.findIndex(q => q.id === beforeId) : -1;
    if (idx >= 0) qs.splice(idx, 0, moving); else { const last = qs.map((q, i) => q.section_key === sectionKey ? i : -1).filter(i => i >= 0).pop(); qs.splice(last === undefined ? qs.length : last + 1, 0, moving); }
    // пренареждаме така, че секциите да са последователни
    const ordered = []; for (const s of test.sections) ordered.push(...qs.filter(q => q.section_key === s.key)); ordered.push(...qs.filter(q => !test.sections.find(s => s.key === q.section_key)));
    await api('POST', `/api/tests/${testId}/reorder`, { order: ordered.map(q => ({ id: q.id, section_key: q.section_key })) }); load();
  }
  async function regenerate(q) {
    const instr = h('input', { type: 'text', placeholder: 'напр. по-лесен; с друг контекст' });
    const m = modal({ title: 'Нов вариант с AI', iconName: 'sparkles', narrow: true, body: h('div', { class: 'stack' }, h('p', { class: 'muted' }, 'Въпросът ще бъде заменен с нов от същия тип, тема и трудност.'), h('label', { class: 'field' }, 'Указания (по желание)', instr)), footer: [h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Отказ'), h('button', { class: 'btn primary', onClick: async e => { e.target.disabled = true; e.target.innerHTML = '<span class="spinner"></span>'; try { await api('POST', `/api/questions/${q.id}/regenerate`, { instructions: instr.value }); m.close(); toast('Готово', 'success'); load(); } catch (err) { toast(err.message, 'error'); m.close(); } } }, 'Генерирай')] });
  }
  async function generate(sectionKey) {
    if (busy) return; busy = true; render();
    try {
      const r = await api('POST', `/api/tests/${testId}/generate`, { section_key: sectionKey || null });
      let added = 0; const errors = [];
      for (const x of r.results) { added += x.added.length; if (x.error) errors.push(x.error); }
      if (added) toast(`Генерирани ${added} въпроса${r.mode === 'mock' ? ' (демо режим)' : ''}`, 'success');
      errors.forEach(e => toast(e, 'error', 6000));
      if (!added && !errors.length) toast('Контейнерите вече са запълнени.');
    } catch (e) { toast(e.message, 'error', 6000); }
    busy = false; await load();
  }
  async function fillFromBank(sectionKey) {
    try { const r = await api('POST', `/api/tests/${testId}/fill-from-bank`, { section_key: sectionKey }); toast(r.message || `Добавени ${r.added.length} въпроса от банката`, r.message ? '' : 'success'); } catch (e) { toast(e.message, 'error'); }
    load();
  }
  function editSection(s, onDone) {
    const f = Sections.sectionForm(s, { curriculumId: test.curriculum_id, aiMode });
    const m = modal({ title: s ? 'Настройки на контейнера' : 'Нов контейнер', iconName: 'box', wide: true, body: f.el, footer: [h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Отказ'), h('button', { class: 'btn primary', onClick: () => { m.close(); onDone(f.collect()); } }, 'Запази')] });
  }
  async function saveSections(sections) { test = await api('PATCH', `/api/tests/${testId}`, { title: test.title, description: test.description, curriculum_id: test.curriculum_id, sections }); render(); }

  function pickFromBank(sectionKey) {
    const list = h('div'); const chosen = new Set(); const q = h('input', { type: 'search', placeholder: 'Търсене…' });
    const typeSel = h('select', {}, h('option', { value: '' }, 'Всички типове'), ...Object.entries(Editor.TYPE_META).map(([k, m]) => h('option', { value: k }, m.label)));
    const usedIds = new Set(test.questions.map(x => x.source_question_id).filter(Boolean));
    async function draw() { const p = new URLSearchParams(); if (q.value) p.set('q', q.value); if (typeSel.value) p.set('type', typeSel.value); if (test.curriculum_id) p.set('curriculum_id', test.curriculum_id); const items = await api('GET', '/api/bank?' + p); list.innerHTML = ''; if (!items.length) list.append(h('p', { class: 'muted' }, 'Няма въпроси в банката по тези критерии.')); for (const it of items) { const cb = h('input', { type: 'checkbox', checked: chosen.has(it.id) || null }); cb.addEventListener('change', () => cb.checked ? chosen.add(it.id) : chosen.delete(it.id)); list.append(h('label', { class: 'q-item', style: { cursor: 'pointer' } }, cb, h('div', { class: 'q-item-body' }, App.htmlBlock(it.stem, 'q-item-stem'), h('div', { class: 'q-item-meta' }, h('span', {}, Editor.TYPE_META[it.type]?.label), App.diffBadge(it.difficulty), it.topic ? h('span', {}, it.topic) : null, usedIds.has(it.id) ? h('span', { class: 'badge' }, 'вече в теста') : null)))); } icons(list); renderMath(list); }
    q.addEventListener('input', debounce(draw, 300)); typeSel.addEventListener('change', draw); draw();
    const m = modal({ title: 'Добавяне от банката с въпроси', iconName: 'library', wide: true, body: h('div', { class: 'stack' }, h('div', { class: 'toolbar' }, h('div', { class: 'search grow' }, icon('search'), q), typeSel), list), footer: [h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Отказ'), h('button', { class: 'btn primary', onClick: async () => { if (!chosen.size) return toast('Изберете въпроси'); await api('POST', `/api/tests/${testId}/questions/from-bank`, { question_ids: [...chosen], section_key: sectionKey }); m.close(); toast(`Добавени ${chosen.size} въпроса`, 'success'); load(); } }, 'Добави избраните')] });
  }
  function addQuestionMenu(sectionKey) {
    const grid = h('div', { class: 'type-grid' });
    const m = modal({ title: 'Нов въпрос – изберете тип', iconName: 'plus', wide: true, body: grid });
    for (const [k, meta] of Object.entries(Editor.TYPE_META)) grid.append(h('button', { type: 'button', class: 'type-card', onClick: () => { m.close(); Editor.open({ type: k, testId, sectionKey, curriculumId: test.curriculum_id, onSave: load }); } }, icon(meta.icon), h('div', {}, h('div', { class: 'tc-label' }, meta.label), h('div', { class: 'tc-sub' }, meta.auto ? 'автоматична проверка' : 'ръчна проверка'))));
    icons(grid);
  }

  function render() {
    root.innerHTML = '';
    const title = h('input', { type: 'text', value: test.title, style: { fontSize: '1.2rem', fontWeight: 700 } }); title.addEventListener('input', () => { test.title = title.value; saveMeta({}); });
    const desc = h('textarea', { rows: 2, placeholder: 'Описание / указания за учениците' }, test.description || ''); desc.addEventListener('input', () => { test.description = desc.value; saveMeta({}); });
    const curTpl = document.getElementById('curriculumOptions'); const cur = curTpl.cloneNode(true); cur.id = ''; cur.classList.remove('hidden'); cur.value = test.curriculum_id || ''; cur.addEventListener('change', () => { test.curriculum_id = cur.value ? Number(cur.value) : null; saveMeta({}); setTimeout(load, 700); });
    const totalPts = test.questions.reduce((a, q) => a + q.points, 0);
    const aiSections = test.sections.filter(s => s.source === 'ai' && s.type);
    const side = h('div', { class: 'builder-side' },
      h('div', { class: 'card' }, h('div', { class: 'stack' }, h('label', { class: 'field' }, 'Заглавие', title), h('label', { class: 'field' }, 'Описание', desc), h('label', { class: 'field' }, 'Учебна програма', cur), h('div', { class: 'row gap wrap' }, h('span', { class: 'badge primary' }, `${test.questions.length} въпроса`), h('span', { class: 'badge' }, `${totalPts} т.`), test.assignment_count ? h('span', { class: 'badge warning', title: 'Промените засягат вече възложените задания' }, icon('send'), `възложен ×${test.assignment_count}`) : null))),
      h('div', { class: 'card' }, h('div', { class: 'card-head' }, h('h3', {}, icon('boxes'), 'Контейнери'), h('button', { class: 'btn sm ghost', onClick: () => editSection(null, v => saveSections([...test.sections, v])) }, icon('plus'))),
        h('div', { id: 'sectionCards' }, ...test.sections.map((s, i) => { const c = Sections.sectionSummary(s); c.draggable = true; c.addEventListener('dragstart', e => { e.dataTransfer.setData('text/plain', 's:' + i); c.classList.add('dragging'); }); c.addEventListener('dragend', () => c.classList.remove('dragging')); c.addEventListener('dragover', e => e.preventDefault()); c.addEventListener('drop', e => { e.preventDefault(); const d = e.dataTransfer.getData('text/plain'); if (!d.startsWith('s:')) return; const from = Number(d.slice(2)); if (from === i) return; const arr = test.sections.slice(); const [x] = arr.splice(from, 1); arr.splice(i, 0, x); saveSections(arr).then(() => { const ordered = []; for (const sec of arr) ordered.push(...test.questions.filter(q => q.section_key === sec.key)); api('POST', `/api/tests/${testId}/reorder`, { order: ordered.map(q => ({ id: q.id, section_key: q.section_key })) }).then(load); }); });
          c.querySelector('.sc-head').append(h('button', { class: 'icon-btn sm', title: 'Настройки', onClick: () => editSection(s, v => { const arr = test.sections.slice(); arr[i] = v; saveSections(arr); }) }, icon('settings-2')), h('button', { class: 'icon-btn sm danger', title: 'Изтрий контейнера (въпросите се преместват в първия)', disabled: test.sections.length <= 1 || null, onClick: async () => { if (await confirmDialog('Изтриване на контейнера? Въпросите му ще се преместят в първия контейнер.', { danger: true, okText: 'Изтрий' })) saveSections(test.sections.filter((_, j) => j !== i)); } }, icon('x'))); return c; })),
        aiMode !== 'off' && aiSections.length ? h('button', { class: 'btn primary block mt-s', disabled: busy || null, onClick: () => generate(null) }, busy ? h('span', { class: 'spinner' }) : icon('sparkles'), busy ? ' Генериране…' : ' Генерирай всички AI контейнери') : null,
        aiMode === 'off' ? h('p', { class: 'subtle mt-s' }, 'AI генерирането изисква GEMINI_API_KEY.') : null));
    const main = h('div');
    let n = 0;
    for (const s of test.sections) {
      const qs = test.questions.filter(q => q.section_key === s.key); const meta = Sections.TYPE_META[s.type] || {};
      const block = h('div', { class: 'section-block', dataset: { key: s.key } });
      block.addEventListener('dragover', e => { if ((e.dataTransfer.types || []).includes('text/plain')) { e.preventDefault(); block.classList.add('over'); } });
      block.addEventListener('dragleave', e => { if (!block.contains(e.relatedTarget)) block.classList.remove('over'); });
      block.addEventListener('drop', e => { block.classList.remove('over'); const d = e.dataTransfer.getData('text/plain'); if (d.startsWith('q:')) { e.preventDefault(); moveQuestion(Number(d.slice(2)), s.key, null); } });
      const missing = Math.max(0, (s.count || 0) - qs.length);
      block.append(h('div', { class: 'sb-head' }, h('h3', {}, s.title), h('span', { class: 'badge' }, `${qs.length}${s.count ? ' / ' + s.count : ''} въпроса`), s.type ? h('span', { class: 'badge primary' }, icon(meta.icon), meta.label) : null,
        h('div', { class: 'actions' },
          s.source === 'ai' && s.type && aiMode !== 'off' && missing ? h('button', { class: 'btn sm soft', disabled: busy || null, onClick: () => generate(s.key) }, icon('sparkles'), `Генерирай ${missing} с AI`) : null,
          s.source === 'bank' && s.type && missing ? h('button', { class: 'btn sm soft', onClick: () => fillFromBank(s.key) }, icon('shuffle'), `Попълни ${missing} от банката`) : null,
          h('button', { class: 'btn sm', onClick: () => pickFromBank(s.key) }, icon('library'), 'От банката'),
          h('button', { class: 'btn sm primary', onClick: () => addQuestionMenu(s.key) }, icon('plus'), 'Въпрос'))));
      if (!qs.length) block.append(h('div', { class: 'section-drop' }, 'Няма въпроси в този контейнер. Добавете ръчно, от банката или с AI; може и да плъзнете въпрос тук.'));
      for (const q of qs) block.append(qItem(q, ++n));
      main.append(block);
    }
    const orphan = test.questions.filter(q => !test.sections.find(s => s.key === q.section_key));
    if (orphan.length) { const block = h('div', { class: 'section-block' }, h('div', { class: 'sb-head' }, h('h3', {}, 'Други'))); for (const q of orphan) block.append(qItem(q, ++n)); main.append(block); }
    root.append(h('div', { class: 'builder' }, side, main)); icons(root); renderMath(root);
  }

  document.addEventListener('DOMContentLoaded', async () => {
    await load();
    const p = new URLSearchParams(location.search);
    if (p.get('generate') === '1') { history.replaceState(null, '', location.pathname); generate(null); }
    else if (p.get('fill') === '1') { history.replaceState(null, '', location.pathname); for (const s of test.sections.filter(x => x.source === 'bank')) await fillFromBank(s.key); }
  });
})();
