/* Банка с въпроси: филтри, списък, редакция. */
(function () {
  const { h, icon, icons, api, toast, confirmDialog, renderMath, debounce } = App;
  const root = document.getElementById('bankList'); if (!root) return;
  const f = { q: document.getElementById('fQ'), cur: document.getElementById('fCur'), type: document.getElementById('fType'), diff: document.getElementById('fDiff') };

  function item(q) {
    const meta = Editor.TYPE_META[q.type] || {};
    return h('div', { class: 'q-item' },
      h('span', { class: 'badge primary', title: meta.label }, icon(meta.icon || 'help-circle')),
      h('div', { class: 'q-item-body' }, App.htmlBlock(q.stem || '<em>(без условие)</em>', 'q-item-stem'), h('div', { class: 'q-item-meta' }, h('span', {}, meta.label || q.type), App.diffBadge(q.difficulty), h('span', {}, `${q.points} т.`), q.topic ? h('span', {}, icon('tag'), ' ', q.topic) : null, q.source === 'ai' ? h('span', { class: 'badge' }, icon('sparkles'), 'AI') : null)),
      h('div', { class: 'q-item-actions' }, h('button', { class: 'icon-btn', title: 'Преглед', onClick: () => Editor.preview(q) }, icon('eye')), h('button', { class: 'icon-btn', title: 'Редакция', onClick: () => Editor.open({ question: q, onSave: load }) }, icon('pencil')), h('button', { class: 'icon-btn', title: 'Дублирай', onClick: async () => { await api('POST', `/api/questions/${q.id}/duplicate`); load(); } }, icon('copy')), h('button', { class: 'icon-btn danger', title: 'Изтрий', onClick: async () => { if (await confirmDialog('Изтриване на въпроса от банката?', { danger: true, okText: 'Изтрий' })) { await api('DELETE', `/api/questions/${q.id}`); load(); } } }, icon('trash-2'))));
  }
  async function load() {
    const p = new URLSearchParams(); if (f.q.value) p.set('q', f.q.value); if (f.cur.value) p.set('curriculum_id', f.cur.value); if (f.type.value) p.set('type', f.type.value); if (f.diff.value) p.set('difficulty', f.diff.value);
    const list = await api('GET', '/api/bank?' + p.toString()); root.innerHTML = ''; document.getElementById('bankCount').textContent = `${list.length} въпроса`;
    if (!list.length) { root.append(h('div', { class: 'card empty' }, icon('library'), h('h3', {}, 'Няма въпроси'), h('p', {}, 'Добавете нов въпрос или променете филтрите.'))); icons(root); return; }
    list.forEach(q => root.append(item(q))); icons(root); renderMath(root);
  }
  document.getElementById('newQuestionBtn').addEventListener('click', () => Editor.open({ curriculumId: f.cur.value ? Number(f.cur.value) : null, onSave: load }));
  f.q.addEventListener('input', debounce(load, 300)); [f.cur, f.type, f.diff].forEach(el => el.addEventListener('change', load));
  document.addEventListener('DOMContentLoaded', load);
})();
