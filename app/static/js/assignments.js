/* Списък със задания. */
(function () {
  const { h, icon, icons, api, toast, confirmDialog, fmtDate } = App;
  async function init() {
    const root = document.getElementById('assignmentList'); if (!root) return;
    const list = await api('GET', '/api/assignments'); root.innerHTML = '';
    if (!list.length) { root.append(h('div', { class: 'card empty' }, icon('send'), h('h3', {}, 'Няма задания'), h('p', {}, 'Отворете тест и го възложете на клас.'))); icons(root); return; }
    const tbl = h('table', { class: 'table' }, h('thead', {}, h('tr', {}, h('th', {}, 'Задание'), h('th', {}, 'Класове'), h('th', {}, 'Период'), h('th', { class: 'num' }, 'Предадени'), h('th', {}, 'Статус'), h('th'))));
    const tb = h('tbody'); tbl.append(tb);
    for (const a of list) {
      tb.append(h('tr', {},
        h('td', {}, h('a', { href: `/assignments/${a.id}` }, h('strong', {}, a.title)), ' ', a.mode === 'exam' ? h('span', { class: 'badge danger' }, icon('shield-alert'), 'Изпит') : h('span', { class: 'badge primary' }, 'Упражнение'), a.needs_manual ? h('div', {}, h('span', { class: 'badge warning' }, `${a.needs_manual} за проверка`)) : null),
        h('td', {}, a.classrooms.map(c => c.name).join(', ')),
        h('td', { class: 'subtle' }, `${fmtDate(a.start_at)} – ${a.end_at ? fmtDate(a.end_at) : 'безсрочно'}`, a.time_limit_min ? h('div', {}, `${a.time_limit_min} мин`) : null),
        h('td', { class: 'num' }, `${a.submitted}`, a.in_progress ? h('span', { class: 'subtle' }, ` (+${a.in_progress} в процес)`) : null),
        h('td', {}, a.status === 'closed' ? h('span', { class: 'badge' }, 'Затворено') : a.is_open ? h('span', { class: 'badge success' }, 'Активно') : h('span', { class: 'badge warning' }, 'Извън период')),
        h('td', { class: 'actions' }, h('a', { class: 'btn sm', href: `/assignments/${a.id}` }, icon('chart-no-axes-column'), 'Резултати'),
          a.status === 'active' ? h('button', { class: 'icon-btn', title: 'Затвори заданието', onClick: async () => { if (!await confirmDialog('Затваряне на заданието? Учениците няма да могат да го решават повече.', { okText: 'Затвори' })) return; await api('PATCH', `/api/assignments/${a.id}`, { status: 'closed' }); init(); } }, icon('lock')) : h('button', { class: 'icon-btn', title: 'Отвори отново', onClick: async () => { await api('PATCH', `/api/assignments/${a.id}`, { status: 'active' }); init(); } }, icon('unlock')),
          h('button', { class: 'icon-btn danger', title: 'Изтрий', onClick: async () => { if (!await confirmDialog('Изтриване на заданието и всички резултати по него?', { danger: true, okText: 'Изтрий' })) return; await api('DELETE', `/api/assignments/${a.id}`); init(); } }, icon('trash-2')))));
    }
    root.append(h('div', { class: 'card pad-0 table-wrap' }, tbl)); icons(root);
  }
  document.addEventListener('DOMContentLoaded', init);
})();
