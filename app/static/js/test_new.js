/* Съветник за нов тест: данни → начин на създаване → контейнери → създаване. */
(function () {
  const { h, icon, icons, api, toast, modal } = App;
  const root = document.getElementById('wizard'); if (!root) return;
  const aiMode = root.dataset.ai;
  const state = { step: 1, title: '', description: '', curriculum_id: '', mode: 'ai', sections: [] };
  const curTpl = document.getElementById('curriculumOptions');
  const mine = Array.from(curTpl.options).find(o => o.dataset.mine); if (mine) state.curriculum_id = mine.value;

  function steps() { const names = ['Данни за теста', 'Начин на създаване', 'Контейнери', 'Преглед']; const el = h('div', { class: 'steps' }); names.forEach((n, i) => { const k = i + 1; el.append(h('div', { class: 'step' + (k === state.step ? ' active' : k < state.step ? ' done' : '') }, h('span', { class: 'n' }, k < state.step ? icon('check') : k), n)); if (k < names.length) el.append(h('span', { class: 'line' })); }); return el; }

  function step1() {
    const title = h('input', { type: 'text', value: state.title, placeholder: 'напр. Контролна работа №1 – Квадратни уравнения' }); const desc = h('textarea', { rows: 2, placeholder: 'Кратко описание / указания за учениците' }, state.description);
    const cur = curTpl.cloneNode(true); cur.id = ''; cur.classList.remove('hidden'); cur.value = state.curriculum_id;
    return h('div', { class: 'card', style: { maxWidth: '720px', margin: '0 auto' } }, h('h2', {}, 'Данни за теста'), h('div', { class: 'stack' }, h('label', { class: 'field' }, 'Заглавие', title), h('label', { class: 'field' }, 'Описание', desc), h('label', { class: 'field' }, 'Учебна програма', cur, h('span', { class: 'hint' }, 'AI генерира въпросите по темите и очакваните резултати от програмата.'))),
      h('div', { class: 'row gap mt', style: { justifyContent: 'flex-end' } }, h('button', { class: 'btn primary', onClick: () => { if (!title.value.trim()) return toast('Въведете заглавие', 'error'); state.title = title.value.trim(); state.description = desc.value; state.curriculum_id = cur.value; state.step = 2; render(); } }, 'Напред', icon('arrow-right'))));
  }
  function step2() {
    const opts = [
      ['ai', 'sparkles', 'Генериране с AI по учебната програма', 'Подреждате контейнери (тип, брой, трудност, теми), а Gemini ги запълва с въпроси. След това редактирате свободно.', aiMode === 'off'],
      ['bank', 'library', 'Автоматично от банката с въпроси', 'Контейнерите се запълват със случайни въпроси от вашата банка по избраните критерии.', false],
      ['manual', 'pencil-line', 'Собствен тест от нулата', 'Добавяте въпросите един по един с редактора – всички 15 типа задачи.', false],
    ];
    const list = h('div', { class: 'choice-list' });
    for (const [k, ic, t, sub, dis] of opts) { const inp = h('input', { type: 'radio', name: 'mode', value: k, checked: state.mode === k || null, disabled: dis || null }); const el = h('label', { class: 'choice' + (state.mode === k ? ' selected' : '') + (dis ? ' disabled' : ''), style: dis ? { opacity: .55 } : {} }, inp, h('div', {}, h('div', { class: 'choice-title' }, icon(ic), ' ', t, dis ? h('span', { class: 'badge warning', style: { marginLeft: '.5rem' } }, 'нужен GEMINI_API_KEY') : null), h('div', { class: 'choice-sub' }, sub))); inp.addEventListener('change', () => { state.mode = k; list.querySelectorAll('.choice').forEach(c => c.classList.remove('selected')); el.classList.add('selected'); }); list.append(el); }
    return h('div', { class: 'card', style: { maxWidth: '720px', margin: '0 auto' } }, h('h2', {}, 'Как да създадем теста?'), list, h('div', { class: 'row gap mt between' }, h('button', { class: 'btn ghost', onClick: () => { state.step = 1; render(); } }, icon('arrow-left'), 'Назад'), h('button', { class: 'btn primary', onClick: () => { if (state.mode === 'manual') return create(); if (!state.sections.length) state.sections.push({ key: Sections.uid(), title: 'Част 1', type: 'single_choice', count: 5, difficulty: 2, topics: [], points: 1, source: state.mode, instructions: '' }); state.sections.forEach(s => s.source = state.mode); state.step = 3; render(); } }, state.mode === 'manual' ? 'Създай теста' : 'Напред', icon('arrow-right'))));
  }
  function editSection(s, onDone) {
    const f = Sections.sectionForm(s, { curriculumId: state.curriculum_id, aiMode, allowManual: false });
    const m = modal({ title: s ? 'Контейнер' : 'Нов контейнер', iconName: 'box', wide: true, body: f.el, footer: [h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Отказ'), h('button', { class: 'btn primary', onClick: () => { const v = f.collect(); if (!v.type) return toast('Изберете тип', 'error'); m.close(); onDone(v); } }, 'Готово')] });
  }
  function step3() {
    const list = h('div');
    function draw() {
      list.innerHTML = '';
      state.sections.forEach((s, i) => { const card = Sections.sectionSummary(s); card.draggable = true; card.addEventListener('dragstart', e => { e.dataTransfer.setData('text/plain', i); card.classList.add('dragging'); }); card.addEventListener('dragend', () => card.classList.remove('dragging')); card.addEventListener('dragover', e => e.preventDefault()); card.addEventListener('drop', e => { e.preventDefault(); const from = Number(e.dataTransfer.getData('text/plain')); if (from === i) return; const [x] = state.sections.splice(from, 1); state.sections.splice(i, 0, x); draw(); });
        card.querySelector('.sc-head').append(h('button', { class: 'icon-btn sm', onClick: () => editSection(s, v => { state.sections[i] = v; draw(); }) }, icon('pencil')), h('button', { class: 'icon-btn sm danger', onClick: () => { state.sections.splice(i, 1); draw(); } }, icon('x'))); list.append(card); });
      icons(list);
    }
    draw();
    const total = () => state.sections.reduce((a, s) => a + s.count, 0);
    return h('div', { class: 'card', style: { maxWidth: '820px', margin: '0 auto' } }, h('h2', {}, 'Подредете контейнерите на теста'), h('p', { class: 'muted' }, state.mode === 'ai' ? 'Всеки контейнер е група въпроси от един тип. AI ще ги запълни по учебната програма.' : 'Всеки контейнер се запълва със случайни въпроси от банката по зададените критерии.'), aiMode === 'mock' && state.mode === 'ai' ? h('div', { class: 'ai-note mb' }, icon('sparkles'), h('span', {}, 'AI работи в демо режим – ще бъдат създадени примерни въпроси.')) : null, list,
      h('button', { class: 'btn soft mt-s', onClick: () => editSection(null, v => { state.sections.push(v); draw(); }) }, icon('plus'), 'Добави контейнер'),
      h('div', { class: 'row gap mt between' }, h('button', { class: 'btn ghost', onClick: () => { state.step = 2; render(); } }, icon('arrow-left'), 'Назад'), h('button', { class: 'btn primary', onClick: () => { if (!state.sections.length) return toast('Добавете поне един контейнер', 'error'); state.step = 4; render(); } }, `Напред (${total()} въпроса)`, icon('arrow-right'))));
  }
  function step4() {
    const total = state.sections.reduce((a, s) => a + s.count, 0), pts = state.sections.reduce((a, s) => a + s.count * s.points, 0);
    return h('div', { class: 'card', style: { maxWidth: '720px', margin: '0 auto' } }, h('h2', {}, 'Преглед'), h('div', { class: 'stack' }, h('div', {}, h('strong', {}, state.title), h('div', { class: 'subtle' }, curTpl.options[curTpl.selectedIndex]?.text)), h('div', { class: 'row gap wrap' }, h('span', { class: 'badge primary' }, `${state.sections.length} контейнера`), h('span', { class: 'badge' }, `${total} въпроса`), h('span', { class: 'badge' }, `${pts} т.`)), ...state.sections.map(Sections.sectionSummary)),
      h('div', { class: 'row gap mt between' }, h('button', { class: 'btn ghost', onClick: () => { state.step = 3; render(); } }, icon('arrow-left'), 'Назад'), h('button', { class: 'btn primary lg', id: 'createBtn', onClick: create }, icon(state.mode === 'ai' ? 'sparkles' : 'check'), state.mode === 'ai' ? 'Създай и генерирай с AI' : 'Създай и попълни от банката')));
  }
  async function create() {
    const btn = document.getElementById('createBtn'); if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Създаване…'; }
    try {
      const t = await api('POST', '/api/tests', { title: state.title, description: state.description, curriculum_id: state.curriculum_id ? Number(state.curriculum_id) : null, sections: state.mode === 'manual' ? null : state.sections });
      location.href = `/tests/${t.id}/edit` + (state.mode === 'ai' ? '?generate=1' : state.mode === 'bank' ? '?fill=1' : '');
    } catch (e) { toast(e.message, 'error'); if (btn) { btn.disabled = false; btn.textContent = 'Опитай отново'; } }
  }
  function render() { root.innerHTML = ''; root.append(steps(), [step1, step2, step3, step4][state.step - 1]()); icons(root); }
  render();
})();
