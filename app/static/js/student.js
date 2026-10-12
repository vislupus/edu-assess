/* Ученик: табло със задания и списък с резултати. */
(function () {
  const { h, icon, icons, api, toast, fmtDate, confirmDialog } = App;

  function statusBadge(a) {
    if (a.current) return h('span', { class: 'badge warning' }, icon('loader'), 'В процес');
    if (a.best) return a.best.status === 'annulled' ? h('span', { class: 'badge danger' }, icon('ban'), 'Анулиран') : h('span', { class: 'badge success' }, icon('check'), 'Предаден');
    if (!a.is_open) return h('span', { class: 'badge' }, icon('clock'), a.status === 'closed' ? 'Затворен' : (new Date(a.start_at) > new Date() ? 'Предстои' : 'Изтекъл'));
    return h('span', { class: 'badge info' }, icon('circle'), 'Незапочнат');
  }

  async function start(a) {
    if (a.mode === 'exam') {
      const ok = await confirmDialog(`Това е изпит в строг режим${a.time_limit_min ? ` с ограничение ${a.time_limit_min} мин` : ''}. По време на решаването не може да напускате страницата. Започвате ли?`, { okText: 'Започни изпита', title: 'Изпитен режим' });
      if (!ok) return;
    }
    try { const at = await api('POST', `/api/assignments/${a.id}/start`); location.href = `/attempts/${at.id}`; }
    catch (e) { toast(e.message, 'error'); }
  }

  function card(a) {
    const meta = [a.subject, a.teacher, `${a.question_count} въпроса`];
    if (a.time_limit_min) meta.push(`${a.time_limit_min} мин`);
    if (a.end_at) meta.push(`до ${fmtDate(a.end_at)}`);
    if (a.attempts_allowed) meta.push(`опити: ${a.attempts_used}/${a.attempts_allowed}`);
    const actions = h('div', { class: 'btn-group' });
    if (a.can_resume) actions.append(h('a', { class: 'btn primary', href: `/attempts/${a.current.id}` }, icon('play'), 'Продължи'));
    else if (a.can_start) actions.append(h('button', { class: 'btn primary', onClick: () => start(a) }, icon(a.mode === 'exam' ? 'shield-check' : 'play'), a.best ? 'Нов опит' : 'Започни'));
    if (a.best && a.results_visible) actions.append(h('a', { class: 'btn', href: `/attempts/${a.best.id}/review` }, icon('eye'), 'Резултат'));
    const el = h('div', { class: 'card' },
      h('div', { class: 'row gap wrap between' },
        h('div', { class: 'grow' },
          h('div', { class: 'row gap wrap' }, h('h3', { style: { margin: 0 } }, a.title), a.mode === 'exam' ? h('span', { class: 'badge danger' }, icon('shield-alert'), 'Изпит') : h('span', { class: 'badge primary' }, icon('pencil-line'), 'Упражнение'), statusBadge(a)),
          h('div', { class: 'subtle mt-s' }, meta.join(' · ')),
          a.best ? h('div', { class: 'mt-s row gap' }, h('span', { class: `pct ${App.pctClass(a.best.percent)}` }, a.results_visible ? `${a.best.percent}%` : ''), a.results_visible ? h('span', { class: 'badge' }, a.best.grade_label) : h('span', { class: 'subtle' }, 'Резултатът ще бъде публикуван от учителя.')) : null,
        ),
        actions));
    return el;
  }

  async function home() {
    const root = document.getElementById('studentHome'); if (!root) return;
    try {
      const list = await api('GET', '/api/my/assignments');
      root.innerHTML = '';
      if (!list.length) { root.append(h('div', { class: 'card empty' }, icon('inbox'), h('h3', {}, 'Нямаш задания'), h('p', {}, 'Когато учител ти възложи тест, той ще се появи тук.'))); icons(root); return; }
      const active = list.filter(a => a.can_start || a.can_resume), rest = list.filter(a => !(a.can_start || a.can_resume));
      if (active.length) { root.append(h('h2', { class: 'mb-s' }, 'Активни'), h('div', { class: 'stack mb' }, ...active.map(card))); }
      if (rest.length) { root.append(h('h2', { class: 'mb-s' }, 'Приключени и предстоящи'), h('div', { class: 'stack' }, ...rest.map(card))); }
      icons(root);
    } catch (e) { root.innerHTML = ''; root.append(h('div', { class: 'card empty' }, e.message)); }
  }

  async function results() {
    const root = document.getElementById('studentResults'); if (!root) return;
    try {
      const list = await api('GET', '/api/my/attempts');
      root.innerHTML = '';
      if (!list.length) { root.append(h('div', { class: 'card empty' }, icon('chart-no-axes-column'), h('h3', {}, 'Още няма резултати'))); icons(root); return; }
      const vis = list.filter(x => x.results_visible && x.status !== 'annulled');
      if (vis.length) {
        const avg = vis.reduce((s, x) => s + x.percent, 0) / vis.length;
        root.append(h('div', { class: 'grid cols-3 mb' },
          h('div', { class: 'card stat' }, h('span', { class: 'label' }, 'Решени тестове'), h('span', { class: 'value' }, list.length)),
          h('div', { class: 'card stat success' }, h('span', { class: 'label' }, 'Среден успех'), h('span', { class: 'value' }, `${avg.toFixed(0)}%`)),
          h('div', { class: 'card stat primary' }, h('span', { class: 'label' }, 'Най-добър резултат'), h('span', { class: 'value' }, `${Math.max(...vis.map(x => x.percent))}%`))));
      }
      const tbl = h('table', { class: 'table' }, h('thead', {}, h('tr', {}, h('th', {}, 'Тест'), h('th', {}, 'Предмет'), h('th', {}, 'Дата'), h('th', {}, 'Статус'), h('th', { class: 'num' }, 'Успех'), h('th', {}, 'Оценка'), h('th'))));
      const tb = h('tbody'); tbl.append(tb);
      for (const x of list) {
        const vis = x.results_visible;
        tb.append(h('tr', {}, h('td', {}, h('strong', {}, x.assignment.title), ' ', x.assignment.mode === 'exam' ? h('span', { class: 'badge danger' }, 'Изпит') : null), h('td', {}, x.assignment.subject || ''), h('td', {}, fmtDate(x.submitted_at)),
          h('td', {}, x.status === 'annulled' ? h('span', { class: 'badge danger' }, 'Анулиран') : x.needs_manual ? h('span', { class: 'badge warning' }, 'Чака проверка') : h('span', { class: 'badge success' }, 'Оценен')),
          h('td', { class: 'num' }, vis ? h('span', { class: `pct ${App.pctClass(x.percent)}` }, `${x.percent}%`) : '–'), h('td', {}, vis ? x.grade_label : '–'),
          h('td', { class: 'actions' }, vis ? h('a', { class: 'btn sm', href: `/attempts/${x.id}/review` }, icon('eye'), 'Преглед') : h('span', { class: 'subtle' }, 'скрит'))));
      }
      root.append(h('div', { class: 'card pad-0 table-wrap' }, tbl)); icons(root);
    } catch (e) { root.innerHTML = ''; root.append(h('div', { class: 'card empty' }, e.message)); }
  }

  document.addEventListener('DOMContentLoaded', () => { home(); results(); });
})();
