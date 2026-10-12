/* Редактор на въпроси: Quill за условието (с KaTeX формули) + форма според типа. */
(function () {
  const { h, icon, icons, api, toast, modal, renderMath } = App;
  const QTYPES = (() => { try { return JSON.parse(document.getElementById('qtypesData')?.textContent || 'null') || null; } catch (e) { return null; } })();
  const SUB_TYPES = ['single_choice', 'multi_choice', 'true_false', 'fill_blank', 'dropdown_blank', 'open'];
  const TYPE_META = {};
  if (QTYPES) for (const [k, label, ic, auto, group] of QTYPES) TYPE_META[k] = { label, icon: ic, auto, group };
  const uid = (p = 'o') => p + Math.random().toString(36).slice(2, 8);

  function quillEditor(html, { compact = false, placeholder = '' } = {}) {
    const wrap = h('div'); const ed = h('div'); wrap.append(ed);
    const toolbar = compact ? [['bold', 'italic', 'underline'], ['formula', 'clean']] : [[{ header: [false, 2, 3] }], ['bold', 'italic', 'underline', 'strike'], [{ script: 'sub' }, { script: 'super' }], [{ list: 'ordered' }, { list: 'bullet' }], ['link', 'image', 'formula'], ['clean']];
    const q = new Quill(ed, { theme: 'snow', placeholder, modules: { toolbar } });
    if (html) q.clipboard.dangerouslyPasteHTML(html);
    // Качване на изображения като файл (вместо base64)
    const tb = q.getModule('toolbar');
    if (!compact) tb.addHandler('image', () => { const inp = h('input', { type: 'file', accept: 'image/*' }); inp.addEventListener('change', async () => { const f = inp.files[0]; if (!f) return; const fd = new FormData(); fd.append('file', f); try { const up = await api('POST', '/api/uploads', fd); const r = q.getSelection(true); q.insertEmbed(r ? r.index : 0, 'image', up.url, 'user'); } catch (e) { toast(e.message, 'error'); } }); inp.click(); });
    return { el: wrap, quill: q, html: () => { const s = q.getSemanticHTML(); return q.getText().trim() || s.includes('<img') || s.includes('ql-formula') ? s : ''; } };
  }

  /* --- помощни контроли --- */
  function listEditor({ items, placeholder, onChange, withCorrect, multi, min = 2 }) {
    const box = h('div', { class: 'editor-rows' });
    const rows = items.map(it => ({ ...it }));
    function draw() {
      box.innerHTML = '';
      rows.forEach((r, i) => {
        const inp = h('input', { type: 'text', value: r.text || '', placeholder: placeholder + ' ' + (i + 1) });
        inp.addEventListener('input', () => { r.text = inp.value; onChange && onChange(); });
        const row = h('div', { class: 'editor-row' });
        if (withCorrect) { const c = h('input', { type: multi ? 'checkbox' : 'radio', name: 'correct_' + box.dataset.k, class: 'radio', checked: r.correct || null, title: 'Верен отговор' }); c.addEventListener('change', () => { if (!multi) rows.forEach(x => x.correct = false); r.correct = c.checked; if (!multi) draw(); }); row.append(c); }
        row.append(h('span', { class: 'subtle', style: { width: '1.4rem' } }, i + 1 + '.'), inp, h('button', { type: 'button', class: 'icon-btn sm', title: 'Нагоре', disabled: i === 0 || null, onClick: () => { [rows[i - 1], rows[i]] = [rows[i], rows[i - 1]]; draw(); } }, icon('chevron-up')), h('button', { type: 'button', class: 'icon-btn sm danger', title: 'Премахни', disabled: rows.length <= min || null, onClick: () => { rows.splice(i, 1); draw(); } }, icon('x')));
        box.append(row);
      });
      box.append(h('button', { type: 'button', class: 'btn sm ghost', onClick: () => { rows.push({ id: uid(), text: '' }); draw(); setTimeout(() => box.querySelectorAll('input[type=text]')[rows.length - 1]?.focus(), 0); } }, icon('plus'), 'Добави'));
      icons(box);
    }
    box.dataset.k = uid('k'); draw();
    return { el: box, rows: () => rows.map(r => ({ ...r, text: (r.text || '').trim() })).filter(r => r.text) };
  }
  const field = (label, ctrl, hint) => h('label', { class: 'field' }, label, ctrl, hint ? h('span', { class: 'hint' }, hint) : null);
  const blanks = text => Array.from(new Set((text.match(/\[\[(\w+)\]\]/g) || []).map(m => m.slice(2, -2))));

  /* --- форми по тип: връщат { el, collect() } --- */
  const FORMS = {
    single_choice(d) { const opts = (d.options || [{ id: 'a', text: '' }, { id: 'b', text: '' }, { id: 'c', text: '' }, { id: 'd', text: '' }]).map(o => ({ ...o, correct: o.id === d.correct })); const le = listEditor({ items: opts, placeholder: 'Отговор', withCorrect: true, multi: false }); return { el: h('div', {}, h('p', { class: 'subtle' }, 'Отбележете верния отговор. Формули: $x^2$'), le.el), collect: () => { const rows = le.rows(); return { options: rows.map(r => ({ id: r.id, text: r.text })), correct: (rows.find(r => r.correct) || {}).id }; } }; },
    multi_choice(d) { const corr = new Set(d.correct || []); const opts = (d.options || [{ id: 'a', text: '' }, { id: 'b', text: '' }, { id: 'c', text: '' }, { id: 'd', text: '' }]).map(o => ({ ...o, correct: corr.has(o.id) })); const le = listEditor({ items: opts, placeholder: 'Отговор', withCorrect: true, multi: true }); const pc = h('input', { type: 'checkbox', checked: d.partial_credit !== false || null }); return { el: h('div', {}, h('p', { class: 'subtle' }, 'Отбележете всички верни отговори.'), le.el, h('label', { class: 'check mt-s' }, pc, 'Частичен кредит (точки за всеки верен, минус за грешен)')), collect: () => { const rows = le.rows(); return { options: rows.map(r => ({ id: r.id, text: r.text })), correct: rows.filter(r => r.correct).map(r => r.id), partial_credit: pc.checked }; } }; },
    true_false(d) {
      const rows = (d.statements || [{ id: uid('s'), text: '', answer: true }, { id: uid('s'), text: '', answer: false }]).map(s => ({ ...s })); const box = h('div', { class: 'editor-rows' });
      function draw() { box.innerHTML = ''; rows.forEach((r, i) => { const inp = h('input', { type: 'text', value: r.text, placeholder: 'Твърдение ' + (i + 1) }); inp.addEventListener('input', () => r.text = inp.value); const seg = h('div', { class: 'segment' }, h('button', { type: 'button', class: r.answer ? 'active' : '', onClick: () => { r.answer = true; draw(); } }, 'Вярно'), h('button', { type: 'button', class: !r.answer ? 'active' : '', onClick: () => { r.answer = false; draw(); } }, 'Грешно')); box.append(h('div', { class: 'editor-row' }, inp, seg, h('button', { type: 'button', class: 'icon-btn sm danger', disabled: rows.length <= 1 || null, onClick: () => { rows.splice(i, 1); draw(); } }, icon('x')))); }); box.append(h('button', { type: 'button', class: 'btn sm ghost', onClick: () => { rows.push({ id: uid('s'), text: '', answer: true }); draw(); } }, icon('plus'), 'Добави твърдение')); icons(box); }
      draw(); return { el: box, collect: () => ({ statements: rows.filter(r => r.text.trim()).map(r => ({ id: r.id, text: r.text.trim(), answer: !!r.answer })) }) };
    },
    dropdown_blank(d) {
      const text = h('textarea', { rows: 3, placeholder: 'Текст с празни места, напр.: Врабчето [[1]] по оградата.' }, d.text || ''); const box = h('div', { class: 'stack mt-s' }); const state = { ...(d.blanks || {}) };
      function draw() { box.innerHTML = ''; for (const k of blanks(text.value)) { state[k] ||= { options: [], correct: '' }; const opts = h('input', { type: 'text', value: (state[k].options || []).join(', '), placeholder: 'опция 1, опция 2, опция 3' }); const corr = h('input', { type: 'text', value: state[k].correct || '', placeholder: 'верният' }); opts.addEventListener('input', () => state[k].options = opts.value.split(',').map(s => s.trim()).filter(Boolean)); corr.addEventListener('input', () => state[k].correct = corr.value.trim()); box.append(h('div', { class: 'row gap wrap' }, h('span', { class: 'badge primary' }, `[[${k}]]`), field('Опции (разделени със запетая)', opts), field('Верен отговор', corr))); } }
      text.addEventListener('input', draw); draw();
      return { el: h('div', {}, field('Текст', text, 'Използвайте [[1]], [[2]] … за празните места'), box), collect: () => ({ text: text.value, blanks: Object.fromEntries(blanks(text.value).map(k => [k, state[k]])) }) };
    },
    fill_blank(d) {
      const text = h('textarea', { rows: 3, placeholder: 'Столицата на България е [[1]].' }, d.text || ''); const box = h('div', { class: 'stack mt-s' }); const state = { ...(d.blanks || {}) }; const cs = h('input', { type: 'checkbox', checked: d.case_sensitive || null });
      function draw() { box.innerHTML = ''; for (const k of blanks(text.value)) { state[k] ||= { answers: [] }; const a = h('input', { type: 'text', value: (state[k].answers || []).join(' | '), placeholder: 'София | гр. София' }); a.addEventListener('input', () => state[k].answers = a.value.split('|').map(s => s.trim()).filter(Boolean)); box.append(h('div', { class: 'row gap wrap' }, h('span', { class: 'badge primary' }, `[[${k}]]`), field('Приемливи отговори (разделени с |)', a))); } }
      text.addEventListener('input', draw); draw();
      return { el: h('div', {}, field('Текст', text, 'Използвайте [[1]], [[2]] … за празните места'), box, h('label', { class: 'check mt-s' }, cs, 'Малки/главни букви имат значение')), collect: () => ({ text: text.value, blanks: Object.fromEntries(blanks(text.value).map(k => [k, state[k]])), case_sensitive: cs.checked }) };
    },
    ordering(d) { const order = d.correct_order || []; const items = order.length ? order.map(id => (d.items || []).find(i => i.id === id)).filter(Boolean) : (d.items || [{ id: uid('i'), text: '' }, { id: uid('i'), text: '' }, { id: uid('i'), text: '' }]); const le = listEditor({ items, placeholder: 'Елемент' }); return { el: h('div', {}, h('p', { class: 'subtle' }, 'Въведете елементите в ПРАВИЛНИЯ ред – на ученика ще бъдат показани разбъркани.'), le.el), collect: () => { const rows = le.rows(); return { items: rows.map(r => ({ id: r.id, text: r.text })), correct_order: rows.map(r => r.id) }; } }; },
    matching(d) {
      const left = (d.left || [{ id: uid('l'), text: '' }, { id: uid('l'), text: '' }, { id: uid('l'), text: '' }]).map(x => ({ ...x })); const right = (d.right || [{ id: uid('r'), text: '' }, { id: uid('r'), text: '' }, { id: uid('r'), text: '' }]).map(x => ({ ...x })); const pairs = { ...(d.pairs || {}) };
      const lE = listEditor({ items: left, placeholder: 'Ляво' }), rE = listEditor({ items: right, placeholder: 'Дясно', min: 2 }); const pbox = h('div', { class: 'stack' });
      function drawPairs() { pbox.innerHTML = ''; const L = lE.rows(), R = rE.rows(); for (const l of L) { const sel = h('select', {}, h('option', { value: '' }, '— съответствие —'), ...R.map(r => h('option', { value: r.id, selected: pairs[l.id] === r.id || null }, r.text))); sel.addEventListener('change', () => pairs[l.id] = sel.value); pbox.append(h('div', { class: 'row gap' }, h('span', { class: 'grow' }, l.text), icon('arrow-right'), sel)); } icons(pbox); }
      lE.el.addEventListener('input', drawPairs); rE.el.addEventListener('input', drawPairs); lE.el.addEventListener('click', drawPairs); rE.el.addEventListener('click', drawPairs); drawPairs();
      return { el: h('div', { class: 'stack' }, h('div', { class: 'grid cols-2' }, h('div', {}, h('h4', {}, 'Лява колона'), lE.el), h('div', {}, h('h4', {}, 'Дясна колона (може с излишни)'), rE.el)), h('h4', {}, 'Съответствия'), pbox), collect: () => ({ left: lE.rows().map(r => ({ id: r.id, text: r.text })), right: rE.rows().map(r => ({ id: r.id, text: r.text })), pairs }) };
    },
    grouping(d) {
      const gE = listEditor({ items: (d.groups || [{ id: uid('g'), text: '' }, { id: uid('g'), text: '' }]).map(g => ({ id: g.id, text: g.name || g.text })), placeholder: 'Група' }); const items = (d.items || []).map(i => ({ ...i })); const ibox = h('div', { class: 'editor-rows' });
      function drawItems() { ibox.innerHTML = ''; const G = gE.rows(); items.forEach((it, i) => { const inp = h('input', { type: 'text', value: it.text, placeholder: 'Елемент ' + (i + 1) }); inp.addEventListener('input', () => it.text = inp.value); const sel = h('select', {}, h('option', { value: '' }, '— група —'), ...G.map(g => h('option', { value: g.id, selected: it.group === g.id || null }, g.text))); sel.addEventListener('change', () => it.group = sel.value); ibox.append(h('div', { class: 'editor-row' }, inp, sel, h('button', { type: 'button', class: 'icon-btn sm danger', onClick: () => { items.splice(i, 1); drawItems(); } }, icon('x')))); }); ibox.append(h('button', { type: 'button', class: 'btn sm ghost', onClick: () => { items.push({ id: uid('i'), text: '', group: '' }); drawItems(); } }, icon('plus'), 'Добави елемент')); icons(ibox); }
      gE.el.addEventListener('input', drawItems); gE.el.addEventListener('click', drawItems); drawItems();
      return { el: h('div', { class: 'stack' }, h('div', {}, h('h4', {}, 'Групи'), gE.el), h('div', {}, h('h4', {}, 'Елементи и групата им'), ibox)), collect: () => ({ groups: gE.rows().map(g => ({ id: g.id, name: g.text })), items: items.filter(i => i.text.trim() && i.group).map(i => ({ id: i.id, text: i.text.trim(), group: i.group })) }) };
    },
    numeric(d) {
      const ans = h('input', { type: 'number', step: 'any', value: d.answer ?? '' }), tol = h('input', { type: 'number', step: 'any', min: 0, value: d.tolerance ?? 0 }), unit = h('input', { type: 'text', value: d.unit || '', placeholder: 'm, kg, %' }); const widget = h('select', {}, h('option', { value: 'input' }, 'Поле за число'), h('option', { value: 'slider' }, 'Плъзгач')); widget.value = d.widget || 'input';
      const mn = h('input', { type: 'number', step: 'any', value: d.min ?? '' }), mx = h('input', { type: 'number', step: 'any', value: d.max ?? '' }), st = h('input', { type: 'number', step: 'any', value: d.step ?? '' }); const range = h('div', { class: 'form-grid' + (widget.value === 'slider' ? '' : ' hidden') }, field('Минимум', mn), field('Максимум', mx), field('Стъпка', st)); widget.addEventListener('change', () => range.classList.toggle('hidden', widget.value !== 'slider'));
      return { el: h('div', { class: 'stack' }, h('div', { class: 'form-grid' }, field('Верен отговор', ans), field('Допустимо отклонение (±)', tol), field('Мерна единица', unit), field('Начин на въвеждане', widget)), range), collect: () => ({ answer: ans.value, tolerance: tol.value, unit: unit.value, widget: widget.value, min: mn.value, max: mx.value, step: st.value }) };
    },
    find_errors(d) {
      const text = h('textarea', { rows: 4, placeholder: 'Текст, в който сте допуснали умишлени грешки…' }, d.text || ''); const errors = {}; (d.errors || []).forEach(e => errors[e.index] = e.correct); const box = h('div', { class: 'tokens mt-s' });
      function draw() { box.innerHTML = ''; const toks = text.value.split(/\s+/).filter(Boolean); toks.forEach((t, i) => { const el = h('span', { class: 'tok' + (errors[i] !== undefined ? ' edited' : '') }, t, errors[i] !== undefined ? h('span', { class: 'fix' }, errors[i]) : null); el.addEventListener('click', () => { const v = prompt(`Правилна форма на „${t}“ (празно = не е грешка):`, errors[i] ?? t); if (v === null) return; if (!v.trim() || v.trim() === t) delete errors[i]; else errors[i] = v.trim(); draw(); }); box.append(el, ' '); }); }
      text.addEventListener('input', draw); draw();
      return { el: h('div', {}, field('Текст с грешки', text), h('p', { class: 'subtle' }, 'Кликнете върху дума, за да зададете правилната ѝ форма (вкл. препинателния знак след нея).'), box), collect: () => ({ text: text.value, errors: Object.entries(errors).map(([i, c]) => ({ index: Number(i), correct: c })) }) };
    },
    open(d) { const q = quillEditor(d.model_answer || '', { compact: true, placeholder: 'Модел на отговор / критерии (виждат се само от учителя)' }); const mw = h('input', { type: 'number', min: 0, value: d.min_words || 0 }); return { el: h('div', { class: 'stack' }, field('Модел на отговор (за учителя)', q.el), field('Минимален брой думи (0 = без)', mw)), collect: () => ({ model_answer: q.html(), min_words: mw.value }) }; },
    file_upload(d) { const q = quillEditor(d.instructions || '', { compact: true, placeholder: 'Указания за файла' }); const ext = h('input', { type: 'text', value: (d.allowed_ext || ['pdf', 'jpg', 'png']).join(', ') }); const mb = h('input', { type: 'number', min: 1, max: 50, value: d.max_mb || 10 }); return { el: h('div', { class: 'stack' }, field('Указания', q.el), h('div', { class: 'form-grid' }, field('Разрешени разширения', ext), field('Макс. размер (MB)', mb))), collect: () => ({ instructions: q.html(), allowed_ext: ext.value.split(',').map(s => s.trim()).filter(Boolean), max_mb: mb.value }) }; },
    hotspot(d) {
      let imageUrl = d.image_url || ''; const labels = (d.labels || [{ id: uid('k'), text: '' }, { id: uid('k'), text: '' }]).map(l => ({ ...l })); const markers = (d.markers || []).map(m => ({ ...m }));
      const lE = listEditor({ items: labels, placeholder: 'Наименование', min: 1 }); const imgBox = h('div', { class: 'hotspot-img', style: { cursor: 'crosshair' } }); const mlist = h('div', { class: 'hotspot-list mt-s' });
      function drawImg() { imgBox.innerHTML = ''; if (imageUrl) imgBox.append(h('img', { src: imageUrl, alt: '' })); else imgBox.append(h('div', { class: 'empty' }, icon('image'), h('div', {}, 'Качете изображение'))); markers.forEach((m, i) => imgBox.append(h('span', { class: 'marker', style: { left: m.x + '%', top: m.y + '%' }, title: 'Клик = премахни', onClick: e => { e.stopPropagation(); markers.splice(i, 1); drawImg(); drawList(); } }, i + 1))); icons(imgBox); }
      function drawList() { mlist.innerHTML = ''; const L = lE.rows(); markers.forEach((m, i) => { const sel = h('select', {}, h('option', { value: '' }, '— наименование —'), ...L.map(l => h('option', { value: l.id, selected: m.label_id === l.id || null }, l.text))); sel.addEventListener('change', () => m.label_id = sel.value); mlist.append(h('div', { class: 'hotspot-row' }, h('span', { class: 'mk' }, i + 1), sel)); }); }
      imgBox.addEventListener('click', e => { if (!imageUrl) return; const r = imgBox.getBoundingClientRect(); markers.push({ id: uid('m'), x: +((e.clientX - r.left) / r.width * 100).toFixed(2), y: +((e.clientY - r.top) / r.height * 100).toFixed(2), label_id: '' }); drawImg(); drawList(); });
      lE.el.addEventListener('input', drawList); lE.el.addEventListener('click', drawList);
      const up = h('input', { type: 'file', accept: 'image/*', class: 'hidden' }); up.addEventListener('change', async () => { const f = up.files[0]; if (!f) return; const fd = new FormData(); fd.append('file', f); try { const r = await api('POST', '/api/uploads', fd); imageUrl = r.url; drawImg(); } catch (e) { toast(e.message, 'error'); } });
      drawImg(); drawList();
      return { el: h('div', { class: 'hotspot-wrap' }, h('div', {}, h('div', { class: 'row gap mb-s' }, h('button', { type: 'button', class: 'btn sm', onClick: () => up.click() }, icon('upload'), 'Изображение'), up, h('span', { class: 'subtle' }, 'Кликнете върху картинката, за да добавите маркер')), imgBox), h('div', {}, h('h4', {}, 'Наименования'), lE.el, h('h4', { class: 'mt' }, 'Маркери'), mlist)), collect: () => ({ image_url: imageUrl, labels: lE.rows().map(l => ({ id: l.id, text: l.text })), markers }) };
    },
    reading(d) { return compositeForm(d, 'reading'); },
    listening(d) { return compositeForm(d, 'listening'); },
  };

  function compositeForm(d, kind) {
    const subs = (d.sub_questions || []).map(s => ({ ...s })); const sbox = h('div', { class: 'stack' }); const forms = [];
    let passage = null, audioUrl = d.audio_url || '', transcript = null;
    const head = h('div', { class: 'stack' });
    if (kind === 'reading') { passage = quillEditor(d.passage || '', { placeholder: 'Текст за четене' }); head.append(field('Текст за четене', passage.el)); }
    else { transcript = h('textarea', { rows: 3, placeholder: 'Транскрипция (помага на AI и на учителя)' }, d.transcript || ''); const audioBox = h('div', { class: 'row gap wrap' }); const up = h('input', { type: 'file', accept: 'audio/*', class: 'hidden' }); function drawA() { audioBox.innerHTML = ''; if (audioUrl) audioBox.append(h('audio', { controls: true, src: audioUrl })); audioBox.append(h('button', { type: 'button', class: 'btn sm', onClick: () => up.click() }, icon('upload'), audioUrl ? 'Смени аудио' : 'Качи аудио'), up); icons(audioBox); } up.addEventListener('change', async () => { const f = up.files[0]; if (!f) return; const fd = new FormData(); fd.append('file', f); try { const r = await api('POST', '/api/uploads', fd); audioUrl = r.url; drawA(); } catch (e) { toast(e.message, 'error'); } }); drawA(); head.append(field('Аудио', audioBox), field('Транскрипция', transcript)); }
    function drawSubs() {
      sbox.innerHTML = ''; forms.length = 0;
      subs.forEach((s, i) => {
        const stem = h('input', { type: 'text', value: App.stripHtml(s.stem || ''), placeholder: 'Текст на подвъпроса' });
        const f = FORMS[s.type](s.data || {}); forms.push({ s, stem, f });
        sbox.append(h('div', { class: 'card flat' }, h('div', { class: 'row gap mb-s' }, h('span', { class: 'badge primary' }, `${i + 1}. ${TYPE_META[s.type]?.label || s.type}`), h('span', { class: 'grow' }), h('label', { class: 'row gap small' }, 'Точки', h('input', { type: 'number', min: 0.25, step: 0.25, value: s.points || 1, class: 'sm', style: { width: '70px' }, onInput: e => s.points = e.target.value })), h('button', { type: 'button', class: 'icon-btn sm danger', onClick: () => { subs.splice(i, 1); drawSubs(); } }, icon('x'))), field('Подвъпрос', stem), h('div', { class: 'mt-s' }, f.el)));
      });
      const sel = h('select', {}, ...SUB_TYPES.map(t => h('option', { value: t }, TYPE_META[t]?.label || t)));
      sbox.append(h('div', { class: 'row gap' }, sel, h('button', { type: 'button', class: 'btn sm', onClick: () => { subs.push({ id: uid('q'), type: sel.value, stem: '', points: 1, data: {} }); drawSubs(); } }, icon('plus'), 'Добави подвъпрос')));
      icons(sbox);
    }
    drawSubs();
    return { el: h('div', { class: 'stack' }, head, h('h4', {}, 'Подвъпроси'), sbox), collect: () => { const out = { sub_questions: forms.map(({ s, stem, f }) => ({ id: s.id, type: s.type, stem: '<p>' + App.esc(stem.value) + '</p>', points: s.points || 1, data: f.collect() })) }; if (kind === 'reading') out.passage = passage.html(); else { out.audio_url = audioUrl; out.transcript = transcript.value; } return out; } };
  }

  function topicSelect(curriculumSel, value) {
    const sel = h('select', {});
    function fill() { const opt = curriculumSel.selectedOptions[0]; let topics = []; try { topics = JSON.parse(opt?.dataset.topics || '[]'); } catch (e) {} sel.innerHTML = ''; sel.append(h('option', { value: '' }, '— тема —'), ...topics.map(t => h('option', { value: t, selected: t === value || null }, t))); if (value && !topics.includes(value)) sel.append(h('option', { value, selected: true }, value)); }
    curriculumSel.addEventListener('change', fill); fill(); return sel;
  }

  /* Отваря редактора. opts: { question?, type?, testId?, sectionKey?, curriculumId?, onSave(q) } */
  function open(opts = {}) {
    const q = opts.question || { type: opts.type || 'single_choice', stem: '', data: {}, difficulty: 2, points: 1, curriculum_id: opts.curriculumId || null, topic: '' };
    let type = q.type;
    const curTpl = document.getElementById('curriculumOptions'); const cur = curTpl ? curTpl.cloneNode(true) : h('select'); cur.id = ''; cur.classList.remove('hidden'); cur.value = q.curriculum_id || '';
    const topic = topicSelect(cur, q.topic || '');
    const diff = h('select', {}, h('option', { value: 1 }, 'Ниска трудност'), h('option', { value: 2 }, 'Средна трудност'), h('option', { value: 3 }, 'Висока трудност')); diff.value = q.difficulty || 2;
    const pts = h('input', { type: 'number', min: 0.25, step: 0.25, value: q.points || 1 });
    const stem = quillEditor(q.stem || '', { placeholder: 'Условие на въпроса… (бутон ƒx за формула)' });
    const typeSel = h('select', {}, ...Object.entries(TYPE_META).map(([k, m]) => h('option', { value: k, selected: k === type || null }, m.label)));
    const formBox = h('div'); let form = FORMS[type](q.data || {}); formBox.append(form.el);
    typeSel.addEventListener('change', () => { type = typeSel.value; form = FORMS[type]({}); formBox.innerHTML = ''; formBox.append(form.el); icons(formBox); });
    const body = h('div', { class: 'stack' },
      h('div', { class: 'form-grid' }, field('Тип на въпроса', typeSel), field('Учебна програма', cur), field('Тема', topic), h('div', { class: 'form-grid' }, field('Трудност', diff), field('Точки', pts))),
      field('Условие', stem.el), h('h4', {}, 'Съдържание'), formBox);
    const m = modal({ title: q.id ? 'Редакция на въпрос' : 'Нов въпрос', iconName: 'pencil', wide: true, body,
      footer: [h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Отказ'), h('button', { class: 'btn primary', onClick: save }, icon('save'), 'Запази')] });
    async function save() {
      const payload = { type, stem: stem.html(), data: form.collect(), difficulty: Number(diff.value), points: Number(pts.value || 1), curriculum_id: cur.value ? Number(cur.value) : null, topic: topic.value, section_key: opts.sectionKey || q.section_key || null };
      if (!payload.stem && !['reading', 'listening'].includes(type)) return toast('Въведете условие на въпроса', 'error');
      try {
        let saved;
        if (q.id) saved = await api('PUT', `/api/questions/${q.id}`, payload);
        else if (opts.testId) saved = await api('POST', `/api/tests/${opts.testId}/questions`, payload);
        else saved = await api('POST', '/api/bank', payload);
        m.close(); toast('Въпросът е запазен', 'success'); opts.onSave && opts.onSave(saved);
      } catch (e) { toast(e.message, 'error'); }
    }
  }

  /* Преглед на въпрос (как го вижда ученикът + верни отговори) */
  function preview(q) {
    const key = (window.Questions && typeof answerKey === 'function') ? answerKey(q) : null;
    const body = h('div', {}, Questions.renderCard(q, { key: q.id, n: q.position + 1 || 1, response: key, review: !!key, teacherView: true, final_score: q.points, onChange: () => {} }));
    modal({ title: 'Преглед на въпроса', iconName: 'eye', wide: true, body });
  }
  function answerKey(q) {
    const d = q.data; switch (q.type) {
      case 'single_choice': return d.correct; case 'multi_choice': return d.correct;
      case 'true_false': return Object.fromEntries(d.statements.map(s => [s.id, s.answer]));
      case 'dropdown_blank': return Object.fromEntries(Object.entries(d.blanks).map(([k, b]) => [k, b.correct]));
      case 'fill_blank': return Object.fromEntries(Object.entries(d.blanks).map(([k, b]) => [k, b.answers[0]]));
      case 'ordering': return d.correct_order; case 'matching': return d.pairs;
      case 'grouping': return Object.fromEntries(d.items.map(i => [i.id, i.group]));
      case 'numeric': return d.answer; case 'find_errors': return Object.fromEntries(d.errors.map(e => [String(e.index), e.correct]));
      case 'hotspot': return Object.fromEntries(d.markers.map(m => [m.id, m.label_id]));
      case 'open': return { text: d.model_answer }; case 'file_upload': return null;
      case 'reading': case 'listening': return Object.fromEntries(d.sub_questions.map(sq => [sq.id, answerKey(sq)]));
      default: return null;
    }
  }

  window.Editor = { open, preview, TYPE_META, answerKey };
})();
