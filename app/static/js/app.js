/* Общи помощни функции: DOM, API, икони, формули, тостове, модални прозорци. */
(function () {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function h(tag, attrs = {}, ...children) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k === 'html') el.innerHTML = v;
      else if (k === 'text') el.textContent = v;
      else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
      else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v);
      else if (k === 'dataset') Object.assign(el.dataset, v);
      else if (v === true) el.setAttribute(k, '');
      else el.setAttribute(k, v);
    }
    for (const c of children.flat(Infinity)) {
      if (c === null || c === undefined || c === false) continue;
      el.append(c instanceof Node ? c : document.createTextNode(String(c)));
    }
    return el;
  }
  const icon = (name, cls = '') => h('i', { 'data-lucide': name, class: cls });
  function icons(root) { if (window.lucide) lucide.createIcons({ attrs: { 'stroke-width': 2 } }); }
  function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }

  function renderMath(root = document) {
    if (!window.katex) return;
    root.querySelectorAll('.ql-formula[data-value]').forEach(el => {
      if (el.dataset.rendered) return;
      try { katex.render(el.dataset.value, el, { throwOnError: false }); el.dataset.rendered = '1'; } catch (e) {}
    });
    if (window.renderMathInElement) {
      try {
        renderMathInElement(root, {
          delimiters: [{ left: '$$', right: '$$', display: true }, { left: '$', right: '$', display: false }, { left: '\\(', right: '\\)', display: false }, { left: '\\[', right: '\\]', display: true }],
          throwOnError: false, ignoredClasses: ['ql-formula', 'no-math', 'ql-editor'],
        });
      } catch (e) {}
    }
  }
  /* Текст с $…$ формули → HTML (escape + KaTeX) */
  function mathText(text) {
    const span = h('span', { class: 'mtext' });
    span.textContent = text ?? '';
    renderMath(span);
    return span;
  }
  function htmlBlock(html, cls = '') { const d = h('div', { class: cls }); d.innerHTML = html || ''; renderMath(d); return d; }

  async function api(method, url, body, opts = {}) {
    const init = { method, headers: { Accept: 'application/json' }, credentials: 'same-origin' };
    if (body instanceof FormData) init.body = body;
    else if (body !== undefined) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(body); }
    const res = await fetch(url, init);
    if (res.status === 204) return null;
    let data = null;
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) data = await res.json(); else data = await res.text();
    if (!res.ok) {
      const msg = (data && data.detail) ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : `Грешка ${res.status}`;
      const err = new Error(msg); err.status = res.status; err.data = data; throw err;
    }
    return data;
  }

  function toast(msg, type = '', ms = 3200) {
    const box = $('#toasts'); if (!box) return;
    const t = h('div', { class: `toast ${type}` }, icon(type === 'success' ? 'check-circle-2' : type === 'error' ? 'alert-circle' : 'info'), h('span', {}, msg));
    box.append(t); icons(t);
    setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity .3s'; setTimeout(() => t.remove(), 300); }, ms);
  }

  /* Модален прозорец: modal({title, body(Node|string), footer:[buttons], wide}) → {el, close} */
  function modal({ title, body, footer = [], wide = false, narrow = false, onClose, iconName }) {
    const dlg = h('dialog', { class: `modal ${wide ? 'wide' : ''} ${narrow ? 'narrow' : ''}` });
    const closeBtn = h('button', { class: 'icon-btn', type: 'button', onClick: () => close() }, icon('x'));
    const head = h('div', { class: 'modal-head' }, h('h3', {}, iconName ? icon(iconName) : null, title), closeBtn);
    const bodyEl = h('div', { class: 'modal-body' }); if (typeof body === 'string') bodyEl.innerHTML = body; else if (body) bodyEl.append(body);
    const foot = h('div', { class: 'modal-foot' }, ...footer);
    dlg.append(head, bodyEl, footer.length ? foot : '');
    document.body.append(dlg);
    function close(v) { try { dlg.close(); } catch (e) {} dlg.remove(); onClose && onClose(v); }
    dlg.addEventListener('cancel', e => { e.preventDefault(); close(); });
    dlg.addEventListener('click', e => { if (e.target === dlg) close(); });
    dlg.showModal(); icons(dlg); renderMath(bodyEl);
    return { el: dlg, body: bodyEl, close };
  }
  function confirmDialog(msg, { okText = 'Потвърди', danger = false, title = 'Потвърждение' } = {}) {
    return new Promise(resolve => {
      const m = modal({
        title, narrow: true, iconName: danger ? 'alert-triangle' : 'help-circle',
        body: h('p', {}, msg),
        footer: [h('button', { class: 'btn ghost', onClick: () => m.close(false) }, 'Отказ'), h('button', { class: `btn ${danger ? 'danger' : 'primary'}`, onClick: () => m.close(true) }, okText)],
        onClose: v => resolve(!!v),
      });
    });
  }
  function promptDialog(title, { label = '', value = '', placeholder = '', okText = 'Запази' } = {}) {
    return new Promise(resolve => {
      const input = h('input', { type: 'text', value, placeholder });
      const m = modal({
        title, narrow: true, body: h('label', { class: 'field' }, label, input),
        footer: [h('button', { class: 'btn ghost', onClick: () => m.close(null) }, 'Отказ'), h('button', { class: 'btn primary', onClick: () => m.close(input.value) }, okText)],
        onClose: v => resolve(v),
      });
      input.addEventListener('keydown', e => { if (e.key === 'Enter') m.close(input.value); });
      setTimeout(() => input.focus(), 50);
    });
  }

  const MONTHS = ['ян.', 'февр.', 'март', 'апр.', 'май', 'юни', 'юли', 'авг.', 'септ.', 'окт.', 'ноем.', 'дек.'];
  function fmtDate(iso, withTime = true) {
    if (!iso) return '–';
    const d = new Date(iso); if (isNaN(d)) return '–';
    let s = `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
    if (withTime) s += `, ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
    return s;
  }
  function toLocalInput(iso) { if (!iso) return ''; const d = new Date(iso); const p = n => String(n).padStart(2, '0'); return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`; }
  function fmtDuration(sec) { sec = Math.max(0, Math.floor(sec)); const m = Math.floor(sec / 60), s = sec % 60; const hh = Math.floor(m / 60); return hh ? `${hh}:${String(m % 60).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`; }
  function pctClass(p) { return p >= 75 ? 'good' : p >= 50 ? 'mid' : 'bad'; }
  function diffBadge(d) { const lab = { 1: 'Ниска', 2: 'Средна', 3: 'Висока' }[d] || ''; return h('span', { class: `diff diff-${d}` }, h('span', { class: 'bars' }, h('i'), h('i'), h('i')), lab + ' трудност'); }
  function shuffle(arr) { const a = arr.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }
  function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }
  function stripHtml(html) { const d = document.createElement('div'); d.innerHTML = html || ''; d.querySelectorAll('.ql-formula').forEach(f => f.replaceWith('$' + (f.dataset.value || '') + '$')); return d.textContent.trim(); }

  /* Навигация на мобилни */
  document.addEventListener('DOMContentLoaded', () => {
    const t = $('#navToggle'); if (t) t.addEventListener('click', () => document.body.classList.toggle('nav-open'));
    document.addEventListener('click', e => { if (document.body.classList.contains('nav-open') && !e.target.closest('#sidebar') && !e.target.closest('#navToggle')) document.body.classList.remove('nav-open'); });
    icons(); renderMath(document.body);
  });

  window.App = { $, $$, h, icon, icons, esc, renderMath, mathText, htmlBlock, api, toast, modal, confirmDialog, promptDialog, fmtDate, toLocalInput, fmtDuration, pctClass, diffBadge, shuffle, debounce, stripHtml };
})();
