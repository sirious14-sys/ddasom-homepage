import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import vm from 'node:vm';

// 원본 커밋: 92b2f1ed8c3dd86c58830a8fcd05b9fb9ecf2c9e (Windows CRLF 체크아웃)
const baseline = readFileSync(new URL('./fixtures/apply-original.html', import.meta.url));
const current = readFileSync(new URL('../apply.html', import.meta.url));
const scripts = html => [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(match => match[1]);
const agents = { pc: 'Desktop Test', android: 'Android Mobile', ios: 'iPhone Mobile' };
const RECEIPT = '11111111-1111-4111-8111-111111111111';

// 모킹 DOM: 기존 스크립트 전체와 실제 전환 리스너를 VM에서 실행합니다.
// 어떤 외부 script도 로드하지 않으며 fetch/clipboard/sms는 관찰용 mock입니다.
function run(html, { mode, device = 'pc', missing, region = '대구 중구', managerTel = '010-5495-9500', outcome = 'success' } = {}) {
  const elements = new Map(), documentListeners = new Map();
  const trace = { fetch: [], events: [], alerts: [], conversions: [], clarity: [], clipboard: [], scroll: [], href: '' };
  class Element {
    value = ''; checked = false; dataset = {}; style = {}; textContent = ''; listeners = new Map(); children = [];
    classList = { toggle() {}, remove() {}, add() {} };
    constructor(id) { this.id = id; elements.set(id, this); }
    addEventListener(type, callback) { const list = this.listeners.get(type) || []; list.push(callback); this.listeners.set(type, list); }
    fire(type, event) { for (const callback of this.listeners.get(type) || []) callback.call(this, event); }
    querySelector(selector) { return selector === 'button[type=submit]' ? elements.get('submitButton') : selector === '.agree-info' ? elements.get('agreeInfo') : null; }
    querySelectorAll() { return []; }
    set innerHTML(value) {
      this.html = value;
      if (this.id === 'applySent') for (const id of ['quoteServerStatus', 'applyCopy', 'applyBody']) elements.delete(id);
      for (const match of value.matchAll(/id="([^"]+)"/g)) new Element(match[1]);
    }
    get innerHTML() { return this.html || ''; }
    appendChild(child) { this.children.push(child); elements.set(child.id, child); }
    prepend(child) { this.children.unshift(child); elements.set(child.id, child); }
    setAttribute(key, value) { this[key] = value; }
    scrollIntoView(options) { trace.scroll.push(options); }
    select() {}
  }
  for (const id of ['menuBtn', 'navLinks', 'header', 'applyForm', 'af-name', 'af-tel', 'af-region', 'af-addr', 'af-place', 'af-state', 'af-product', 'af-msg', 'af-agree', 'applySent', 'submitButton', 'agreeInfo', 'note', 'description']) new Element(id);
  const values = { 'af-name': ' 테스트고객 ', 'af-tel': '010-0000-0000', 'af-region': region, 'af-addr': '테스트 주소', 'af-place': '아파트', 'af-state': '입주 예정', 'af-product': '커튼', 'af-msg': '테스트 요청\n창 사진 예정' };
  for (const [id, value] of Object.entries(values)) elements.get(id).value = value;
  elements.get('af-region').selectedOptions = [{ dataset: { tel: managerTel } }];
  elements.get('af-agree').checked = missing !== 'agree';
  if (missing && missing !== 'agree') elements.get('af-' + missing).value = '';
  const configured = html.match(/data-server-submit="([^"]+)"/)?.[1];
  elements.get('applyForm').dataset.serverSubmit = mode ?? configured;
  const document = {
    getElementById: id => elements.get(id) || null,
    querySelector: selector => elements.get(selector === '.apply-note' ? 'note' : selector === '.apply-desc' ? 'description' : 'agreeInfo'),
    querySelectorAll: () => [],
    createElement: () => new Element('created-' + elements.size),
    addEventListener(type, callback) { const list = documentListeners.get(type) || []; list.push(callback); documentListeners.set(type, list); },
    dispatchEvent(event) {
      trace.events.push(event.type);
      for (const callback of documentListeners.get(event.type) || []) { callback(event); if (event.stopped) break; }
    },
  };
  const timers = new Map(); let timerId = 0;
  const window = { clarity: (...args) => trace.clarity.push(args), wcs: { trans: payload => trace.conversions.push(payload.type), inflow() {} } };
  const location = { set href(value) { trace.href = value; }, get href() { return trace.href; } };
  const fetch = async (url, init) => {
    trace.fetch.push({ url, body: JSON.parse(init.body), keepalive: init.keepalive });
    if (outcome === 'network') throw new Error('mock network');
    if (outcome === 'timeout') return new Promise((resolve, reject) => init.signal.addEventListener('abort', () => reject(new Error('mock timeout'))));
    if (outcome === 'invalid') return { ok: true, json: async () => { throw new Error('not json'); } };
    if (outcome === 'failure') return { ok: false, json: async () => ({ ok: false, id: null }) };
    return { ok: true, json: async () => ({ ok: true, id: RECEIPT }) };
  };
  const context = vm.createContext({ document, window, navigator: { userAgent: agents[device], clipboard: { writeText: async text => trace.clipboard.push(text) } },
    location, scrollY: 0, addEventListener() {}, IntersectionObserver: class { observe() {} },
    CustomEvent: class { constructor(type) { this.type = type; } stopImmediatePropagation() { this.stopped = true; } },
    alert: text => trace.alerts.push(text), clarity: window.clarity, wcs: window.wcs, wcs_do() {},
    fetch, AbortController, setTimeout: callback => { timers.set(++timerId, callback); return timerId; }, clearTimeout: id => timers.delete(id), console });
  for (const source of scripts(html)) {
    if (source.includes('const form=document.getElementById') || source.includes("const quoteForm=document.getElementById") || source.includes('document.addEventListener("quote:prepared"')) vm.runInContext(source, context);
  }
  function submit() { elements.get('applyForm').fire('submit', { preventDefault() {} }); }
  function snapshot() {
    return JSON.parse(JSON.stringify({ trace, body: elements.get('applyBody')?.value || '', rendered: elements.get('applySent').innerHTML,
      display: elements.get('applySent').style.display, note: elements.get('note').innerHTML, description: elements.get('description').innerHTML,
      button: elements.get('submitButton').textContent, status: elements.get('quoteServerStatus')?.textContent || null }));
  }
  return { elements, trace, submit, snapshot, timers };
}
async function flush() { for (let i = 0; i < 15; i++) await Promise.resolve(); }

