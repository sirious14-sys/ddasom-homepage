// 기본 비활성화. QUOTE_SUBMIT_ENABLED=on 과 QUOTES 바인딩이 모두 필요합니다.
const RETENTION_SECONDS = 30 * 24 * 60 * 60;
const MAX_BODY_BYTES = 16 * 1024;
const FALLBACK = '서버 접수가 어려워요. 전화·문자로 연락 주세요.';
const JEONG = new Set(['대구 중구', '대구 동구', '대구 서구', '대구 남구', '대구 북구', '대구 수성구', '대구 달서구', '대구 달성군', '대구 군위군', '경산시', '구미시', '김천시', '청도군', '칠곡군', '성주군', '고령군']);
const LEE = new Set(['포항시', '경주시', '안동시', '영천시', '영주시', '의성군', '울진군', '영덕군', '청송군', '봉화군', '영양군', '문경시', '상주시', '예천군', '울릉군']);
const OPTIONS = {
  place: ['아파트', '주택 / 빌라', '상가 / 사무실', '관공서 / 기타'],
  state: ['현재 공실 (비어 있음)', '거주 중', '입주 예정', '층고 높음 / 큰 창'],
  product: ['커튼', '블라인드', '커튼 + 블라인드', '전동 커튼·블라인드', '롤스크린', '기타 / 상담 후 결정'],
};

function reply(status, id = null, headers = {}) {
  return new Response(JSON.stringify(status === 200 ? { ok: true, id } : { ok: false, id: null, message: FALLBACK }), {
    status, headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', ...headers },
  });
}

async function readBody(request) {
  if (Number(request.headers.get('Content-Length')) > MAX_BODY_BYTES) throw new Error('body');
  if (!request.body) throw new Error('body');
  const reader = request.body.getReader();
  const chunks = [];
  let size = 0;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX_BODY_BYTES) { await reader.cancel(); throw new Error('body'); }
    chunks.push(value);
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
}

function validate(data) {
  if (!data || typeof data !== 'object' || Array.isArray(data) || data.agree !== true) return null;
  if (data.website !== undefined && (typeof data.website !== 'string' || data.website.trim())) return null;
  const limits = { name: 50, tel: 20, region: 30, addr: 200, place: 50, state: 50, product: 50, msg: 2000 };
  const quote = {};
  for (const [field, max] of Object.entries(limits)) {
    const value = data[field] ?? '';
    if (typeof value !== 'string' || value.length > max) return null;
    quote[field] = value.trim();
    if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(value)) return null;
    if (field !== 'msg' && /[\r\n\t]/.test(value)) return null;
  }
  if (!quote.name || !quote.tel || !quote.region) return null;
  if (!/^[0-9 ()-]+$/.test(quote.tel)) return null;
  quote.tel = quote.tel.replace(/[ ()-]/g, '');
  if (!/^0\d{8,10}$/.test(quote.tel)) return null;
  const manager = JEONG.has(quote.region) ? 'JEONG' : LEE.has(quote.region) ? 'LEE' : null;
  if (!manager) return null;
  for (const [field, values] of Object.entries(OPTIONS)) {
    if (quote[field] && !values.includes(quote[field])) return null;
  }
  return { ...quote, agree: true, manager, managerTel: manager === 'JEONG' ? '010-5495-9500' : '010-2825-7275' };
}

async function allowRequest(request, kv) {
  // KV는 원자적 카운터가 아니므로 분산/동시 요청에 대한 엄격한 제한은 아닙니다.
  const ip = request.headers.get('CF-Connecting-IP');
  if (!ip) return true; // 로컬 요청: 임의 X-Forwarded-For를 신뢰하지 않습니다.
  const now = Date.now();
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(`${new Date(now).toISOString().slice(0, 10)}:${ip}`));
  const key = 'rate:' + Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('');
  const previous = await kv.get(key, 'json');
  const recent = Array.isArray(previous) ? previous.filter(t => Number.isFinite(t) && t > now - 60000) : [];
  if (recent.length >= 3) return false;
  await kv.put(key, JSON.stringify([...recent, now]), { expirationTtl: 60 });
  return true;
}

async function notify(env, quote, id) {
  // 외부 서비스에는 고객 이름/연락처/상세주소/요청 내용을 보내지 않습니다.
  const text = `따솜 견적 접수\n접수번호: ${id}\n지역: ${quote.region}\n담당: ${quote.manager === 'JEONG' ? '정실장' : '이실장'} (${quote.managerTel})\nCloudflare QUOTES에서 quote:${id}를 확인해 주세요.`;
  let url, payload, headers = { 'Content-Type': 'application/json' };
  if (env.NOTIFY_MODE === 'email') {
    const to = env[`NOTIFY_EMAIL_${quote.manager}`];
    if (!env.RESEND_API_KEY || !env.NOTIFY_EMAIL_FROM || !to) return;
    url = 'https://api.resend.com/emails';
    headers.Authorization = `Bearer ${env.RESEND_API_KEY}`;
    headers['Idempotency-Key'] = `quote-${id}`;
    payload = { from: env.NOTIFY_EMAIL_FROM, to: [to], subject: '따솜 새 견적 접수', text };
  } else if (env.NOTIFY_MODE === 'telegram') {
    const chatId = env[`TELEGRAM_CHAT_ID_${quote.manager}`];
    if (!env.TELEGRAM_BOT_TOKEN || !chatId) return;
    url = `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`;
    payload = { chat_id: chatId, text };
  } else return; // 미설정/키 없음/알 수 없는 모드 = none
  const response = await fetch(url, { method: 'POST', headers, body: JSON.stringify(payload), signal: AbortSignal.timeout(8000) });
  if (!response.ok || (env.NOTIFY_MODE === 'telegram' && !(await response.json()).ok)) throw new Error('notify');
}

export async function onRequest(context) {
  const { request, env } = context;
  if (request.method !== 'POST') return reply(405, null, { Allow: 'POST' });
  if (env.QUOTE_SUBMIT_ENABLED !== 'on' || !env.QUOTES) return reply(503);
  const origin = request.headers.get('Origin');
  if ((origin && origin !== new URL(request.url).origin) || request.headers.get('Sec-Fetch-Site') === 'cross-site') return reply(403);
  if (!/^application\/json(?:\s*;|$)/i.test(request.headers.get('Content-Type') || '')) return reply(415);
  let quote;
  try { quote = validate(await readBody(request)); } catch { return reply(400); }
  if (!quote) return reply(400);
  const id = crypto.randomUUID();
  try {
    if (!(await allowRequest(request, env.QUOTES))) return reply(429, null, { 'Retry-After': '60' });
    await env.QUOTES.put(`quote:${id}`, JSON.stringify({ id, createdAt: new Date().toISOString(), ...quote }), { expirationTtl: RETENTION_SECONDS });
  } catch { return reply(503); } // KV에 저장되지 않았으면 성공을 반환하지 않습니다.
  const notification = notify(env, quote, id).catch(() => {
    console.warn('quote notification failed'); // 개인정보/키/응답 본문은 로그에 남기지 않음
  });
  if (context.waitUntil) context.waitUntil(notification);
  else await notification;
  return reply(200, id); // 알림 실패는 이미 저장한 접수를 취소하지 않습니다.
}
