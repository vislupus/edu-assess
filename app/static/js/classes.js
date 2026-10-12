/* Класове: списък, създаване, добавяне/премахване на ученици. */
(function () {
  const { h, icon, icons, api, toast, modal, confirmDialog, promptDialog } = App;

  function curriculumSelect(selected) {
    const tpl = document.getElementById('curriculumOptions'); const sel = tpl.cloneNode(true); sel.id = ''; sel.classList.remove('hidden'); if (selected !== undefined) sel.value = selected || ''; return sel;
  }

  async function createClass() {
    const name = h('input', { type: 'text', placeholder: 'напр. 8б – Математика' }); const cur = curriculumSelect();
    const m = modal({ title: 'Нов клас', iconName: 'school', narrow: true, body: h('div', { class: 'stack' }, h('label', { class: 'field' }, 'Име на класа', name), h('label', { class: 'field' }, 'Учебна програма', cur)),
      footer: [h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Отказ'), h('button', { class: 'btn primary', onClick: async () => { if (!name.value.trim()) return name.focus(); try { const c = await api('POST', '/api/classes', { name: name.value, curriculum_id: cur.value ? Number(cur.value) : null }); m.close(); location.href = `/classes/${c.id}`; } catch (e) { toast(e.message, 'error'); } } }, 'Създай')] });
    setTimeout(() => name.focus(), 50);
  }

  async function listPage() {
    const root = document.getElementById('classList'); if (!root) return;
    document.getElementById('newClassBtn').addEventListener('click', createClass);
    const list = await api('GET', '/api/classes');
    root.innerHTML = '';
    if (!list.length) { root.append(h('div', { class: 'card empty', style: { gridColumn: '1 / -1' } }, icon('users'), h('h3', {}, 'Нямате класове'), h('p', {}, 'Създайте клас и добавете ученици.'))); icons(root); return; }
    for (const c of list) root.append(h('a', { class: 'tile', href: `/classes/${c.id}` }, h('div', { class: 'tile-title' }, icon('school'), c.name), h('div', { class: 'tile-sub' }, `${c.student_count} ученици · ${c.subject || ''} · код ${c.join_code}`)));
    icons(root);
  }

  async function detailPage() {
    const card = document.getElementById('studentsCard'); if (!card) return;
    const cid = Number(card.dataset.class); const box = document.getElementById('students');
    let data = await api('GET', `/api/classes/${cid}`);
    function draw() {
      box.innerHTML = ''; document.getElementById('studentCount').textContent = data.students.length;
      if (!data.students.length) { box.append(h('p', { class: 'muted' }, 'Няма ученици. Добавете от бутона горе.')); return; }
      const list = h('div', { class: 'list' });
      for (const s of data.students) list.append(h('div', { class: 'list-item' }, h('span', { class: 'avatar', style: { '--c': s.avatar_color } }, s.initials), h('div', { class: 'body' }, h('div', { class: 'title' }, s.full_name), h('div', { class: 'meta' }, h('span', {}, `${s.grade_label} клас`), h('span', {}, s.username))), h('button', { class: 'icon-btn danger', title: 'Премахни от класа', onClick: async () => { if (!await confirmDialog(`Премахване на ${s.full_name} от класа?`, { danger: true, okText: 'Премахни' })) return; data = await api('DELETE', `/api/classes/${cid}/students/${s.id}`); draw(); } }, icon('user-minus'))));
      box.append(list); icons(box);
    }
    draw();
    document.getElementById('addStudentsBtn').addEventListener('click', async () => {
      const all = await api('GET', '/api/students'); const inClass = new Set(data.students.map(s => s.id));
      const chosen = new Set(); const search = h('input', { type: 'search', placeholder: 'Търсене по име…' });
      const list = h('div', { class: 'list' });
      function drawList() {
        list.innerHTML = ''; const q = search.value.toLowerCase();
        const groups = {};
        for (const s of all) { if (inClass.has(s.id)) continue; if (q && !s.full_name.toLowerCase().includes(q)) continue; (groups[s.grade_label] ||= []).push(s); }
        if (!Object.keys(groups).length) list.append(h('p', { class: 'muted' }, 'Няма налични ученици.'));
        for (const [g, students] of Object.entries(groups)) {
          list.append(h('div', { class: 'grade-label' }, icon('school'), `${g} клас`, h('button', { class: 'btn sm ghost', style: { marginLeft: 'auto' }, onClick: () => { students.forEach(s => chosen.add(s.id)); drawList(); } }, 'Избери всички')));
          for (const s of students) { const cb = h('input', { type: 'checkbox', checked: chosen.has(s.id) || null }); cb.addEventListener('change', () => cb.checked ? chosen.add(s.id) : chosen.delete(s.id)); list.append(h('label', { class: 'list-item', style: { cursor: 'pointer' } }, cb, h('span', { class: 'avatar sm', style: { '--c': s.avatar_color } }, s.initials), h('span', { class: 'body' }, s.full_name))); }
        }
        icons(list);
      }
      search.addEventListener('input', drawList); drawList();
      const m = modal({ title: 'Добавяне на ученици', iconName: 'user-plus', body: h('div', { class: 'stack' }, h('div', { class: 'search' }, icon('search'), search), list),
        footer: [h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Отказ'), h('button', { class: 'btn primary', onClick: async () => { if (!chosen.size) return toast('Изберете ученици'); data = await api('POST', `/api/classes/${cid}/students`, { student_ids: [...chosen] }); m.close(); draw(); toast(`Добавени: ${chosen.size}`, 'success'); } }, 'Добави')] });
    });
    document.getElementById('renameBtn').addEventListener('click', async () => {
      const name = await promptDialog('Преименуване на класа', { label: 'Име', value: data.name }); if (!name || !name.trim()) return;
      const cur = document.getElementById('curriculumOptions').value;
      data = await api('PATCH', `/api/classes/${cid}`, { name, curriculum_id: cur ? Number(cur) : null }); document.getElementById('className').textContent = data.name; toast('Запазено', 'success');
    });
    document.getElementById('deleteClassBtn').addEventListener('click', async () => {
      if (!await confirmDialog('Изтриване на класа? Заданията към него ще останат, но учениците ще загубят достъп.', { danger: true, okText: 'Изтрий' })) return;
      try { await api('DELETE', `/api/classes/${cid}`); location.href = '/classes'; } catch (e) { toast(e.message, 'error'); }
    });
  }
  document.addEventListener('DOMContentLoaded', () => { listPage(); detailPage(); });
})();
