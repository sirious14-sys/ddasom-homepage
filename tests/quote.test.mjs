import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../_초안_functions/api/quote.js', import.meta.url), 'utf8');
const { onRequest } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const valid = { name: '테스트고객', tel: '010-0000-0000', region: '대구 중구', addr: '', place: '아파트', state: '입주 예정', product: '커튼', msg: '테스트 요청', agree: true, website: '' };
class MockKV {
  values = new Map(); writes = [];
  async get(key, type) {
    const item = this.values.get(key);
    if (!item || item.expires <= Date.now()) return null;
    return type === 'json' ? JSON.parse(item.value) : item.value;
  }
  async put(key, value, options) {
    this.writes.push({ key, value, options });
    this.values.set(key, { value, expires: Date.now() + options.expirationTtl * 1000 });
  }
}
function context(data = valid, overrides = {}, init = {}) {
  const pending = [];
  const env = { QUOTE_SUBMIT_ENABLED: 'on', NOTIFY_MODE: 'none', QUOTES: new MockKV(), ...overrides };
  const request = new Request('https://ddasom.test/api/quote', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': '192.0.2.1', Origin: 'https://ddasom.test', ...init.headers },
    body: JSON.stringify(data), ...Object.fromEntries(Object.entries(init).filter(([key]) => key !== 'headers')),
  });
  return { request, env, pending, waitUntil(promise) { pending.push(promise); } };
}
async function send(ctx) {
  const response = await onRequest(ctx);
  await Promise.all(ctx.pending);
  return { response, body: await response.json() };
}
test.beforeEach(t => { t.mock.method(globalThis, 'fetch', () => { throw new Error('실제 외부 호출 금지'); }); });

