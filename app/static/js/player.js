/* Решаване на тест: автоматично записване, таймер, изпитен режим (цял екран,
   следене на фокус/табове, предупреждения и анулиране). */
(function () {
  const { h, icon, icons, api, toast, fmtDuration, confirmDialog, modal, renderMath } = App;
  const root = document.getElementById('player');
  const attemptId = Number(document.body.dataset.attempt);
  const isExam = document.body.dataset.exam === '1';

  let data = null, timeLeft = null, timerHandle = null, submitting = false, finished = false;
  const responses = {}; const pending = new Map(); let saveState = 'saved';
  let warnings = 0, maxWarnings = 3, lastViolationAt = 0, suppressUntil = 0, overlay = null;

  /* ---------- запис на отговори ---------- */
  const saveQueue = {};
  function queueSave(qid, value) {
    responses[qid] = value; setSaveState('pending'); updateNav();
    clearTimeout(saveQueue[qid]);
    saveQueue[qid] = setTimeout(() => flush(qid), 500);
  }
  async function flush(qid) {
    if (finished) return;
    const p = api('PUT', `/api/attempts/${attemptId}/answers/${qid}`, { response: responses[qid] })
      .then(r => { if (r && r.time_left !== null && r.time_left !== undefined) timeLeft = r.time_left; })
      .catch(e => { if (e.status === 409) { finished = true; showMessage('Опитът е приключен', e.message, true); } else { setSaveState('error'); toast('Грешка при запис: ' + e.message, 'error'); } })
      .finally(() => { pending.delete(qid); if (!pending.size && saveState !== 'error') setSaveState('saved'); });
    pending.set(qid, p);
  }
  async function flushAll() { for (const qid of Object.keys(saveQueue)) { clearTimeout(saveQueue[qid]); } for (const qid of Object.keys(responses)) if (!pending.has(qid)) {/* already saved */} await Promise.all([...pending.values()]); }
  function setSaveState(s) { saveState = s; const el = document.getElementById('saveState'); if (!el) return; el.innerHTML = ''; el.append(icon(s === 'saved' ? 'cloud-check' : s === 'pending' ? 'cloud-upload' : 'cloud-off'), ' ', s === 'saved' ? 'Записано' : s === 'pending' ? 'Записва се…' : 'Грешка при запис'); icons(el); }

  /* ---------- таймер ---------- */
  function startTimer() {
    if (timeLeft === null || timeLeft === undefined) return;
    const el = document.getElementById('timer');
    if (!el) { timerHandle = setInterval(() => { timeLeft = Math.max(0, timeLeft - 1); if (timeLeft <= 0 && !finished) { clearInterval(timerHandle); submit(true); } }, 1000); return; }
    const tick = () => {
      if (finished) return;
      timeLeft = Math.max(0, timeLeft - 1);
      if (el) { el.textContent = ''; el.append(icon('timer'), ' ', fmtDuration(timeLeft)); icons(el); el.classList.toggle('low', timeLeft <= 60); }
      if (timeLeft <= 0) { clearInterval(timerHandle); submit(true); }
    };
    tick(); timerHandle = setInterval(tick, 1000);
  }

  /* ---------- изпитен режим ---------- */
  function inFullscreen() { return !!(document.fullscreenElement || document.webkitFullscreenElement); }
  async function enterFullscreen() { try { await (document.documentElement.requestFullscreen ? document.documentElement.requestFullscreen({ navigationUI: 'hide' }) : document.documentElement.webkitRequestFullscreen()); } catch (e) {} }
  function exitFullscreen() { try { if (inFullscreen()) document.exitFullscreen(); } catch (e) {} }

  async function violation(kind, detail = '') {
    if (!isExam || finished || submitting) return;
    const now = Date.now();
    if (now < suppressUntil) return;
    if (now - lastViolationAt < 2500) return;
    lastViolationAt = now;
    try {
      const r = await api('POST', `/api/attempts/${attemptId}/violation`, { kind, detail });
      if (r.ignored) return;
      warnings = r.warnings; maxWarnings = r.max_warnings; updateWarnBadge();
      if (r.status === 'annulled') { finished = true; clearInterval(timerHandle); showAnnulled(); return; }
      showWarning(kind);
    } catch (e) { /* мрежова грешка – не блокираме ученика */ }
  }
  const KIND_TEXT = { tab: 'Напуснахте раздела на изпита (смяна на таб или прозорец).', blur: 'Прозорецът на изпита загуби фокус (друго приложение или прозорец).', fullscreen: 'Излязохте от режим „цял екран“.', keys: 'Използвахте забранена клавишна комбинация.' };
  function showWarning(kind) {
    if (overlay) overlay.remove();
    overlay = h('div', { class: 'warn-overlay' }, h('div', { class: 'box' }, icon('shield-alert'), h('h2', {}, 'Предупреждение'), h('div', { class: 'count' }, `${warnings} / ${maxWarnings}`), h('p', {}, KIND_TEXT[kind] || 'Отчетено е напускане на изпита.'), h('p', {}, warnings >= maxWarnings ? 'Това беше последното предупреждение. При следващо нарушение тестът ще бъде анулиран с оценка Слаб (2).' : `Имате още ${maxWarnings - warnings} предупреждения. След тях тестът се анулира с оценка Слаб (2).`), h('button', { class: 'btn lg primary', onClick: async () => { overlay.remove(); overlay = null; await enterFullscreen(); window.focus(); } }, icon('arrow-left'), 'Връщане към изпита')));
    document.body.append(overlay); icons(overlay);
  }
  function showAnnulled() {
    exitFullscreen();
    root.innerHTML = '';
    root.append(h('div', { class: 'card exam-gate' }, icon('ban', 'shield'), h('h1', {}, 'Тестът е анулиран'), h('p', { class: 'muted' }, `Превишихте допустимия брой предупреждения (${maxWarnings}). Резултатът е оценка Слаб (2). Учителят ви е уведомен.`), h('a', { class: 'btn primary', href: '/' }, icon('home'), 'Към началото')));
    if (overlay) { overlay.remove(); overlay = null; }
    icons(root);
  }
  function updateWarnBadge() { const el = document.getElementById('warnCount'); if (!el) return; el.innerHTML = ''; for (let i = 0; i < maxWarnings; i++) el.append(h('i', { class: i < warnings ? 'on' : '' })); const lab = document.getElementById('warnLabel'); if (lab) lab.textContent = `Предупреждения: ${warnings}/${maxWarnings}`; }
  function armMonitoring() {
    document.addEventListener('visibilitychange', () => { if (document.hidden) violation('tab'); });
    window.addEventListener('blur', () => { setTimeout(() => { if (!document.hasFocus() && !document.hidden) violation('blur'); else if (document.hidden) {/* обработено от visibilitychange */} }, 150); });
    document.addEventListener('fullscreenchange', () => { if (!inFullscreen() && !finished && !submitting) violation('fullscreen'); });
    document.addEventListener('contextmenu', e => e.preventDefault());
    ['copy', 'cut', 'paste'].forEach(ev => document.addEventListener(ev, e => { if (!e.target.closest('.ql-editor, textarea, input')) e.preventDefault(); }));
    document.addEventListener('keydown', e => {
      const k = e.key.toLowerCase();
      if (e.key === 'F12' || (e.ctrlKey && e.shiftKey && ['i', 'j', 'c'].includes(k)) || (e.ctrlKey && ['p', 's', 'u', 't', 'n', 'w'].includes(k)) || (e.altKey && e.key === 'Tab')) { e.preventDefault(); violation('keys', e.key); }
    });
    // Диалогът за избор на файл изважда прозореца от фокус – не е нарушение
    document.addEventListener('click', e => { if (e.target.matches('input[type=file]')) { suppressUntil = Date.now() + 90000; const back = () => { suppressUntil = Date.now() + 1500; window.removeEventListener('focus', back); }; window.addEventListener('focus', back); } }, true);
    window.addEventListener('beforeunload', e => { if (!finished) { e.preventDefault(); e.returnValue = ''; } });
  }

  /* ---------- рендериране ---------- */
  function updateNav() {
    document.querySelectorAll('.q-nav button').forEach(b => { const q = data.questions.find(x => x.id === Number(b.dataset.qid)); b.classList.toggle('answered', Questions.isAnswered(q.type, responses[q.id])); });
  }
  function render() {
    root.innerHTML = '';
    const a = data.assignment;
    const top = h('div', { class: 'player-top' },
      h('span', { class: 'title' }, a.title),
      a.mode === 'exam' ? h('span', { class: 'badge danger' }, icon('shield-alert'), 'Изпит') : h('span', { class: 'badge primary' }, 'Упражнение'),
      h('span', { class: 'save-state', id: 'saveState' }),
      a.time_limit_min ? h('span', { class: 'timer', id: 'timer' }) : h('span', { class: 'subtle' }, icon('infinity'), ' без ограничение във времето'),
    );
    root.append(top);
    if (isExam) root.append(h('div', { class: 'exam-banner' }, icon('eye'), h('span', { id: 'warnLabel' }, `Предупреждения: ${warnings}/${maxWarnings}`), h('span', { class: 'warn-count', id: 'warnCount' }), h('span', { class: 'right subtle' }, 'Строг режим: не напускайте страницата')));
    const nav = h('div', { class: 'q-nav' });
    data.questions.forEach((q, i) => nav.append(h('button', { type: 'button', dataset: { qid: q.id }, title: q.type_label, onClick: () => { const el = document.querySelector(`.q-card[data-qid="${q.id}"]`); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' }); } }, i + 1)));
    root.append(nav);
    const sections = data.sections || [];
    let lastSection = null;
    data.questions.forEach((q, i) => {
      const sec = sections.find(s => s.key === q.section_key);
      if (sec && sections.length > 1 && sec.key !== lastSection) { root.append(h('div', { class: 'section-title' }, icon('folder'), sec.title)); lastSection = sec.key; }
      responses[q.id] = q.response;
      root.append(Questions.renderCard(q, { key: q.id, n: i + 1, response: q.response, review: false, onChange: v => queueSave(q.id, v) }));
    });
    root.append(h('div', { class: 'player-foot' }, h('span', { class: 'subtle', style: { alignSelf: 'center' } }, `${data.questions.length} въпроса · ${data.attempt.max_score} т.`), h('button', { class: 'btn primary lg', onClick: () => submit(false) }, icon('send'), 'Предай теста')));
    icons(root); renderMath(root); updateNav(); updateWarnBadge(); setSaveState('saved'); startTimer();
  }

  function showMessage(title, text, danger) {
    root.innerHTML = '';
    root.append(h('div', { class: 'card exam-gate' }, icon(danger ? 'alert-triangle' : 'check-circle-2', 'shield'), h('h1', {}, title), h('p', { class: 'muted' }, text), h('a', { class: 'btn primary', href: '/' }, icon('home'), 'Към началото')));
    icons(root);
  }

  async function submit(auto) {
    if (submitting || finished) return;
    if (!auto) {
      const unanswered = data.questions.filter(q => !Questions.isAnswered(q.type, responses[q.id])).length;
      const ok = await confirmDialog(unanswered ? `Имате ${unanswered} неотговорени въпроса. Сигурни ли сте, че искате да предадете?` : 'Сигурни ли сте, че искате да предадете теста?', { okText: 'Предай', title: 'Предаване' });
      if (!ok) return;
    }
    submitting = true;
    try {
      await flushAll();
      const r = await api('POST', `/api/attempts/${attemptId}/submit`);
      finished = true; clearInterval(timerHandle); exitFullscreen();
      root.innerHTML = '';
      const box = h('div', { class: 'card exam-gate result-hero' });
      if (auto) box.append(h('p', { class: 'badge warning' }, 'Времето изтече – тестът беше предаден автоматично.'));
      if (r.results_visible && r.status === 'submitted') {
        box.append(h('div', { class: `grade-big g${Math.round(r.grade)}` }, r.grade), h('h2', {}, r.grade_label), h('p', { class: 'muted' }, `${r.score} от ${r.max_score} точки · ${r.percent}%`));
        if (r.needs_manual) box.append(h('p', {}, h('span', { class: 'badge info' }, 'Част от отговорите ще бъдат проверени от учителя.')));
        box.append(h('div', { class: 'row gap', style: { justifyContent: 'center' } }, h('a', { class: 'btn', href: `/attempts/${attemptId}/review` }, icon('eye'), 'Преглед на отговорите'), h('a', { class: 'btn primary', href: '/' }, icon('home'), 'Към началото')));
      } else {
        box.append(icon('check-circle-2', 'shield'), h('h1', {}, 'Тестът е предаден'), h('p', { class: 'muted' }, 'Резултатът ще бъде публикуван от учителя.'), h('a', { class: 'btn primary', href: '/' }, icon('home'), 'Към началото'));
      }
      root.append(box); icons(root);
    } catch (e) { submitting = false; toast(e.message, 'error'); if (e.status === 409) { finished = true; showMessage('Опитът е приключен', e.message, true); } }
  }

  async function init() {
    try { data = await api('GET', `/api/attempts/${attemptId}`); }
    catch (e) { root.innerHTML = ''; root.append(h('div', { class: 'card empty' }, e.message)); return; }
    if (data.attempt.status !== 'in_progress') { location.href = `/attempts/${attemptId}/review`; return; }
    timeLeft = data.time_left; warnings = data.attempt.warnings; maxWarnings = data.assignment.max_warnings;
    if (isExam) {
      root.innerHTML = '';
      root.append(h('div', { class: 'card exam-gate' }, icon('shield-check', 'shield'), h('h1', {}, data.assignment.title), h('p', { class: 'muted' }, 'Изпитът се провежда в строг режим:'),
        h('ul', {}, h('li', {}, 'тестът се решава на цял екран;'), h('li', {}, 'превключването към друг раздел, прозорец или програма се отчита;'), h('li', {}, `след ${maxWarnings} предупреждения тестът се анулира с оценка Слаб (2);`), data.assignment.time_limit_min ? h('li', {}, `време за решаване: ${data.assignment.time_limit_min} мин.`) : null),
        h('button', { class: 'btn primary lg', onClick: async () => { await enterFullscreen(); armMonitoring(); render(); } }, icon('play'), 'Започни изпита')));
      icons(root);
    } else render();
  }
  document.addEventListener('DOMContentLoaded', init);
})();
