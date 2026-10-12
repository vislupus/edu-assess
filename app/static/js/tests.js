/* Списък с тестове. */
(function () {
  const { h, icon, icons, api, toast, confirmDialog, fmtDate } = App;
  async function init() {
    const root = document.getElementById('testList'); if (!root) return;
    const list = await api('GET', '/api/tests'); root.innerHTML = '';
    if (!list.length) { root.append(h('div', { class: 'card empty' }, icon('file-text'), h('h3', {}, 'Нямате тестове'), h('p', {}, 'Създайте първия си тест.'), h('a', { class: 'btn primary', href: '/tests/new' }, icon('plus'), 'Нов тест'))); icons(root); return; }
    const tbl = h('table', { class: 'table' }, h('thead', {}, h('tr', {}, h('th', {}, 'Тест'), h('th', {}, 'Предмет'), h('th', { class: 'num' }, 'Въпроси'), h('th', { class: 'num' }, 'Точки'), h('th', {}, 'Статус'), h('th', {}, 'Променен'), h('th'))));
    const tb = h('tbody'); tbl.append(tb);
    for (const t of list) {
      tb.append(h('tr', {},
        h('td', {}, h('a', { href: `/tests/${t.id}/edit` }, h('strong', {}, t.title)), t.description ? h('div', { class: 'subtle' }, t.description.slice(0, 90)) : null),
        h('td', {}, t.subject || '–', t.grade_label ? h('div', { class: 'subtle' }, t.grade_label) : null),
        h('td', { class: 'num' }, t.question_count), h('td', { class: 'num' }, t.total_points),
        h('td', {}, t.assignment_count ? h('span', { class: 'badge success' }, icon('send'), `възложен ×${t.assignment_count}`) : t.status === 'ready' ? h('span', { class: 'badge primary' }, 'Готов') : h('span', { class: 'badge' }, 'Чернова')),
        h('td', { class: 'subtle' }, fmtDate(t.updated_at)),
        h('td', { class: 'actions' },
          h('a', { class: 'icon-btn', href: `/tests/${t.id}/edit`, title: 'Редакция' }, icon('pencil')),
          h('a', { class: 'icon-btn', href: `/tests/${t.id}/assign`, title: 'Възложи' }, icon('send')),
          h('a', { class: 'icon-btn', href: `/tests/${t.id}/print`, target: '_blank', title: 'Печат' }, icon('printer')),
          h('button', { class: 'icon-btn', title: 'Дублирай', onClick: async () => { await api('POST', `/api/tests/${t.id}/duplicate`); toast('Създадено копие', 'success'); init(); } }, icon('copy')),
          h('button', { class: 'icon-btn danger', title: 'Изтрий', onClick: async () => { if (!await confirmDialog(`Изтриване на „${t.title}“?`, { danger: true, okText: 'Изтрий' })) return; try { await api('DELETE', `/api/tests/${t.id}`); init(); } catch (e) { toast(e.message, 'error'); } } }, icon('trash-2')))));
    }
    root.append(h('div', { class: 'card pad-0 table-wrap' }, tbl)); icons(root);
  }
  document.addEventListener('DOMContentLoaded', init);
})();