test('정상: KV 30일 TTL, 동의 기록, 최소 항목, JSON 응답', async () => {
  const ctx = context({ ...valid, unwanted: '저장 금지', managerTel: '임의 번호' });
  const { response, body } = await send(ctx);
  assert.equal(response.status, 200); assert.equal(body.ok, true); assert.match(body.id, /^[0-9a-f-]{36}$/);
  assert.equal(response.headers.get('Cache-Control'), 'no-store');
  const saved = ctx.env.QUOTES.writes.find(w => w.key === `quote:${body.id}`);
  assert.equal(saved.options.expirationTtl, 2592000);
  const record = JSON.parse(saved.value);
  assert.equal(record.tel, '01000000000'); assert.equal(record.agree, true);
  assert.equal(record.managerTel, '010-5495-9500');
  assert.equal(record.unwanted, undefined); assert.equal(record.website, undefined);
  assert.equal(record.ip, undefined); assert.equal(record.userAgent, undefined);
  const rate = ctx.env.QUOTES.writes.find(w => w.key.startsWith('rate:'));
  assert.equal(rate.options.expirationTtl, 60); assert.ok(!rate.key.includes('192.0.2.1'));
});
test('필수 누락: 성함·연락처·지역 각각 거절', async () => {
  for (const field of ['name', 'tel', 'region']) {
    const ctx = context({ ...valid, [field]: ' ' });
    const { response, body } = await send(ctx);
    assert.equal(response.status, 400); assert.equal(body.ok, false); assert.equal(body.id, null);
    assert.match(body.message, /전화·문자로 연락 주세요/); assert.equal(ctx.env.QUOTES.writes.length, 0);
  }
});
test('동의 없음 및 문자열 동의 거절', async () => {
  for (const agree of [false, undefined, 'true', 1]) assert.equal((await send(context({ ...valid, agree }))).response.status, 400);
});
test('honeypot 입력 및 비문자 값 거절', async () => {
  for (const website of ['https://spam.test', true]) {
    const ctx = context({ ...valid, website });
    assert.equal((await send(ctx)).response.status, 400); assert.equal(ctx.env.QUOTES.writes.length, 0);
  }
});
test('최근 1분 동일 IP 3회 허용, 4회 거절, 만료 및 다른 IP 허용', async t => {
  let now = 1800000000000;
  t.mock.method(Date, 'now', () => now);
  const kv = new MockKV();
  for (let i = 0; i < 3; i++) {
    now = 1800000000000 + i * 20000;
    assert.equal((await send(context(valid, { QUOTES: kv }))).response.status, 200);
  }
  now = 1800000059000;
  const limited = await send(context(valid, { QUOTES: kv }));
  assert.equal(limited.response.status, 429); assert.equal(limited.response.headers.get('Retry-After'), '60');
  assert.equal(kv.writes.filter(w => w.key.startsWith('quote:')).length, 3);
  assert.equal((await send(context(valid, { QUOTES: kv }, { headers: { 'CF-Connecting-IP': '192.0.2.2' } }))).response.status, 200);
  now = 1800000060000;
  assert.equal((await send(context(valid, { QUOTES: kv }))).response.status, 200);
});
test('폼 31개 지역 모두 담당 번호 매핑 일치', async () => {
  const html = readFileSync(new URL('../apply.html', import.meta.url), 'utf8');
  const options = [...html.matchAll(/<option data-tel="([\d-]+)">([^<]+)<\/option>/g)];
  assert.equal(options.length, 31);
  for (const [, tel, region] of options) {
    const ctx = context({ ...valid, region });
    const { body } = await send(ctx); assert.equal(body.ok, true);
    const saved = ctx.env.QUOTES.writes.find(w => w.key.startsWith('quote:'));
    assert.equal(JSON.parse(saved.value).managerTel, tel);
  }
});
test('길이·전화 형식·알 수 없는 지역/선택값·타입 검증', async () => {
  const lengths = { name: 50, tel: 20, region: 30, addr: 200, place: 50, state: 50, product: 50, msg: 2000 };
  for (const [field, limit] of Object.entries(lengths)) assert.equal((await send(context({ ...valid, [field]: '가'.repeat(limit + 1) }))).response.status, 400);
  for (const data of [{ ...valid, tel: 'hello' }, { ...valid, tel: '010' }, { ...valid, tel: '+821000000000' }, { ...valid, region: '임의 지역' }, { ...valid, place: '임의' }, { ...valid, state: '임의' }, { ...valid, product: '임의' }, { ...valid, name: 12 }, { ...valid, name: '가\n나' }, { ...valid, msg: '\u0000' }, null, []]) {
    assert.equal((await send(context(data))).response.status, 400);
  }
  assert.equal((await send(context({ ...valid, name: '가'.repeat(50), addr: '가'.repeat(200), msg: '가'.repeat(2000) }))).response.status, 200);
});
test('JSON 오류·본문 크기·Content-Type·교차 출처 거절', async () => {
  for (const init of [{ body: '{' }, { body: 'x'.repeat(16385) }, { headers: { 'Content-Length': '16385' } }]) assert.equal((await send(context(valid, {}, init))).response.status, 400);
  assert.equal((await send(context(valid, {}, { headers: { 'Content-Type': 'text/plain' } }))).response.status, 415);
  for (const headers of [{ Origin: 'https://other.test' }, { 'Sec-Fetch-Site': 'cross-site' }]) assert.equal((await send(context(valid, {}, { headers }))).response.status, 403);
});
test('기본 서버 off·KV 없음·KV 쓰기 실패: 접수 성공 없음', async () => {
  for (const overrides of [{ QUOTE_SUBMIT_ENABLED: undefined }, { QUOTE_SUBMIT_ENABLED: 'off' }, { QUOTES: undefined }, { QUOTES: { get: async () => null, put: async () => { throw new Error('KV'); } } }]) {
    const { response, body } = await send(context(valid, overrides));
    assert.equal(response.status, 503); assert.equal(body.ok, false); assert.equal(body.id, null);
  }
});
test('GET 거절 (개인정보 조회 API 없음)', async () => {
  const response = await onRequest({ request: new Request('https://ddasom.test/api/quote'), env: {} });
  assert.equal(response.status, 405); assert.equal(response.headers.get('Allow'), 'POST');
});
test('알림: none·키/수신처 없음·알 수 없는 모드는 외부 호출 0회', async () => {
  for (const overrides of [{}, { NOTIFY_MODE: 'email' }, { NOTIFY_MODE: 'email', RESEND_API_KEY: 'mock-only', NOTIFY_EMAIL_FROM: 'sender@example.test' }, { NOTIFY_MODE: 'telegram' }, { NOTIFY_MODE: 'unknown' }]) assert.equal((await send(context(valid, overrides))).body.ok, true);
});
test('email/telegram 두 담당 라우팅, 고객 개인정보 전송 없음 (fetch 모킹)', async t => {
  const calls = [];
  t.mock.method(globalThis, 'fetch', async (url, init) => { calls.push({ url, init }); return Response.json({ ok: true }); });
  for (const [region, manager] of [['대구 중구', 'JEONG'], ['안동시', 'LEE']]) {
    for (const mode of ['email', 'telegram']) {
      const env = { NOTIFY_MODE: mode, RESEND_API_KEY: 'mock-only', NOTIFY_EMAIL_FROM: 'sender@example.test', NOTIFY_EMAIL_JEONG: 'jeong@example.test', NOTIFY_EMAIL_LEE: 'lee@example.test', TELEGRAM_BOT_TOKEN: 'mock-only', TELEGRAM_CHAT_ID_JEONG: 'mock-jeong', TELEGRAM_CHAT_ID_LEE: 'mock-lee' };
      assert.equal((await send(context({ ...valid, region }, env))).body.ok, true);
      const { init } = calls.at(-1), body = JSON.parse(init.body);
      assert.equal(mode === 'email' ? body.to[0] : body.chat_id, mode === 'email' ? `${manager.toLowerCase()}@example.test` : `mock-${manager.toLowerCase()}`);
      for (const privateText of [valid.name, '01000000000', valid.msg]) assert.ok(!init.body.includes(privateText));
    }
  }
  assert.equal(calls.length, 4);
});
test('알림 실패 시 저장된 접수는 성공, 고정 로그에 개인정보 없음', async t => {
  const warnings = [];
  t.mock.method(console, 'warn', text => warnings.push(text));
  t.mock.method(globalThis, 'fetch', async () => new Response('mock failure', { status: 500 }));
  const ctx = context(valid, { NOTIFY_MODE: 'email', RESEND_API_KEY: 'mock-only', NOTIFY_EMAIL_FROM: 'sender@example.test', NOTIFY_EMAIL_JEONG: 'jeong@example.test' });
  assert.equal((await send(ctx)).body.ok, true);
  assert.equal(ctx.env.QUOTES.writes.filter(w => w.key.startsWith('quote:')).length, 1);
  assert.deepEqual(warnings, ['quote notification failed']);
});
