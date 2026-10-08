# -*- coding: utf-8 -*-
"""홈페이지를 실제로 공개하는 유일한 경로.

★ 깃허브 push 는 배포가 아니다 (2026-09-05 확인).
  ddasom.com 은 Cloudflare Pages 프로젝트 `ddasom` 이 서비스하는데
  이 프로젝트는 **Git 연결이 없다(직접 업로드 방식)**.
  그래서 `git push` 를 아무리 해도 사이트는 그대로다.
  실제로 b2b 시즌 섹션·방염 가이드가 push 된 채로 며칠 안 올라가 있었다.
  깃허브는 소스 보관용, 공개는 이 파일로 한다.

사용법
    python 배포.py            미리보기 — 무엇을 올릴지만 보여준다(사진 관문 검사 포함, 예약은 안 잡음)
    python 배포.py --실행     실제 업로드
    python 배포.py --사진기준  지금 담긴 사진을 「이미 공개된 것」으로 기록만 한다(업로드 안 함).
                              ddasom.com 에 지금 담긴 사진이 이미 올라가 있을 때 한 번만 — 사진 관문의 비교 기준.

★ 사진 중복 관문 (2026-10-08d, 코덱스 교차검증 20261008g §1-4)
  사장님 원칙: 원본은 네이버 한 곳에만 한 번 · 홈페이지는 홈페이지 전용 변형본만 · 같은 채널 재사용 금지.
  담기() 뒤에, 지난 배포 기록과 비교해 「이번 배포로 새로 추가·변경되는 사진」만
  사진체크.업로드전검사(채널="홈페이지") 로 검사한다. 사진체크 모듈이 없거나·기록이 없거나·걸리면 배포를 멈춘다.
"""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = "ddasom"

# 올릴 것만 적는다. 여기 없는 것은 안 올라간다.
# quote.html·estimate.html 은 내부용(원가·마진)이라 뺐다 — 사본: 바탕화면\따솜_내부용_견적계산기 (2026-10-08)
# (예전에는 폴더째 올려서 build.py·_push.bat 이 그대로 공개돼 있었다)
올릴것 = [
    "index.html", "services.html", "gallery.html", "areas.html", "apply.html",
    "privacy.html", "b2b.html", "b2b-bangyeom.html", "b2b-office.html", "b2b-school.html", "b2b-clinic.html", "b2b-shop.html", "b2b-hotel.html", "partner.html",
    "404.html", "site.css", "robots.txt", "sitemap.xml", "rss.xml", "llms.txt",
    "CNAME", "5874d855cbfb4be788976bdf69162102.txt",   # 네이버 사이트 확인 파일
    "reviews", "areas", "ipju", "danji", "promo-img", "guides",
]

TOKEN_후보 = [
    ROOT / ".cloudflare_token",
    Path(r"C:\Users\User\Documents\Claude\Projects\네이버블로그 홍보\애드센스-사이트공장\.cloudflare_token"),
]


def 토큰():
    for p in TOKEN_후보:
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    return os.environ.get("CLOUDFLARE_API_TOKEN")


def 담기(dist: Path):
    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir(parents=True)
    빠진것 = []
    for 이름 in 올릴것:
        원본 = ROOT / 이름
        if not 원본.exists():
            빠진것.append(이름)
            continue
        if 원본.is_dir():
            shutil.copytree(원본, dist / 이름,
                            ignore=shutil.ignore_patterns("__pycache__", "*.py", "*.bat", "*.zip", "*.md"))
        else:
            shutil.copy2(원본, dist / 이름)
    공개금지검사(dist)
    return 빠진것


# 2026-10-08 코덱스 교차검증: 목록 문자열만 검사하는 시험은 append·작은따옴표 재포함을 못 잡았다.
# 그래서 실제로 담긴 결과물(dist)을 올리기 직전에 본다. 하나라도 있으면 아무것도 안 올린다.
공개금지_이름 = {"quote.html", "estimate.html", "quote", "estimate", "functions", "_초안_functions", "tests", ".git"}
공개금지_확장자 = {".py", ".bat", ".md", ".zip", ".ps1", ".mjs"}


def 공개금지검사(dist: Path):
    걸림 = [str(p.relative_to(dist)) for p in dist.rglob("*")
            if p.name in 공개금지_이름 or (p.is_file() and p.suffix.lower() in 공개금지_확장자)
            or p.name.startswith(".") and p.name != ".well-known"]
    if 걸림:
        raise SystemExit("[배포 중단] 올리면 안 되는 파일이 담겼습니다(내부 견적·초안 함수·소스): " + ", ".join(걸림[:20]))


