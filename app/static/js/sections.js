/* Форма за контейнер (секция) на тест – споделена от съветника и конструктора. */
(function () {
  const { h, icon, icons } = App;
  const QTYPES = (() => { try { return JSON.parse(document.getElementById('qtypesData')?.textContent || '[]'); } catch (e) { return []; } })();
  const TYPE_META = Object.fromEntries(QTYPES.map(([k, label, ic, auto, group]) => [k, { label, icon: ic, auto, group }]));
  const uid = () => 's' + Math.random().toString(36).slice(2, 7);

  function topicsOf(curriculumId) { const sel = document.getElementById('curriculumOptions'); const opt = sel && Array.from(sel.options).find(o => o.value === String(curriculumId)); try { return JSON.parse(opt?.dataset.topics || '[]'); } catch (e) { return []; } }

  /* Връща { el, collect() } */
  function sectionForm(section, { curriculumId, aiMode = 'off', allowManual = true } = {}) {
    const s = { key: uid(), title: '', type: 'single_choice', count: 5, difficulty: 2, topics: [], points: 1, source: aiMode !== 'off' ? 'ai' : 'bank', instructions: '', ...(section || {}) };
    const title = h('input', { type: 'text', value: s.title, placeholder: 'напр. Част 1: Квадратни уравнения' });
    const typeGrid = h('div', { class: 'type-grid' });
    let type = s.type || '';
    function drawTypes() { typeGrid.innerHTML = ''; for (const [k, m] of Object.entries(TYPE_META)) typeGrid.append(h('button', { type: 'button', class: 'type-card' + (type === k ? ' active' : ''), onClick: () => { type = k; drawTypes(); } }, icon(m.icon), h('div', {}, h('div', { class: 'tc-label' }, m.label), h('div', { class: 'tc-sub' }, m.auto ? 'автоматична проверка' : 'ръчна проверка')))); icons(typeGrid); }
    drawTypes();
    const count = h('input', { type: 'number', min: 1, max: 30, value: s.count || 5 }); const diff = h('select', {}, h('option', { value: 1 }, 'Ниска'), h('option', { value: 2 }, 'Средна'), h('option', { value: 3 }, 'Висока')); diff.value = s.difficulty || 2;
    const points = h('input', { type: 'number', min: 0.25, step: 0.25, value: s.points || 1 });
    const chosen = new Set(s.topics || []); const topicBox = h('div', { class: 'chip-list' });
    const topics = topicsOf(curriculumId);
    function drawTopics() { topicBox.innerHTML = ''; if (!topics.length) { topicBox.append(h('span', { class: 'subtle' }, 'Изберете учебна програма за теста, за да посочите теми.')); return; } for (const t of topics) topicBox.append(h('button', { type: 'button', class: 'chip' + (chosen.has(t) ? ' active' : ''), onClick: () => { chosen.has(t) ? chosen.delete(t) : chosen.add(t); drawTopics(); } }, chosen.has(t) ? icon('check') : null, t)); icons(topicBox); }
    drawTopics();
    const source = h('div', { class: 'segment' });
    let src = s.source;
    const srcOpts = [['ai', 'Генерирай с AI', aiMode === 'off'], ['bank', 'От банката с въпроси', false], ['manual', 'Ръчно', !allowManual]];
    function drawSrc() { source.innerHTML = ''; for (const [k, lab, dis] of srcOpts) if (!dis) source.append(h('button', { type: 'button', class: src === k ? 'active' : '', onClick: () => { src = k; drawSrc(); } }, lab)); }
    if (srcOpts.find(o => o[0] === src)?.[2]) src = 'bank';
    drawSrc();
    const instr = h('textarea', { rows: 2, placeholder: 'напр. включи задачи с практически контекст; използвай само цели числа' }, s.instructions || '');
    const el = h('div', { class: 'stack' },
      h('div', { class: 'form-grid' }, h('label', { class: 'field full' }, 'Заглавие на контейнера', title), h('div', { class: 'field full' }, 'Източник на въпросите', source), h('label', { class: 'field' }, 'Брой въпроси', count), h('label', { class: 'field' }, 'Трудност', diff), h('label', { class: 'field' }, 'Точки на въпрос', points)),
      h('div', { class: 'field' }, 'Тип на въпросите', typeGrid),
      h('div', { class: 'field' }, 'Теми от учебната програма', topicBox, h('span', { class: 'hint' }, 'Без избрана тема AI използва цялата програма.')),
      h('label', { class: 'field' }, 'Указания към AI (по желание)', instr));
    return { el, collect: () => ({ key: s.key, title: title.value.trim() || (TYPE_META[type]?.label || 'Част'), type, count: Number(count.value || 0), difficulty: Number(diff.value), topics: [...chosen], points: Number(points.value || 1), source: src, instructions: instr.value.trim() }) };
  }

  function sectionSummary(s) {
    const m = TYPE_META[s.type] || {};
    return h('div', { class: `section-card src-${s.source}` }, h('div', { class: 'sc-head' }, icon('grip-vertical'), h('span', { class: 'sc-title' }, s.title), h('span', { class: 'badge' }, s.source === 'ai' ? 'AI' : s.source === 'bank' ? 'банка' : 'ръчно')),
      h('div', { class: 'sc-body' }, h('div', { class: 'row' }, icon(m.icon || 'help-circle'), m.label || '–', h('span', { class: 'right' }, `${s.count} × ${s.points} т.`)), s.topics?.length ? h('div', {}, icon('tag'), ' ', s.topics.join('; ')) : null));
  }

  window.Sections = { sectionForm, sectionSummary, TYPE_META, uid };
})();
