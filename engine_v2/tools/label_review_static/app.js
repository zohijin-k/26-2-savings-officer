'use strict';
// Label review screen. Talks only to this local server; no external resources.
(function () {
  const STATE_NAMES = { PASS: '적합', NEEDS_REVIEW: '확인 필요', FAIL: '재업로드', HOLD: '보류' };
  const DECISION_NAMES = { PASS: '적합', NEEDS_REVIEW: '확인 필요', FAIL: '재업로드', NOT_ASSESSED: '미판정', ERROR: '오류' };
  const STATE_KEYS = { '1': 'PASS', '2': 'NEEDS_REVIEW', '3': 'FAIL', '0': 'HOLD' };
  const REASON_KEYS = { q: 'R1', w: 'R2', e: 'R3', r: 'R4', t: 'R5', y: 'R6', u: 'R9' };
  const ZOOMS = [0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3];

  const $ = (id) => document.getElementById(id);
  const app = {
    token: null, session: null, mode: 'main', index: 0, doc: null,
    page: 0, zoom: 2, status: null, reasons: new Set(), saved: null,
    stage2: false, engine: null, values: null, focus: 0, marks: {}, busy: false, checks: {},
  };

  async function api(method, url, body) {
    const options = { method, headers: {}, cache: 'no-store', credentials: 'same-origin' };
    if (body !== undefined) {
      options.headers['Content-Type'] = 'application/json';
      options.headers['X-Label-Token'] = app.token;
      options.body = JSON.stringify(body);
    }
    const response = await fetch(url, options);
    let data = null;
    try { data = await response.json(); } catch (e) { data = null; }
    if (!response.ok) {
      const code = data && typeof data.error === 'string' ? data.error : 'HTTP_' + response.status;
      throw new Error(code);
    }
    return data;
  }

  function queue() {
    if (!app.session) return [];
    return app.mode === 'cross' ? app.session.cross : app.session.queue;
  }

  function docUrl(key) {
    return (app.mode === 'cross' ? '/api/cross/' : '/api/doc/') + key;
  }

  function setMsg(id, text, error) {
    const el = $(id);
    el.textContent = text || '';
    el.classList.toggle('error', !!error);
  }

  // ------------------------------------------------------------ session

  async function refresh() {
    app.session = await api('GET', '/api/session');
    app.token = app.session.token;
    renderBar();
  }

  function renderBar() {
    const s = app.session;
    const q = queue();
    $('mode-main').classList.toggle('active', app.mode === 'main');
    $('mode-cross').classList.toggle('active', app.mode === 'cross');
    if (app.mode === 'main') {
      const blind = s.queue.filter((d) => d.state !== 'todo').length;
      const done = s.queue.filter((d) => d.state === 'complete').length;
      let text = `1단계 ${blind}/${s.queue.length} · 완료 ${done}/${s.queue.length} · 회차 ${s.round}`;
      if (s.missing) text += ` · 원본 없음 ${s.missing}`;
      $('progress').textContent = text;
    } else {
      const done = s.cross.filter((d) => d.state === 'complete').length;
      $('progress').textContent = s.cross_started ? `교차 확인 ${done}/${s.cross.length}` : '교차 확인 시작 전';
    }
    $('position').textContent = q.length && app.doc ? `순번 ${app.index + 1} / ${q.length}` : '-';
  }

  function firstOpen() {
    const q = queue();
    const i = q.findIndex((d) => d.state !== 'complete');
    return i >= 0 ? i : Math.max(0, q.length - 1);
  }

  // ------------------------------------------------------------ document

  async function openDoc(i) {
    const q = queue();
    if (!q.length) { clearDoc(); return; }
    app.index = Math.min(Math.max(i, 0), q.length - 1);
    const key = q[app.index].key;
    app.busy = true;
    try {
      app.doc = await api('GET', docUrl(key));
    } catch (e) {
      notice('문서를 열 수 없습니다: ' + e.message);
      app.busy = false;
      return;
    }
    app.busy = false;
    notice('');
    app.page = 0;
    app.saved = app.doc.label;
    app.status = app.saved ? app.saved.status : null;
    app.reasons = new Set(app.saved ? app.saved.reasons : []);
    $('form-label').textContent = app.doc.form_label + ' (' + app.doc.form + ')';
    $('cutoff').textContent = cutoffText(app.doc.cutoff);
    checkList($('checks'), (app.checks[app.doc.form] || {}).items);
    $('stage1').hidden = false;
    $('cross-start-box').hidden = true;
    setMsg('blind-msg', app.saved ? '저장됨 · 고치려면 다시 고르고 저장' : '');
    renderChoices();
    showPage();
    hideStage2();
    renderBar();
    if (app.mode === 'main' && app.saved) await showStage2();
  }

  function clearDoc() {
    app.doc = null;
    $('page').removeAttribute('src');
    $('page-info').textContent = '-';
    $('form-label').textContent = '-';
    $('cutoff').textContent = '-';
    $('checks').textContent = '';
    hideStage2();
    renderBar();
  }

  function checkList(target, items) {
    target.textContent = '';
    (items || []).forEach((item) => {
      const li = document.createElement('li');
      li.appendChild(document.createTextNode(item.text));
      if (item.codes.length) {
        const tag = document.createElement('span');
        tag.className = 'codes-tag';
        tag.textContent = item.codes.join(' ');
        li.appendChild(tag);
      }
      const source = document.createElement('span');
      source.className = 'source';
      source.textContent = '출처: ' + item.source;
      li.appendChild(source);
      target.appendChild(li);
    });
  }

  function renderAllChecks() {
    const box = $('all-checks');
    box.textContent = '';
    Object.keys(app.checks).forEach((form) => {
      const head = document.createElement('h4');
      head.textContent = '서식별 확인할 것 · ' + app.checks[form].label;
      const list = document.createElement('ul');
      list.className = 'checks';
      checkList(list, app.checks[form].items);
      box.append(head, list);
    });
  }

  function cutoffText(c) {
    if (!c || c.basis === 'none' || (!c.min && !c.max)) return '기준 없음';
    const basis = { issue_date: '발급일', payment_date: '결제일', interview_date: '면접일', exam_date: '응시일' }[c.basis] || c.basis;
    const parts = [];
    if (c.min) parts.push(`${c.min} 이후`);
    if (c.max) parts.push(`${c.max} 이전`);
    return `${basis} ${parts.join(', ')}`;
  }

  function showPage() {
    if (!app.doc) return;
    const s = app.zoom >= 1.5 ? 3 : 2;
    $('page').src = `/api/doc/${app.doc.key}/page/${app.page}?s=${s}`;
    $('page').style.width = (ZOOMS[app.zoom] * 100) + '%';
    $('page-info').textContent = `${app.page + 1} / ${app.doc.pages} 쪽`;
    $('zoom-info').textContent = Math.round(ZOOMS[app.zoom] * 100) + '%';
  }

  function movePage(step) {
    if (!app.doc) return;
    const next = app.page + step;
    if (next < 0 || next >= app.doc.pages) return;
    app.page = next;
    showPage();
    $('page-box').scrollTop = 0;
  }

  function setZoom(index) {
    app.zoom = Math.min(Math.max(index, 0), ZOOMS.length - 1);
    showPage();
  }

  // ------------------------------------------------------------ stage 1

  function renderChoices() {
    document.querySelectorAll('#states .state').forEach((b) => b.classList.toggle('on', b.dataset.state === app.status));
    const fail = app.status === 'FAIL';
    $('reasons').classList.toggle('disabled', !fail);
    document.querySelectorAll('#reasons .reason').forEach((b) => {
      b.disabled = !fail;
      b.classList.toggle('on', fail && app.reasons.has(b.dataset.reason));
    });
  }

  function dirty() {
    if (!app.saved) return true;
    const now = [...app.reasons].sort().join(',');
    return app.saved.status !== app.status || app.saved.reasons.join(',') !== (app.status === 'FAIL' ? now : '');
  }

  function chooseState(state) {
    if (!app.doc) return;
    app.status = state;
    if (state !== 'FAIL') app.reasons.clear();
    renderChoices();
  }

  function toggleReason(code) {
    if (!app.doc || app.status !== 'FAIL') return;
    if (app.reasons.has(code)) app.reasons.delete(code); else app.reasons.add(code);
    renderChoices();
  }

  async function saveBlind() {
    if (!app.doc || app.busy) return;
    if (!app.status) { setMsg('blind-msg', '정답 상태를 고르세요', true); return; }
    if (app.status === 'FAIL' && !app.reasons.size) { setMsg('blind-msg', '재업로드 근거를 하나 이상 고르세요', true); return; }
    const reasons = app.status === 'FAIL' ? [...app.reasons].sort() : [];
    app.busy = true;
    try {
      await api('POST', docUrl(app.doc.key) + (app.mode === 'cross' ? '' : '/blind'), { status: app.status, reasons });
      app.saved = { status: app.status, reasons };
      setMsg('blind-msg', '저장됨');
      await refresh();
    } catch (e) {
      setMsg('blind-msg', '저장 실패: ' + e.message, true);
      app.busy = false;
      return;
    }
    app.busy = false;
    if (app.mode === 'cross') { await nextTodo(); return; }
    await showStage2();
  }

  // ------------------------------------------------------------ stage 2

  function hideStage2() {
    app.stage2 = false;
    app.engine = null;
    app.values = null;
    app.marks = {};
    $('stage2').hidden = true;
    $('values-box').hidden = true;
    $('save-values').hidden = true;
    $('go-next').hidden = true;
    setMsg('values-msg', '');
  }

  async function showStage2() {
    const key = app.doc.key;
    try {
      app.engine = await api('GET', `/api/doc/${key}/engine`);
    } catch (e) {
      setMsg('blind-msg', '엔진 판정을 불러오지 못했습니다: ' + e.message, true);
      return;
    }
    if (!app.doc || app.doc.key !== key) return;
    app.stage2 = true;
    $('stage2').hidden = false;
    const d = app.engine.decision;
    const el = $('engine-decision');
    el.textContent = (DECISION_NAMES[d] || d) + ' (' + d + ')';
    el.className = 'decision-' + d;
    const list = $('engine-reasons');
    list.textContent = '';
    if (!app.engine.reasons.length) {
      const li = document.createElement('li');
      li.textContent = '없음';
      list.appendChild(li);
    }
    app.engine.reasons.forEach(([code, severity]) => {
      const li = document.createElement('li');
      li.textContent = `${code} · ${severity}`;
      list.appendChild(li);
    });
    if (app.engine.needs_values) {
      $('values-box').hidden = false;
      $('go-next').hidden = true;
      await loadValues(key);
    } else {
      $('values-box').hidden = true;
      $('go-next').hidden = false;
    }
  }

  async function loadValues(key) {
    $('values-status').textContent = '서비스 경로로 다시 읽는 중…';
    $('values').querySelector('tbody').textContent = '';
    $('unread').textContent = '';
    $('save-values').hidden = true;
    let data;
    try {
      data = await api('GET', `/api/doc/${key}/values`);
    } catch (e) {
      $('values-status').textContent = '값 계산 실패: ' + e.message;
      return;
    }
    if (!app.doc || app.doc.key !== key) return;
    app.values = data;
    app.marks = {};
    data.items.forEach((item) => { if (item.mark) app.marks[item.name] = item.mark; });
    app.focus = Math.max(0, data.items.findIndex((item) => !app.marks[item.name]));
    const r = data.recomputed;
    $('values-status').textContent = (r.same === 'O'
      ? '다시 계산한 판정·서식이 측정 결과와 같습니다.'
      : `주의: 다시 계산한 결과(${r.decision}, ${r.form})가 측정 결과와 다릅니다.`) + ` 판독 계층: ${r.tier}`;
    $('unread').textContent = data.unread.length ? '엔진이 읽지 못한 항목: ' + data.unread.join(', ') : '';
    renderValues();
    if (!data.items.length) {
      setMsg('values-msg', '대조할 값이 없습니다', true);
      $('go-next').hidden = false;
    } else {
      $('save-values').hidden = false;
    }
  }

  function renderValues() {
    const body = $('values').querySelector('tbody');
    body.textContent = '';
    app.values.items.forEach((item, i) => {
      const tr = document.createElement('tr');
      if (i === app.focus) tr.className = 'focus';
      const name = document.createElement('td');
      name.textContent = item.name;
      const value = document.createElement('td');
      value.className = 'value';
      value.textContent = item.value;
      const marks = document.createElement('td');
      marks.className = 'marks';
      ['O', 'X'].forEach((m) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.textContent = m;
        if (app.marks[item.name] === m) b.className = 'on-' + m;
        b.addEventListener('click', () => { app.focus = i; mark(m); });
        marks.appendChild(b);
      });
      tr.append(name, value, marks);
      body.appendChild(tr);
    });
    const row = body.children[app.focus];
    if (row) row.scrollIntoView({ block: 'nearest' });
  }

  function mark(m) {
    if (!app.values || !app.values.items.length) return;
    const item = app.values.items[app.focus];
    app.marks[item.name] = m;
    if (app.focus < app.values.items.length - 1) app.focus += 1;
    renderValues();
  }

  function moveFocus(step) {
    if (!app.values || !app.values.items.length) return;
    app.focus = Math.min(Math.max(app.focus + step, 0), app.values.items.length - 1);
    renderValues();
  }

  async function saveValues() {
    if (!app.values || app.busy) return;
    const missing = app.values.items.filter((item) => !app.marks[item.name]);
    if (missing.length) {
      setMsg('values-msg', `O/X를 모두 고르세요 (남은 ${missing.length})`, true);
      app.focus = app.values.items.indexOf(missing[0]);
      renderValues();
      return;
    }
    const fields = {};
    app.values.items.forEach((item) => { fields[item.name] = app.marks[item.name]; });
    app.busy = true;
    try {
      await api('POST', `/api/doc/${app.doc.key}/values`, { fields });
      await refresh();
    } catch (e) {
      setMsg('values-msg', '저장 실패: ' + e.message, true);
      app.busy = false;
      return;
    }
    app.busy = false;
    await nextTodo();
  }

  // ------------------------------------------------------------ navigation

  async function nextTodo() {
    const q = queue();
    if (!q.length) return;
    for (let step = 1; step <= q.length; step += 1) {
      const i = (app.index + step) % q.length;
      if (q[i].state !== 'complete') { await openDoc(i); return; }
    }
    if (app.mode === 'main') notice('모든 문서의 라벨을 마쳤습니다. 요약 명령으로 숫자를 확인하세요.');
    else notice('교차 확인을 모두 마쳤습니다.');
  }

  function notice(text) {
    $('notice').hidden = !text;
    $('notice').textContent = text || '';
  }

  async function setMode(mode) {
    app.mode = mode;
    hideStage2();
    await refresh();
    if (mode === 'cross' && !app.session.cross_started) {
      clearDoc();
      $('stage1').hidden = true;
      $('cross-start-box').hidden = false;
      $('cross-start').disabled = !app.session.main_complete;
      setMsg('cross-msg', app.session.main_complete ? '' : '본 라벨을 모두 마친 뒤 시작할 수 있습니다.');
      return;
    }
    $('cross-start-box').hidden = true;
    await openDoc(firstOpen());
  }

  async function startCross() {
    try {
      await api('POST', '/api/cross/start', {});
    } catch (e) {
      setMsg('cross-msg', '시작 실패: ' + e.message, true);
      return;
    }
    await setMode('cross');
  }

  async function enter() {
    if (!app.doc) return;
    if (app.mode === 'cross' || !app.stage2 || dirty()) { await saveBlind(); return; }
    if (app.engine && app.engine.needs_values && app.values && app.values.items.length) { await saveValues(); return; }
    await nextTodo();
  }

  // ------------------------------------------------------------ wiring

  document.querySelectorAll('#states .state').forEach((b) => b.addEventListener('click', () => chooseState(b.dataset.state)));
  document.querySelectorAll('#reasons .reason').forEach((b) => b.addEventListener('click', () => toggleReason(b.dataset.reason)));
  $('save-blind').addEventListener('click', saveBlind);
  $('save-values').addEventListener('click', saveValues);
  $('go-next').addEventListener('click', nextTodo);
  $('prev-doc').addEventListener('click', () => openDoc(app.index - 1));
  $('next-doc').addEventListener('click', () => openDoc(app.index + 1));
  $('next-todo').addEventListener('click', nextTodo);
  $('page-prev').addEventListener('click', () => movePage(-1));
  $('page-next').addEventListener('click', () => movePage(1));
  $('zoom-in').addEventListener('click', () => setZoom(app.zoom + 1));
  $('zoom-out').addEventListener('click', () => setZoom(app.zoom - 1));
  $('zoom-fit').addEventListener('click', () => setZoom(2));
  $('mode-main').addEventListener('click', () => setMode('main'));
  $('mode-cross').addEventListener('click', () => setMode('cross'));
  $('cross-start').addEventListener('click', startCross);

  document.addEventListener('keydown', (event) => {
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
    const inValues = app.stage2 && app.values && app.values.items.length && !dirty();
    let handled = true;
    if (key in STATE_KEYS) chooseState(STATE_KEYS[key]);
    else if (inValues && key === 'o') mark('O');
    else if (inValues && key === 'x') mark('X');
    else if (inValues && key === 'ArrowDown') moveFocus(1);
    else if (inValues && key === 'ArrowUp') moveFocus(-1);
    else if (key in REASON_KEYS) toggleReason(REASON_KEYS[key]);
    else if (key === 'Enter') enter();
    else if (key === 'ArrowLeft') movePage(-1);
    else if (key === 'ArrowRight') movePage(1);
    else if (key === '+') setZoom(app.zoom + 1);
    else if (key === '-') setZoom(app.zoom - 1);
    else if (key === '=') setZoom(2);
    else if (key === '[') openDoc(app.index - 1);
    else if (key === ']') openDoc(app.index + 1);
    else if (key === 'n') nextTodo();
    else handled = false;
    if (handled) event.preventDefault();
  });

  (async function start() {
    try {
      await refresh();
      app.checks = await api('GET', '/api/checks');
      renderAllChecks();
    } catch (e) {
      notice('서버에 연결하지 못했습니다: ' + e.message);
      return;
    }
    await openDoc(firstOpen());
  }());
}());