# ── 사진 중복 관문 (2026-10-08d) ──────────────────────────────────────────
# 사진체크 모듈(네이버블로그 홍보/tools/사진체크.py)을 경로로 불러 쓴다. 없으면 배포 중단(모르면 안 올림).
사진도구 = Path(os.environ.get("DDASOM_SAJIN_TOOLS")
             or r"C:\Users\User\Documents\Claude\Projects\네이버블로그 홍보\tools")
사진확장자 = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def 사진모듈():
    p = 사진도구 / "사진체크.py"
    if not p.exists():
        raise SystemExit("[배포 중단] 사진 중복 관문 모듈을 못 찾았다: %s — 사진 검사 없이는 안 올린다" % p)
    try:
        sys.path.insert(0, str(사진도구))
        spec = importlib.util.spec_from_file_location("사진체크", str(p))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
    except Exception as e:
        raise SystemExit("[배포 중단] 사진체크 모듈을 불러오지 못했다(%s) — 사진 검사 없이는 안 올린다" % e)
    if not hasattr(m, "업로드전검사"):
        raise SystemExit("[배포 중단] 사진체크 모듈에 업로드전검사가 없다 — 사진 검사 없이는 안 올린다")
    return m


def 배포기록경로():
    return 사진도구 / "_홈페이지배포기록.json"


def 사진목록(dist: Path):
    """담긴 사진 → {상대경로(/): sha256}"""
    out = {}
    for f in sorted(dist.rglob("*")):
        if f.is_file() and f.suffix.lower() in 사진확장자:
            out[f.relative_to(dist).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def 사진기록쓰기(지금: dict, 무엇: str):
    p = 배포기록경로()
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"사진": 지금, "시각": time.strftime("%Y-%m-%dT%H:%M:%S"), "무엇": 무엇, "도구": "배포.py"},
                  f, ensure_ascii=False, indent=1)
    os.replace(tmp, str(p))


def 사진관문(dist: Path, 예약: bool):
    """이번 배포로 새로 추가·변경되는 사진만 사진체크.업로드전검사(채널=홈페이지)로 검사. 걸리면 SystemExit.
    → (사진체크 모듈, 새로·바뀐 상대경로 목록, 지금 담긴 사진 지도)"""
    C = 사진모듈()
    기록 = 배포기록경로()
    if not 기록.exists():
        raise SystemExit("[배포 중단] 지난 배포의 사진 기록(%s)이 없다 — 무엇이 새 사진인지 몰라 안 올린다.\n"
                         "          지금 담긴 사진이 이미 ddasom.com 에 올라가 있다면 `python 배포.py --사진기준` 을 한 번 돌려라." % 기록)
    try:
        기준 = json.loads(기록.read_text(encoding="utf-8"))["사진"]
    except Exception as e:
        raise SystemExit("[배포 중단] 지난 배포 사진 기록을 읽지 못했다(%s)" % e)
    지금 = 사진목록(dist)
    새것 = [r for r, h in 지금.items() if 기준.get(r) != h]
    print("   [사진] 담긴 사진 %d장 · 지난 배포 뒤 새로·바뀐 사진 %d장" % (len(지금), len(새것)))
    if not 새것:
        return C, [], 지금
    for r in 새것[:20]:
        print("          - " + r)
    ok = C.업로드전검사([str(dist / r) for r in 새것], 채널="홈페이지", 예약=예약, 배포루트=str(dist), 도구="배포.py")
    if not ok:
        raise SystemExit("[배포 중단] 사진 중복 관문에 걸렸다 — 홈페이지에는 홈페이지 전용 변형본(채널사진분배 계보·sha256 일치)만, "
                         "같은 원본은 한 번만 올린다. 위 [X] 줄을 고친 뒤 다시.")
    return C, 새것, 지금


INDEXNOW_KEY = "5874d855cbfb4be788976bdf69162102"   # ddasom.com 루트의 확인 파일과 같은 값


