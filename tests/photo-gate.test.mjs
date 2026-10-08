// 2026-10-08d 코덱스 교차검증 20261008g §1-4: 홈페이지 배포 경로에 사진 중복 관문이 없었다.
// 배포.py 가 담기() 뒤에 「이번 배포로 새로 추가·변경되는 사진」만 사진체크.업로드전검사(채널=홈페이지)로 검사하고,
// 모듈 없음·기록 없음·관문 실패면 업로드(wrangler) 전에 멈추는지 본다. 실제 사진체크·네트워크·업로드는 쓰지 않는다(가짜 모듈).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const work = mkdtempSync(join(tmpdir(), 'ddasom-photogate-'));

const fake = `
import json, os
LOG = os.environ["FAKE_SAJIN_LOG"]
def _w(*a):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(a, ensure_ascii=False) + "\\n")
def 업로드전검사(paths, cwd=None, 채널=None, 예약=True, 배포루트=None, 도구=None):
    _w("검사", sorted(os.path.relpath(p, 배포루트).replace("\\\\", "/") for p in paths), 채널, 예약, bool(배포루트))
    return os.environ.get("FAKE_SAJIN_OK") == "1"
def 사용등록(paths, where):
    _w("등록", len(paths), where)
def 예약해제(이유="", rid=None):
    _w("해제", 이유)
`;
writeFileSync(join(work, '사진체크.py'), fake, 'utf8');

const py = `
import importlib.util, sys, json, os, io, pathlib, shutil
spec = importlib.util.spec_from_file_location("deploy", "배포.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
W = pathlib.Path(sys.argv[1]); LOG = W / "log.jsonl"
os.environ["FAKE_SAJIN_LOG"] = str(LOG)
dist = W / "dist"
def make_dist():
    if dist.exists(): shutil.rmtree(dist)
    (dist / "reviews/img/a").mkdir(parents=True); (dist / "promo-img").mkdir(parents=True)
    (dist / "reviews/img/a/1.jpg").write_bytes(b"A1"); (dist / "reviews/img/a/1.webp").write_bytes(b"A1w")
    (dist / "promo-img/b.jpg").write_bytes(b"B"); (dist / "index.html").write_text("x")
def log():
    return [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines()] if LOG.exists() else []
def gate(ok):
    if LOG.exists(): LOG.unlink()
    os.environ["FAKE_SAJIN_OK"] = "1" if ok else "0"
    try:
        _, new, _ = m.사진관문(dist, 예약=True); r = "통과:%d" % len(new)
    except SystemExit as e:
        r = "중단"
    return r, log()
out = {}
make_dist()
m.사진도구 = W / "없음"
out["모듈없음"] = gate(True)[0]
m.사진도구 = W
기록 = m.배포기록경로()
if 기록.exists(): 기록.unlink()
out["기록없음"] = gate(True)[0]
m.사진기록쓰기(m.사진목록(dist), "시험")
out["바뀐것없음"] = gate(True)
(dist / "reviews/img/a/1.jpg").write_bytes(b"A1-changed"); (dist / "reviews/img/c.jpg").parent.mkdir(exist_ok=True); (dist / "reviews/img/c.jpg").write_bytes(b"C")
out["새것_관문실패"] = gate(False)
out["새것_관문통과"] = gate(True)
# main --실행 흐름: 담기 → 사진관문 → (통과 시) wrangler → 등록·기록 갱신 / 실패 시 해제
calls = []
class R: returncode = 0
def fake_run(args, **kw):
    calls.append("wrangler"); open(LOG, "a", encoding="utf-8").write(json.dumps(["wrangler"]) + "\\n"); return R
m.subprocess.run = fake_run
m.토큰 = lambda: "TEST"
m.색인알림 = lambda d: None
os.environ["TEMP"] = str(W)
def fake_담기(d):
    assert pathlib.Path(d) == W / "ddasom_dist"
    global dist
    dist = pathlib.Path(d); make_dist(); (dist / "reviews/img/new.jpg").write_bytes(b"N"); return []
m.담기 = fake_담기
m.사진기록쓰기({"reviews/img/a/1.jpg": __import__("hashlib").sha256(b"A1").hexdigest()}, "시험")
def main(ok, rc=0):
    if LOG.exists(): LOG.unlink()
    os.environ["FAKE_SAJIN_OK"] = "1" if ok else "0"; R.returncode = rc
    sys.argv = ["배포.py", "--실행"]
    try:
        r = m.main()
    except SystemExit as e:
        r = "중단"
    return r, [x[0] for x in log()]
out["실행_관문실패"] = main(False)
out["실행_업로드실패"] = main(True, 1)
before = json.loads(m.배포기록경로().read_text(encoding="utf-8"))["사진"]
out["실행_성공"] = main(True, 0)
after = json.loads(m.배포기록경로().read_text(encoding="utf-8"))["사진"]
out["기록갱신"] = [len(before), len(after)]
out["다시_실행"] = main(True, 0)
print(json.dumps(out, ensure_ascii=False))
`;

test('배포.py 사진 관문: 새로·바뀐 사진만 홈페이지 채널로 검사, 모듈·기록 없음·실패면 업로드 전에 중단', () => {
  const r = spawnSync('python', ['-X', 'utf8', '-c', py, work], { cwd: root, encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
  assert.equal(r.status, 0, r.stderr + r.stdout);
  const out = JSON.parse(r.stdout.trim().split('\n').pop());
  assert.equal(out['모듈없음'], '중단');
  assert.equal(out['기록없음'], '중단');
  assert.deepEqual(out['바뀐것없음'], ['통과:0', []]);                       // 바뀐 사진이 없으면 검사하지 않는다
  assert.equal(out['새것_관문실패'][0], '중단');
  assert.deepEqual(out['새것_관문실패'][1], [['검사', ['reviews/img/a/1.jpg', 'reviews/img/c.jpg'], '홈페이지', true, true]]);
  assert.equal(out['새것_관문통과'][0], '통과:2');
  // 관문 실패면 wrangler 를 부르지 않는다
  assert.deepEqual(out['실행_관문실패'], ['중단', ['검사']]);
  // 업로드 실패면 예약을 풀고 기록은 그대로
  assert.deepEqual(out['실행_업로드실패'], [1, ['검사', 'wrangler', '해제']]);
  // 성공하면 검사 → 업로드 → 사용 등록, 기록 갱신
  assert.deepEqual(out['실행_성공'], [0, ['검사', 'wrangler', '등록']]);
  assert.deepEqual(out['기록갱신'], [1, 4]);
  // 갱신된 기록 기준으로는 새 사진이 없다 → 검사 없이 업로드
  assert.deepEqual(out['다시_실행'], [0, ['wrangler']]);
});
