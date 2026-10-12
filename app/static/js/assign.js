/* Възлагане на тест: класове, режим, период, опити, строг режим. */
(function () {
  const { h, icon, icons, api, toast, toLocalInput } = App;
  const root = document.getElementById('assignForm'); if (!root) return;
  const testId = Number(root.dataset.test); const classes = JSON.parse(document.getElementById('classesData').textContent);

  function choice(name, value, title, sub, checked) { const inp = h('input', { type: 'radio', name, value, checked: checked || null }); const el = h('label', { class: 'choice' + (checked ? ' selected' : '') }, inp, h('div', {}, h('div', { class: 'choice-title' }, title), h('div', { class: 'choice-sub' }, sub))); inp.addEventListener('change', () => { el.parentElement.querySelectorAll('.choice').forEach(c => c.classList.remove('selected')); el.classList.add('selected'); el.dispatchEvent(new CustomEvent('choice', { bubbles: true })); }); return el; }

  const now = new Date(); const start = h('input', { type: 'datetime-local', value: toLocalInput(now.toISOString()) });
  const end = h('input', { type: 'datetime-local' }); const noEnd = h('input', { type: 'checkbox', checked: true });
  const title = h('input', { type: 'text', value: root.dataset.title });
  const limit = h('input', { type: 'number', min: 0, placeholder: 'без ограничение' });
  const attempts = h('input', { type: 'number', min: 0, value: 1 });
  const variants = h('input', { type: 'number', min: 1, max: 10, value: 1 });
  const shuffleQ = h('input', { type: 'checkbox' }), shuffleO = h('input', { type: 'checkbox', checked: true });
  const maxWarn = h('input', { type: 'number', min: 0, max: 10, value: 3 });
  const showRes = h('select', {}, h('option', { value: 'immediately' }, 'Веднага след предаване'), h('option', { value: 'after_end' }, 'След крайния срок / затваряне'), h('option', { value: 'never' }, 'Никога (само учителят вижда)'));
  const scale = { 6: h('input', { type: 'number', value: 90, class: 'sm' }), 5: h('input', { type: 'number', value: 75, class: 'sm' }), 4: h('input', { type: 'number', value: 60, class: 'sm' }), 3: h('input', { type: 'number', value: 50, class: 'sm' }) };

  const classBoxes = classes.map(c => { const cb = h('input', { type: 'checkbox', value: c.id }); return h('label', { class: 'choice' }, cb, h('div', {}, h('div', { class: 'choice-title' }, c.name), h('div', { class: 'choice-sub' }, `${c.n} ученици`))); });
  classBoxes.forEach(el => el.querySelector('input').addEventListener('change', e => el.classList.toggle('selected', e.target.checked)));
  const modes = h('div', { class: 'choice-list' }, choice('mode', 'practice', 'Упражнение / домашна работа', 'Свободно решаване – без ограничения на действията на ученика.', true), choice('mode', 'exam', 'Изпит в строг режим', 'Цял екран, забранено превключване на табове/прозорци. След 3 предупреждения тестът се анулира с оценка 2.'));
  const examBox = h('div', { class: 'form-grid hidden' }, h('label', { class: 'field' }, 'Брой предупреждения преди анулиране', maxWarn, h('span', { class: 'hint' }, 'При следващото нарушение след тях тестът се анулира.')));
  modes.addEventListener('choice', () => { const exam = modes.querySelector('input:checked').value === 'exam'; examBox.classList.toggle('hidden', !exam); if (exam) { attempts.value = 1; if (!limit.value) limit.value = 40; showRes.value = 'after_end'; } });
  noEnd.addEventListener('change', () => { end.disabled = noEnd.checked; }); end.disabled = true;

  root.append(
    h('div', { class: 'grid cols-2' },
      h('div', { class: 'stack' },
        h('div', { class: 'card' }, h('div', { class: 'card-head' }, h('h3', {}, icon('users'), '1. Класове')), classes.length ? h('div', { class: 'choice-list' }, ...classBoxes) : h('p', { class: 'muted' }, 'Нямате класове – ', h('a', { href: '/classes' }, 'създайте клас'), '.')),
        h('div', { class: 'card' }, h('div', { class: 'card-head' }, h('h3', {}, icon('shield-check'), '2. Режим на решаване')), modes, h('div', { class: 'mt' }, examBox)),
      ),
      h('div', { class: 'stack' },
        h('div', { class: 'card' }, h('div', { class: 'card-head' }, h('h3', {}, icon('settings-2'), '3. Настройки')),
          h('div', { class: 'form-grid' },
            h('label', { class: 'field full' }, 'Заглавие на заданието', title),
            h('label', { class: 'field' }, 'Активно от', start), h('label', { class: 'field' }, 'До', end, h('label', { class: 'check' }, noEnd, 'без краен срок')),
            h('label', { class: 'field' }, 'Време за решаване (мин)', limit), h('label', { class: 'field' }, 'Разрешени опити (0 = неограничено)', attempts),
            h('label', { class: 'field' }, 'Варианти (случайно разпределение)', variants), h('label', { class: 'field' }, 'Показване на резултата на ученика', showRes),
            h('div', { class: 'field full' }, 'Разбъркване', h('div', { class: 'row gap wrap' }, h('label', { class: 'check' }, shuffleQ, 'на въпросите'), h('label', { class: 'check' }, shuffleO, 'на отговорите'))),
            h('div', { class: 'field full' }, 'Скала за оценяване (минимален % за оценка)', h('div', { class: 'row gap wrap' }, ...[6, 5, 4, 3].map(g => h('label', { class: 'row gap' }, h('strong', {}, g), scale[g], '%')), h('span', { class: 'subtle' }, 'под това – Слаб (2)'))))),
        h('div', { class: 'row gap' }, h('button', { class: 'btn primary lg', onClick: submit }, icon('send'), 'Възложи теста'), h('a', { class: 'btn ghost', href: `/tests/${testId}/edit` }, 'Назад')))));
  icons(root);

  async function submit() {
    const classroom_ids = classBoxes.filter(el => el.querySelector('input').checked).map(el => Number(el.querySelector('input').value));
    if (!classroom_ids.length) return toast('Изберете поне един клас', 'error');
    const body = { test_id: testId, title: title.value, mode: modes.querySelector('input:checked').value, classroom_ids, start_at: start.value ? new Date(start.value).toISOString() : null, end_at: noEnd.checked || !end.value ? null : new Date(end.value).toISOString(), time_limit_min: limit.value ? Number(limit.value) : null, attempts_allowed: Number(attempts.value || 0), shuffle_questions: shuffleQ.checked, shuffle_options: shuffleO.checked, variants: Number(variants.value || 1), show_results: showRes.value, max_warnings: Number(maxWarn.value || 3), grade_scale: Object.fromEntries(Object.entries(scale).map(([g, i]) => [g, Number(i.value)])) };
    try { const a = await api('POST', '/api/assignments', body); toast('Тестът е възложен', 'success'); location.href = `/assignments/${a.id}`; } catch (e) { toast(e.message, 'error'); }
  }
})();