test('기본 off 및 새 속성/추가 블록 제거 시 원본 파일 바이트 완전 일치', () => {
  assert.match(current.toString(), /data-server-submit="off"/);
  const stripped = current.toString().replace(' data-server-submit="off"', '').replace(/<!-- QUOTE-SERVER-DRAFT:start -->[\s\S]*?<!-- QUOTE-SERVER-DRAFT:end -->\r?\n/, '');
  assert.deepEqual(Buffer.from(stripped), baseline);
});
test('배포.py 바이트 불변', () => {
  assert.equal(createHash('sha256').update(readFileSync(new URL('../배포.py', import.meta.url))).digest('hex'), 'feac739efb33e6e4933b0a0060a8718307cb5fda101bbb8d6decb731b5cb2f31');
});
for (const device of Object.keys(agents)) {
  test(`off ${device}: 문자 본문/화면 HTML/SMS URI/복사/custom001 원본과 완전 일치, 서버 호출 0`, async () => {
    const previous = run(baseline.toString(), { device }), next = run(current.toString(), { device });
    previous.submit(); next.submit(); await flush();
    previous.elements.get('applyCopy').fire('click'); next.elements.get('applyCopy').fire('click'); await flush();
    assert.deepEqual(next.snapshot(), previous.snapshot());
    assert.equal(next.trace.fetch.length, 0); assert.deepEqual(next.trace.conversions, ['custom001']);
    assert.equal(next.elements.get('af-website'), undefined);
  });
}
for (const missing of ['name', 'tel', 'region', 'agree']) {
  test(`off ${missing} 누락: 기존 검증/알림 불변, 서버 호출 0`, async () => {
    const previous = run(baseline.toString(), { missing }), next = run(current.toString(), { missing });
    previous.submit(); next.submit(); await flush();
    assert.deepEqual(next.snapshot(), previous.snapshot()); assert.equal(next.trace.fetch.length, 0);
  });
}
for (const device of Object.keys(agents)) {
  test(`on ${device}: 기존 문자 즉시 생성, 성공 후에만 lead/접수번호`, async () => {
    const previous = run(baseline.toString(), { device });
    const next = run(current.toString(), { mode: 'on', device });
    previous.submit(); next.submit();
    assert.equal(next.trace.href, previous.trace.href); assert.equal(next.snapshot().body, previous.snapshot().body);
    assert.deepEqual(next.trace.conversions, []); // 응답 전 전환 없음
    await flush(); assert.equal(next.trace.fetch.length, 1); assert.equal(next.trace.fetch[0].url, '/api/quote');
    assert.equal(next.trace.fetch[0].keepalive, true); assert.equal(next.trace.fetch[0].body.agree, true);
    assert.match(next.snapshot().status, new RegExp(`접수되었습니다\\(${RECEIPT}\\)`));
    assert.deepEqual(next.trace.conversions, ['lead']); assert.equal(next.timers.size, 0);
  });
}
for (const outcome of ['failure', 'network', 'invalid', 'timeout']) {
  test(`on ${outcome}: 전화·문자 안내와 기존 문자/복사 유지, 전환 없음`, async () => {
    const next = run(current.toString(), { mode: 'on', device: 'ios', outcome });
    const previous = run(baseline.toString(), { device: 'ios' });
    next.submit(); previous.submit(); await flush();
    if (outcome === 'timeout') { for (const callback of next.timers.values()) callback(); await flush(); }
    assert.match(next.snapshot().status, /전화·문자로 연락 주세요/);
    assert.equal(next.snapshot().body, previous.snapshot().body); assert.equal(next.trace.href, previous.trace.href);
    next.elements.get('applyCopy').fire('click'); previous.elements.get('applyCopy').fire('click'); await flush();
    assert.deepEqual(next.trace.clipboard, previous.trace.clipboard); assert.deepEqual(next.trace.conversions, []);
  });
}
test('on에서도 필수/동의 검증 전 서버 호출 없음', async () => {
  for (const missing of ['name', 'tel', 'region', 'agree']) {
    const next = run(current.toString(), { mode: 'on', missing }); next.submit(); await flush();
    assert.equal(next.trace.fetch.length, 0); assert.equal(next.trace.alerts.length, 1);
  }
});
test('on 재작성: 이전 접수 표시를 지우고 최신 접수 결과 표시', async () => {
  const next = run(current.toString(), { mode: 'on' }); next.submit(); await flush();
  next.elements.get('af-msg').value = '두 번째 요청'; next.submit(); await flush();
  assert.match(next.snapshot().status, /접수되었습니다/); assert.equal(next.trace.fetch.length, 2);
  assert.equal(next.trace.fetch[1].body.msg, '두 번째 요청');
});
