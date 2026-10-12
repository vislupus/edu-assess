/* Резултати по задание: обобщение, таблица по ученици, анализ по въпроси. */
(function () {
  const { h, icon, icons, api, toast, confirmDialog, fmtDate } = App;
  const root = document.getElementById('results'); if (!root) return;
  const aid = Number(root.dataset.assignment);

  function statusBadge(r) {
    if (r.status === 'submitted') return r.best && r.best.needs_manual ? h('span', { class: 'badge warning' }, 'Чака проверка') : h('span', { class: 'badge success' }, 'Предаден');
    if (r.status === 'annulled') return h('span', { class: 'badge danger' }, icon('ban'), 'Анулиран');
    if (r.status === 'in_progress') return h('span', { class: 'badge warning' }, icon('loader'), 'В процес');
    return h('span', { class: 'badge' }, 'Незапочнал');
  }

  async function init() {
    let d; try { d = await api('GET', `/api/assignments/${aid}/results`); } catch (e) { root.innerHTML = ''; root.append(h('div', { class: 'card empty' }, e.message)); return; }
    const a = d.assignment, s = d.summary; root.innerHTML = '';
    root.append(h('div', { class: 'page-head' }, h('div', {}, h('h1', {}, icon('chart-no-axes-column'), a.title), h('p', { class: 'muted' }, a.mode === 'exam' ? h('span', { class: 'badge danger' }, 'Изпит') : h('span', { class: 'badge primary' }, 'Упражнение'), ' ', a.is_open ? h('span', { class: 'badge success' }, 'Активно') : h('span', { class: 'badge' }, 'Неактивно'), ` · ${a.classrooms.map(c => c.name).join(', ')} · от ${fmtDate(a.start_at)}${a.end_at ? ' до ' + fmtDate(a.end_at) : ''}${a.time_limit_min ? ' · ' + a.time_limit_min + ' мин' : ''}`)),
      h('div', { class: 'actions' }, h('a', { class: 'btn', href: `/tests/${a.test_id}/edit` }, icon('file-text'), 'Тестът'), a.status === 'active' ? h('button', { class: 'btn', onClick: async () => { if (await confirmDialog('Затваряне на заданието?', { okText: 'Затвори' })) { await api('PATCH', `/api/assignments/${aid}`, { status: 'closed' }); init(); } } }, icon('lock'), 'Затвори') : h('button', { class: 'btn', onClick: async () => { await api('PATCH', `/api/assignments/${aid}`, { status: 'active' }); init(); } }, icon('unlock'), 'Отвори'))));
    root.append(h('div', { class: 'grid cols-4 mb' },
      h('div', { class: 'card stat' }, h('span', { class: 'label' }, 'Предадени'), h('span', { class: 'value' }, `${s.submitted} `, h('small', {}, `/ ${s.total}`))),
      h('div', { class: 'card stat warning' }, h('span', { class: 'label' }, 'В процес / незапочнали'), h('span', { class: 'value' }, `${s.in_progress} `, h('small', {}, `/ ${s.not_started}`))),
      h('div', { class: 'card stat success' }, h('span', { class: 'label' }, 'Среден успех'), h('span', { class: 'value' }, s.avg_percent !== null ? `${s.avg_percent}%` : '–')),
      h('div', { class: 'card stat primary' }, h('span', { class: 'label' }, 'Средна оценка'), h('span', { class: 'value' }, s.avg_grade !== null ? `${s.avg_grade_label}` : '–'))));
    // Разпределение и анализ по въпроси
    const maxD = Math.max(1, ...Object.values(s.grade_distribution));
    const dist = h('div', { class: 'dist' }, ...[2, 3, 4, 5, 6].map(g => h('div', { class: 'col' }, h('span', { class: 'val' }, s.grade_distribution[g] || 0), h('i', { style: { height: `${(s.grade_distribution[g] || 0) / maxD * 80}%`, background: g <= 2 ? 'var(--danger-strong)' : g === 3 ? 'var(--warning)' : g === 4 ? '#2563eb' : 'var(--success)' } }), h('span', { class: 'lab' }, g))));
    const pq = h('div', { class: 'hbar-list' });
    for (const q of d.per_question) { const cls = q.avg_percent >= 75 ? 'success' : q.avg_percent >= 50 ? 'warning' : 'danger'; pq.append(h('div', { class: 'hbar', title: `${q.type_label}${q.topic ? ' · ' + q.topic : ''}` }, h('strong', {}, `${q.n}.`), h('div', { class: `bar ${cls}` }, h('i', { style: { width: `${q.avg_percent}%` } })), h('span', { class: `pct ${App.pctClass(q.avg_percent)}` }, `${q.avg_percent}%`))); }
    const hardest = d.per_question.filter(q => q.answered).sort((x, y) => x.avg_percent - y.avg_percent).slice(0, 3);
    root.append(h('div', { class: 'grid cols-3 mb' },
      h('div', { class: 'card' }, h('div', { class: 'card-head' }, h('h3', {}, icon('bar-chart-3'), 'Разпределение на оценките')), dist),
      h('div', { class: 'card', style: { gridColumn: 'span 2' } }, h('div', { class: 'card-head' }, h('h3', {}, icon('target'), 'Успеваемост по въпроси'), hardest.length ? h('span', { class: 'subtle' }, 'най-трудни: ' + hardest.map(q => `№${q.n} (${q.avg_percent}%)`).join(', ')) : null), d.per_question.length ? pq : h('p', { class: 'muted' }, 'Още няма предадени решения.'))));
    // Таблица
    const tbl = h('table', { class: 'table' }, h('thead', {}, h('tr', {}, h('th', {}, '№'), h('th', {}, 'Ученик'), h('th', {}, 'Статус'), h('th', { class: 'num' }, 'Вариант'), h('th', { class: 'num' }, 'Успех'), h('th', {}, 'Оценка'), h('th', { class: 'num' }, 'Точки'), h('th', { class: 'num' }, 'Предупр.'), h('th', {}, 'Предаден'), h('th'))));
    const tb = h('tbody'); tbl.append(tb);
    d.rows.forEach((r, i) => {
      const b = r.best;
      tb.append(h('tr', {}, h('td', { class: 'subtle' }, i + 1), h('td', {}, h('div', { class: 'row gap' }, h('span', { class: 'avatar sm', style: { '--c': r.student.avatar_color } }, r.student.initials), h('span', {}, r.student.full_name), r.attempts.length > 1 ? h('span', { class: 'badge' }, `${r.attempts.length} опита`) : null)),
        h('td', {}, statusBadge(r)), h('td', { class: 'num' }, b ? b.variant : r.current ? r.current.variant : '–'),
        h('td', { class: 'num' }, b && b.status === 'submitted' ? h('span', { class: `pct ${App.pctClass(b.percent)}` }, `${b.percent}%`) : '–'), h('td', {}, b ? b.grade_label : '–'),
        h('td', { class: 'num' }, b ? `${b.score} / ${b.max_score}` : '–'), h('td', { class: 'num' }, (b && b.warnings) || (r.current && r.current.warnings) ? h('span', { class: 'badge danger' }, (b || r.current).warnings) : '–'),
        h('td', { class: 'subtle' }, b ? fmtDate(b.submitted_at) : '–'),
        h('td', { class: 'actions' }, b ? h('a', { class: 'btn sm primary', href: `/attempts/${b.id}/review` }, icon(b.needs_manual ? 'pen-line' : 'eye'), b.needs_manual ? 'Провери' : 'Решение') : null,
          (b || r.current) ? h('button', { class: 'icon-btn danger', title: 'Нулирай опита (ученикът ще може да реши отново)', onClick: async () => { if (!await confirmDialog(`Изтриване на опита на ${r.student.full_name}?`, { danger: true, okText: 'Изтрий' })) return; await api('POST', `/api/attempts/${(b || r.current).id}/reopen`); init(); } }, icon('rotate-ccw')) : null)));
    });
    root.append(h('div', { class: 'card pad-0 table-wrap' }, tbl)); icons(root);
  }
  document.addEventListener('DOMContentLoaded', init);
})();
