# -*- coding: utf-8 -*-
"""홈페이지를 실제로 공개하는 유일한 경로.

★ 깃허브 push 는 배포가 아니다 (2026-09-05 확인).
  ddasom.com 은 Cloudflare Pages 프로젝트 `ddasom` 이 서비스하는데
  이 프로젝트는 **Git 연결이 없다(직접 업로드 방식)**.
  그래서 `git push` 를 아무리 해도 사이트는 그대로다.
  실제로 b2b 시즌 섹션·방염 가이드가 push 된 채로 며칠 안 올라가 있었다.
  깃허브는 소스 보관용, 공개는 이 파일로 한다.

사용법
    python 배포.py            미리보기 — 무엇을 올릴지만 보여준다
    python 배포.py --실행     실제 업로드
"""
import os
import shutil
import subprocess
import sys
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
    return 빠진것


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
        return r.returncode
    print("   올라갔다 → https://ddasom.com/")
    색인알림(dist)
    return 0


if __name__ == "__main__":
    sys.exit(main())