def 색인알림(dist):
    """올린 뒤 검색엔진에 "이 주소 바뀌었다"를 바로 알린다 (IndexNow).

    안 부르면 구글·빙이 며칠 뒤에나 온다. 배포는 성공했는데 검색 결과만
    옛날 것으로 남는다. 빙·네이버 등이 IndexNow 를 받는다.

    보낼 주소 = 지난번 알린 뒤에 내용이 바뀐 HTML. `.indexnow_last` 에 시각을 적어둔다.
    실패해도 배포를 실패로 만들지 않는다 — 올린 것은 이미 올라갔다.
    """
    import json
    import time
    import urllib.request

    기록 = ROOT / ".indexnow_last"
    지난번 = float(기록.read_text().strip()) if 기록.exists() else 0.0
    주소 = []
    for f in sorted(dist.rglob("*.html")):
        if f.stat().st_mtime <= 지난번:
            continue
        rel = f.relative_to(dist).as_posix()
        rel = "" if rel == "index.html" else rel[:-len("index.html")] if rel.endswith("/index.html") else rel
        주소.append("https://ddasom.com/" + rel)
    if not 주소:
        print("   [색인] 바뀐 페이지가 없다 — 알리지 않는다")
        return
    몸통 = json.dumps({
        "host": "ddasom.com",
        "key": INDEXNOW_KEY,
        "keyLocation": "https://ddasom.com/%s.txt" % INDEXNOW_KEY,
        "urlList": 주소[:10000],
    }).encode()
    요청 = urllib.request.Request(
        "https://api.indexnow.org/IndexNow", data=몸통,
        headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(요청, timeout=20) as r:
            코드 = r.status
    except Exception as e:
        print("   [색인] 알림 실패: %s" % e)
        print("          사이트는 올라갔다. 나중에 다시 배포하면 재시도한다.")
        return
    if 코드 in (200, 202):
        기록.write_text(str(time.time()))
        print("   [색인] %d개 주소 알림 완료 (HTTP %d)" % (len(주소), 코드))
    else:
        print("   [색인] 거절됨 HTTP %d — 키 파일을 확인해라" % 코드)


def main():
    실행 = "--실행" in sys.argv
    dist = Path(os.environ.get("TEMP", "/tmp")) / "ddasom_dist"
    빠진것 = 담기(dist)
    if "--사진기준" in sys.argv:
        지금 = 사진목록(dist)
        사진기록쓰기(지금, "기준(--사진기준: 이미 공개된 것으로 기록)")
        print("   [사진] 지금 담긴 사진 %d장을 이미 공개된 기준으로 기록했다 → %s" % (len(지금), 배포기록경로()))
        return 0
    사진체크, 새사진, 지금사진 = 사진관문(dist, 예약=실행)
    수 = sum(1 for _ in dist.rglob("*") if _.is_file())
    크기 = sum(f.stat().st_size for f in dist.rglob("*") if f.is_file()) / 1024 / 1024
    print("■ ddasom.com  →  Cloudflare Pages 프로젝트 `%s`" % PROJECT)
    print("   %d장 · %.0fMB" % (수, 크기))
    if 빠진것:
        print("   [주의] 목록에 있는데 파일이 없다: %s" % ", ".join(빠진것))
    if not 실행:
        print("   미리보기 — 실제로 올리려면 --실행")
        return 0

    tk = 토큰()
    if not tk:
        print("   [멈춤] Cloudflare API 토큰을 못 찾았다.")
        print("          .cloudflare_token 에 한 줄로 넣어라.")
        if 새사진:
            사진체크.예약해제("토큰 없음 — 업로드 안 함")
        return 1
    환경 = dict(os.environ)
    환경["CLOUDFLARE_API_TOKEN"] = tk
    # --branch=main 을 안 주면 로컬 깃 가지를 보고 미리보기로 올라간다.
    r = subprocess.run(
        ["npx", "--yes", "wrangler", "pages", "deploy", str(dist),
         "--project-name=" + PROJECT, "--branch=main", "--commit-dirty=true"],
        cwd=str(ROOT), shell=True, env=환경)
    if r.returncode != 0:
        print("   [실패] 업로드가 안 됐다 — 사이트는 그대로다")
        if 새사진:
            사진체크.예약해제("홈페이지 배포 실패")
        return r.returncode
    print("   올라갔다 → https://ddasom.com/")
    if 새사진:
        try:
            사진체크.사용등록([str(dist / x) for x in 새사진],
                          "홈페이지 배포(ddasom.com): %s%s" % (새사진[0], " 외 %d장" % (len(새사진) - 1) if len(새사진) > 1 else ""))
        except Exception as e:
            print("   ★사진 사용 등록 실패(%s) — 예약은 남아 계속 막힌다. 사진사용등록.py 로 직접 등록할 것" % e)
    사진기록쓰기(지금사진, "배포 성공")
    색인알림(dist)
    return 0


if __name__ == "__main__":
    sys.exit(main())
