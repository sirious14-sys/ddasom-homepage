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

# 대구는 구/군으로 안 나누고 "대구" 하나로 묶는다 (경북은 시·군별 유지).
# 후기 제목 첫 단어가 아래에 있으면 지역을 "대구"로 통일. (제목은 "대구 …"로 시작 권장)
DAEGU_ALIAS = {"대구", "수성구", "달서구", "달성군", "군위군"}


def region_of(title: str) -> str:
    """후기 제목 첫 단어 = 지역. 단, 대구 구/군은 '대구'로 통일."""
    if not title:
        return ""
    first = title.split()[0]
    return "대구" if first in DAEGU_ALIAS else first


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
    region_order = []  # 등장 순서 유지용
    if not posts:
        cards = '<div class="empty-state">첫 시공후기를 준비 중입니다. 곧 만나보실 수 있어요 🪟</div>'
    else:
        items = []
        for p in posts:
            region = region_of(p["title"])
            if region and region not in region_order:
                region_order.append(region)
            thumb = (
                f'<span class="thumb"><img src="{p["thumb"]}" alt="{p["title"]}" loading="lazy"></span>'
                if p["thumb"]
                else '<span class="thumb"></span>'
            )
            y, mo, d = p["date"].split("-")
            # 카드 설명도 문장 단위 줄바꿈 (모바일에선 br.bd 숨김)
            desc = re.sub(r"(?<=[가-힣])\. (?=.)", '.<br class="bd">', p["desc"])
            items.append(
                f'<a class="review-card" href="{p["file"]}" data-region="{region}">{thumb}'
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
    # 지역 필터 칩 — 가나다순 + 지역별 후기 개수 표시 (지역이 많아져도 한눈에)
    counts = {}
    for p in posts:
        r = region_of(p["title"])
        counts[r] = counts.get(r, 0) + 1
    regions = sorted(counts)  # 가나다순
    chips = [f'  <button class="chip active" data-filter="전체">전체 <span class="chip-n">{len(posts)}</span></button>']
    chips += [
        f'  <button class="chip" data-filter="{r}">{r} <span class="chip-n">{counts[r]}</span></button>'
        for r in regions
    ]
    html = re.sub(
        r"(<!-- FILTERS:START.*?-->).*?(<!-- FILTERS:END -->)",
        lambda m: m.group(1) + "\n" + "\n".join(chips) + "\n" + m.group(2),
        html,
        flags=re.S,
    )
    index.write_text(html, encoding="utf-8")


# 홈 "시공 갤러리" 룩북 — 필터형(공간·제품). 새 후기 추가 시 아래 목록에 한 줄 추가.
#   (후기파일, 이미지경로(reviews/img/... 기준), 공간, 제품, 라벨)
#   공간 ∈ {거실, 침실, 상가·사무실}  ·  제품 ∈ {커튼, 블라인드, 롤스크린}
#   ※ index.html의 필터 칩(data-filter)과 태그 문자열이 정확히 일치해야 함.
GALLERY_ITEMS = [
    ("2026-06-30-yeongju-gaheung-curtain.html", "yeongju-gaheung/01.jpg", "거실", "커튼", "거실 · 헤비쉬폰 커튼"),
    ("2026-07-01-andong-jeongha-curtain.html", "andong-jeongha/01.jpg", "거실", "커튼", "거실 · 베이지 2중커튼"),
    ("2026-07-10-gyeongju-gampo-curtain.html", "gyeongju-gampo/01.jpg", "거실", "커튼", "거실 · 2중커튼"),
    ("2026-06-04-pohang-jukdo-rollscreen.html", "pohang-jukdo/01.jpg", "거실", "롤스크린", "베란다 · 암막 롤스크린"),
    ("2026-07-01-andong-jeongha-curtain.html", "andong-jeongha/03.jpg", "침실", "커튼", "안방 · 2중커튼"),
    ("2026-06-30-yeongju-gaheung-curtain.html", "yeongju-gaheung/04.jpg", "침실", "커튼", "아이방 · 인디언핑크 커튼"),
    ("2026-07-11-pohang-hansin-combi.html", "pohang-hansin/01.jpg", "침실", "블라인드", "안방 · 콤비블라인드"),
    ("2026-07-13-uiseong-combi.html", "uiseong-gisuksa/01.jpg", "침실", "블라인드", "원룸 · 아이보리 콤비블라인드"),
    ("2026-06-30-yeongju-gaheung-curtain.html", "yeongju-gaheung/05.jpg", "침실", "블라인드", "놀이방 · 콤비블라인드"),
    ("2026-07-09-yeongcheon-combi.html", "yeongcheon-sangga/01.jpg", "상가·사무실", "블라인드", "상가 통창 · 콤비블라인드"),
    ("2026-07-08-cheongsong-rollscreen.html", "cheongsong-garden/01.jpg", "상가·사무실", "롤스크린", "음식점 홀 · 채광조절 롤스크린"),
    ("2026-06-05-pohang-unislat.html", "pohang-unislat/01.jpg", "상가·사무실", "블라인드", "상가 매장 · 유니슬랫"),
]


def build_home_gallery(posts):
    """홈 '시공 갤러리'를 GALLERY_ITEMS(공간·제품 태그)로 채운다."""
    existing = {p["file"] for p in posts}
    items = []
    for f, img, space, product, label in GALLERY_ITEMS:
        if f not in existing:
            print(f"[warn] gallery item skipped, review missing: {f}")
            continue
        items.append(
            f'      <a class="g-item" href="reviews/{f}" data-tags="{space} {product}">'
            f'<img src="reviews/img/{img}" alt="{label} 시공 사진" loading="lazy">'
            f'<span class="g-label">{label}</span></a>'
        )
    if not items:
        print("[skip] home gallery unchanged (no items)")
        return
    block = "\n".join(items) + '\n      <div class="gallery-empty">해당 조건의 시공 사진이 아직 없습니다.</div>'
    index = ROOT / "index.html"
    html = index.read_text(encoding="utf-8")
    html = re.sub(
        r"(<!-- GALLERY:START.*?-->).*?(<!-- GALLERY:END -->)",
        lambda m: m.group(1) + "\n" + block + "\n" + m.group(2),
        html,
        flags=re.S,
    )
    index.write_text(html, encoding="utf-8")
    print(f"[ok] home gallery ({len(items)} items, filterable)")


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
