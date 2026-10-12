/* Преглед на решение (ученик) и ръчно оценяване (учител). */
(function () {
  const { h, icon, icons, api, toast, fmtDate, renderMath } = App;
  const root = document.getElementById('review');
  const attemptId = Number(root.dataset.attempt); const teacher = root.dataset.teacher === '1';
  const manual = {};

  function gradeInput(q) {
    const inp = h('input', { type: 'number', min: 0, max: q.points, step: 0.25, value: q.manual_score ?? '' , class: 'sm' });
    const fb = h('input', { type: 'text', placeholder: 'Коментар към ученика', value: q.feedback || '', class: 'sm', style: { minWidth: '240px' } });
    const upd = () => { manual[q.id] = { manual_score: inp.value === '' ? null : Number(inp.value), feedback: fb.value }; };
    inp.addEventListener('input', upd); fb.addEventListener('input', upd);
    return h('div', { class: 'q-feedback', style: { background: 'var(--surface-2)', color: 'var(--text)' } }, h('div', { class: 'row gap wrap' }, h('strong', {}, 'Оценяване:'), h('span', { class: 'grade-input' }, inp, h('span', { class: 'muted' }, `/ ${q.points} т.`)), fb, q.auto !== false && q.needs_manual ? null : h('span', { class: 'subtle' }, `авт.: ${q.auto_score ?? 0} т.`)));
  }

  async function save() {
    try { const r = await api('POST', `/api/attempts/${attemptId}/grade`, { answers: Object.fromEntries(Object.entries(manual).map(([k, v]) => [k, v])), feedback: document.getElementById('overallFb').value });
      toast('Оценката е записана', 'success'); setTimeout(() => location.reload(), 500); }
    catch (e) { toast(e.message, 'error'); }
  }

  async function init() {
    let d;
    try { d = await api('GET', `/api/attempts/${attemptId}/review`); }
    catch (e) { root.innerHTML = ''; root.append(h('div', { class: 'card empty' }, icon('lock'), h('h3', {}, e.message))); icons(root); return; }
    const at = d.attempt; root.innerHTML = '';
    const head = h('div', { class: 'card mb' }, h('div', { class: 'row gap wrap between' },
      h('div', {}, h('div', { class: 'row gap' }, h('span', { class: 'avatar', style: { '--c': d.student.avatar_color } }, d.student.initials), h('div', {}, h('h2', { style: { margin: 0 } }, d.student.full_name), h('div', { class: 'subtle' }, `${d.assignment.title} · опит ${at.attempt_no} · вариант ${at.variant} · предаден ${fmtDate(at.submitted_at)}`))),
        at.status === 'annulled' ? h('p', { class: 'badge danger mt-s' }, icon('ban'), 'Анулиран след превишен брой предупреждения') : null),
      h('div', { class: 'row gap' }, h('div', { class: 'stat' }, h('span', { class: 'label' }, 'Точки'), h('span', { class: 'value' }, `${at.score} `, h('small', {}, `/ ${at.max_score}`))), h('div', { class: 'stat' }, h('span', { class: 'label' }, 'Успех'), h('span', { class: `value ${App.pctClass(at.percent) === 'good' ? '' : ''}` }, `${at.percent}%`)), h('div', { class: 'stat primary' }, h('span', { class: 'label' }, 'Оценка'), h('span', { class: 'value' }, at.grade_label)))));
    if (at.needs_manual) head.append(h('p', { class: 'badge warning mt-s' }, icon('clock'), teacher ? 'Има отговори, които чакат ръчна проверка' : 'Част от отговорите чакат проверка от учителя – оценката може да се промени.'));
    if (at.teacher_feedback && !teacher) head.append(h('div', { class: 'q-feedback mt-s' }, icon('message-square'), ' ', at.teacher_feedback));
    root.append(head);
    if (teacher && d.events && d.events.length) {
      const tl = h('div', { class: 'timeline' });
      for (const e of d.events) tl.append(h('div', { class: `ev ${e.kind}` }, h('span', { class: 't' }, new Date(e.at).toLocaleTimeString('bg-BG')), icon(e.kind === 'violation' ? 'alert-triangle' : e.kind === 'annulled' ? 'ban' : e.kind === 'start' ? 'play' : 'send'), h('span', {}, { start: 'Начало', submit: 'Предаване', autosubmit: 'Автоматично предаване', violation: 'Нарушение', annulled: 'Анулиране' }[e.kind] || e.kind, e.detail ? ` – ${e.detail}` : '')));
      root.append(h('details', { class: 'panel mb', open: at.warnings > 0 || null }, h('summary', {}, icon('activity'), `Дневник на опита (${at.warnings} предупреждения)`), h('div', { class: 'panel-body' }, tl)));
    }
    let lastSection = null;
    for (const q of d.questions) {
      const sec = (d.sections || []).find(s => s.key === q.section_key);
      if (sec && d.sections.length > 1 && sec.key !== lastSection) { root.append(h('div', { class: 'section-title' }, icon('folder'), sec.title)); lastSection = sec.key; }
      const card = Questions.renderCard(q, { key: q.id, n: q.n, response: q.response, review: true, teacherView: teacher, final_score: q.final_score, manual_score: q.manual_score, needs_manual: q.needs_manual, feedback: teacher ? '' : q.feedback, onChange: () => {} });
      if (teacher && at.status !== 'annulled') card.insertBefore(gradeInput(q), card.querySelector('.q-foot'));
      root.append(card);
    }
    if (teacher && at.status !== 'annulled') {
      root.append(h('div', { class: 'card' }, h('label', { class: 'field' }, 'Общ коментар към ученика', h('textarea', { id: 'overallFb', rows: 3 }, at.teacher_feedback || '')), h('div', { class: 'row gap mt-s' }, h('button', { class: 'btn primary', onClick: save }, icon('save'), 'Запази оценяването'), h('a', { class: 'btn ghost', href: `/assignments/${at.assignment_id}` }, 'Назад към резултатите'))));
    }
    icons(root); renderMath(root);
  }
  document.addEventListener('DOMContentLoaded', init);
})();
