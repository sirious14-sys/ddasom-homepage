// 2026-10-08 코덱스 교차검증: 업로드 목록을 문자열로만 보면 append·작은따옴표 재포함을 못 잡는다.
// 배포.py 의 공개금지검사(실제 담긴 결과물 검사)가 내부 견적·소스 재포함을 막는지 본다.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const dist = mkdtempSync(join(tmpdir(), 'ddasom-guard-'));
const py = `
import importlib.util, sys, json
spec = importlib.util.spec_from_file_location("deploy", "배포.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
out = {}
def run(extra):
    if extra: m.올릴것.append(extra)
    try:
        m.담기(__import__("pathlib").Path(sys.argv[1])); r = "통과"
    except SystemExit:
        r = "중단"
    if extra: m.올릴것.remove(extra)
    return r
for x in ["", "quote.html", "estimate.html", "build.py", "_초안_functions"]:
    out[x or "정상"] = run(x)
print(json.dumps(out, ensure_ascii=False))
`;

test('배포.py 공개금지검사: 정상 목록은 통과, 내부 견적·소스·초안 함수 재포함은 중단', () => {
  const r = spawnSync('python', ['-c', py, join(dist, 'd')], { cwd: root, encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
  assert.equal(r.status, 0, r.stderr);
  const out = JSON.parse(r.stdout.trim().split('\n').pop());
  assert.deepEqual(out, { 정상: '통과', 'quote.html': '중단', 'estimate.html': '중단', 'build.py': '중단', '_초안_functions': '중단' });
});
