# -*- coding: utf-8 -*-
"""따솜커튼블라인드 사이트 빌드 스크립트.

reviews/YYYY-MM-DD-*.html 후기 페이지들을 읽어
  1) reviews/index.html 목록(REVIEWS:START~END 사이)을 다시 생성하고
  2) sitemap.xml 을 다시 생성한다.

사용법:  python build.py
새 후기를 올리는 절차는 reviews/_template.html 참고.
"""
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
REVIEWS = ROOT / "reviews"

BASE_URL = "https://ddasom.com"


def parse_post(path: Path):
    html = path.read_text(encoding="utf-8")
    m = re.match(r"(\d{4}-\d{2}-\d{2})-", path.name)
    post_date = m.group(1) if m else ""
    title = re.search(r"<title>(.*?)\s*\|", html, re.S)
    desc = re.search(r'<meta name="description" content="(.*?)"', html)
    img = re.search(r'<img src="(img/[^"]+)"', html)
    return {
        "file": path.name,
        "date": post_date,
        "title": title.group(1).strip() if title else path.stem,
        "desc": desc.group(1) if desc else "",
        "thumb": img.group(1) if img else "",
    }


def build_list(posts):
    index = REVIEWS / "index.html"
    html = index.read_text(encoding="utf-8")
    if not posts:
        cards = '<div class="empty-state">첫 시공후기를 준비 중입니다. 곧 만나보실 수 있어요 🪟</div>'
    else:
        items = []
        for p in posts:
            thumb = (
                f'<span class="thumb"><img src="{p["thumb"]}" alt="{p["title"]}" loading="lazy"></span>'
                if p["thumb"]
                else '<span class="thumb"></span>'
            )
            y, mo, d = p["date"].split("-")
            # 카드 설명도 문장 단위 줄바꿈 (모바일에선 br.bd 숨김)
            desc = re.sub(r"(?<=[가-힣])\. (?=.)", '.<br class="bd">', p["desc"])
            items.append(
                f'<a class="review-card" href="{p["file"]}">{thumb}'
                f'<span class="body"><span class="date">{y}년 {int(mo)}월 {int(d)}일</span>'
                f'<h2>{p["title"]}</h2><p>{desc}</p></span></a>'
            )
        cards = "\n".join(items)
    html = re.sub(
        r"(<!-- REVIEWS:START.*?-->).*?(<!-- REVIEWS:END -->)",
        lambda m: m.group(1) + "\n" + cards + "\n" + m.group(2),
        html,
        flags=re.S,
    )
    index.write_text(html, encoding="utf-8")


def build_home_gallery(posts):
    """홈 갤러리를 최신 후기 6개의 썸네일로 교체. 후기가 없으면 기본 일러스트 유지."""
    withthumb = [p for p in posts if p["thumb"]][:6]
    if not withthumb:
        print("[skip] home gallery unchanged (no posts with photos yet)")
        return
    items = "\n".join(
        f'      <a class="g-item" href="reviews/{p["file"]}">'
        f'<img src="reviews/{p["thumb"]}" alt="{p["title"]}" loading="lazy">'
        f'<span class="g-label">{p["title"]}</span></a>'
        for p in withthumb
    )
    index = ROOT / "index.html"
    html = index.read_text(encoding="utf-8")
    html = re.sub(
        r"(<!-- GALLERY:START.*?-->).*?(<!-- GALLERY:END -->)",
        lambda m: m.group(1) + "\n" + items + "\n" + m.group(2),
        html,
        flags=re.S,
    )
    index.write_text(html, encoding="utf-8")
    print(f"[ok] home gallery ({len(withthumb)} thumbnails)")


def build_sitemap(posts):
    if not BASE_URL:
        print("[skip] BASE_URL not set - sitemap.xml not generated (set it after deploy)")
        return
    today = date.today().isoformat()
    urls = [(f"{BASE_URL}/", today), (f"{BASE_URL}/reviews/", today)]
    urls += [(f"{BASE_URL}/reviews/{p['file']}", p["date"]) for p in posts]
    body = "\n".join(
        f"  <url><loc>{loc}</loc><lastmod>{mod}</lastmod></url>" for loc, mod in urls
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n</urlset>\n"
    )
    (ROOT / "sitemap.xml").write_text(xml, encoding="utf-8")
    print(f"[ok] sitemap.xml ({len(urls)} urls)")


def main():
    posts = sorted(
        (parse_post(p) for p in REVIEWS.glob("2*.html")),
        key=lambda p: p["date"],
        reverse=True,
    )
    build_list(posts)
    print(f"[ok] reviews/index.html ({len(posts)} posts)")
    build_home_gallery(posts)
    build_sitemap(posts)


if __name__ == "__main__":
    sys.exit(main())
