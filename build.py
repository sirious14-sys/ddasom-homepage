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


# 대구·경북 시·군 전체 — 여기 없는 지역(대전 등)은 목록 필터에서 "기타지역"으로 묶는다.
# (제목·CTA에는 실제 지역명 유지: "대전 이실장 …")
GB_REGIONS = {
    "대구", "포항", "경주", "김천", "안동", "구미", "영주", "영천", "상주", "문경",
    "경산", "군위", "의성", "청송", "영양", "영덕", "청도", "고령", "성주", "칠곡",
    "예천", "봉화", "울진", "울릉",
}


def chip_region(region: str) -> str:
    """목록 필터용 지역: 대구·경북 밖이면 '기타지역'."""
    return region if region in GB_REGIONS else "기타지역"


# 지역별 담당 실장 (정실장: 대구권+경북 서부, 이실장: 경북 동북부)
JEONG_REGIONS = {"대구", "경산", "구미", "김천", "청도", "칠곡", "성주", "군위", "고령"}


def manager_of(region: str):
    """지역 → (실장명, 전화번호). 정실장 담당이 아니면 이실장."""
    if region in JEONG_REGIONS:
        return ("정실장", "010-5495-9500")
    return ("이실장", "010-2825-7275")


# 지역 페이지(areas/*.html)용 영문 슬러그 — URL은 영문 규칙.
REGION_SLUG = {
    "대구": "daegu", "포항": "pohang", "경주": "gyeongju", "안동": "andong",
    "경산": "gyeongsan", "구미": "gumi", "김천": "gimcheon", "영천": "yeongcheon",
    "영주": "yeongju", "의성": "uiseong", "울진": "uljin", "영덕": "yeongdeok",
    "청송": "cheongsong", "봉화": "bonghwa", "영양": "yeongyang", "문경": "mungyeong",
    "상주": "sangju", "예천": "yecheon", "울릉": "ulleung", "청도": "cheongdo",
    "칠곡": "chilgok", "성주": "seongju", "군위": "gunwi", "고령": "goryeong",
    "대전": "daejeon",
}

_MCTA_SVG = ('<svg viewBox="0 0 24 24"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5'
             'L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/></svg>')


def apply_cta(path, region):
    """후기 페이지의 CTA를 그 지역 담당 실장 한 명으로 통일 ('포항 이실장 …')."""
    if not region:
        return
    mgr, tel = manager_of(region)
    label = f"{region} {mgr} {tel}"
    html = path.read_text(encoding="utf-8")
    # post-cta 안내박스: 전화 버튼(1개 이상) → 담당 실장 1개
    html = re.sub(
        r'(<div class="post-cta">.*?</p>)\s*(?:<a[^>]*class="btn btn-tel"[^>]*>.*?</a>\s*)+(</div>)',
        lambda m: f'{m.group(1)}\n    <a href="tel:{tel}" class="btn btn-tel">{label}</a>\n  {m.group(2)}',
        html, flags=re.S,
    )
    # 모바일 하단 바: 담당 실장 1개(전체폭)
    html = re.sub(
        r'<div class="mobile-cta">.*?</div>',
        f'<div class="mobile-cta"><a href="tel:{tel}" class="m-tel">{_MCTA_SVG}'
        f'<span>{region} {mgr} 전화</span></a></div>',
        html, flags=re.S,
    )
    path.write_text(html, encoding="utf-8")


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
            region = chip_region(region_of(p["title"]))
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
        r = chip_region(region_of(p["title"]))
        counts[r] = counts.get(r, 0) + 1
    regions = sorted(counts, key=lambda r: (r == "기타지역", r))  # 가나다순, 기타지역은 맨 뒤
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
    # 거실
    ("2026-07-17-pohang-yangdeok-linen.html", "pohang-pungrim/01.jpg", "거실", "커튼", "거실 · ㄱ자 린넨커튼"),
    ("2026-06-30-yeongju-gaheung-curtain.html", "yeongju-gaheung/01.jpg", "거실", "커튼", "거실 · 헤비쉬폰 커튼"),
    ("2026-07-01-andong-jeongha-curtain.html", "andong-jeongha/01.jpg", "거실", "커튼", "거실 · 베이지 2중커튼"),
    ("2026-07-10-gyeongju-gampo-curtain.html", "gyeongju-gampo/01.jpg", "거실", "커튼", "거실 · 2중커튼"),
    ("2026-06-27-andong-okdong-double.html", "andong-okdong/01.jpg", "거실", "커튼", "거실 · 2중커튼"),
    ("2026-06-24-gumi-okgye-curtain.html", "gumi-okgye/01.jpg", "거실", "커튼", "거실 · 헤비쉬폰 2중커튼"),
    ("2026-06-24-pohang-jangseong-combi.html", "pohang-jangseong/01.jpg", "거실", "커튼", "거실 · 헤비쉬폰 커튼"),
    ("2026-06-24-yeongcheon-geumho-sheer.html", "yeongcheon-geumho/01.jpg", "거실", "커튼", "주택 통창 · 헤비쉬폰 커튼"),
    ("2026-06-08-andong-seodongmun-sheer.html", "andong-seodongmun/01.jpg", "거실", "커튼", "전면 통창 · 헤비쉬폰"),
    ("2026-06-20-yeongdeok-jipum-blackout.html", "yeongdeok-jipum/01.jpg", "거실", "커튼", "거실 · 암막커튼"),
    ("2026-07-16-daejeon-jukdong-combi.html", "daejeon-jukdong/01.jpg", "거실", "블라인드", "거실 · 우드룩 콤비블라인드"),
    ("2026-06-04-pohang-jukdo-rollscreen.html", "pohang-jukdo/01.jpg", "거실", "롤스크린", "베란다 · 암막 롤스크린"),
    ("2026-07-17-pohang-yangdeok-linen.html", "pohang-pungrim/05.jpg", "거실", "롤스크린", "베란다 · 아이보리 롤스크린"),
    # 침실
    ("2026-07-01-andong-jeongha-curtain.html", "andong-jeongha/03.jpg", "침실", "커튼", "안방 · 2중커튼"),
    ("2026-06-30-yeongju-gaheung-curtain.html", "yeongju-gaheung/04.jpg", "침실", "커튼", "아이방 · 인디언핑크 커튼"),
    ("2026-06-27-andong-okdong-double.html", "andong-okdong/03.jpg", "침실", "커튼", "안방 · 인디언핑크 암막"),
    ("2026-06-21-yeongju-apt-blackout.html", "yeongju-apt/01.jpg", "침실", "커튼", "안방 · 진그레이 암막커튼"),
    ("2026-07-11-pohang-hansin-combi.html", "pohang-hansin/01.jpg", "침실", "블라인드", "안방 · 콤비블라인드"),
    ("2026-07-13-uiseong-combi.html", "uiseong-gisuksa/01.jpg", "침실", "블라인드", "원룸 · 아이보리 콤비블라인드"),
    ("2026-06-30-yeongju-gaheung-curtain.html", "yeongju-gaheung/05.jpg", "침실", "블라인드", "놀이방 · 콤비블라인드"),
    ("2026-07-01-gyeongju-hwangseong-combi.html", "gyeongju-hwangseong/01.jpg", "침실", "블라인드", "방 · 콤비블라인드"),
    ("2026-06-24-pohang-jangseong-combi.html", "pohang-jangseong/04.jpg", "침실", "블라인드", "작은방 · 콤비블라인드"),
    ("2026-07-16-daejeon-jukdong-combi.html", "daejeon-jukdong/03.jpg", "침실", "롤스크린", "안방 · 화이트 암막롤스크린"),
    # 상가·사무실
    ("2026-07-09-yeongcheon-combi.html", "yeongcheon-sangga/01.jpg", "상가·사무실", "블라인드", "상가 통창 · 콤비블라인드"),
    ("2026-06-05-pohang-unislat.html", "pohang-unislat/01.jpg", "상가·사무실", "블라인드", "상가 매장 · 유니슬랫"),
    ("2026-06-21-gyeongsan-cafe-wood.html", "gyeongsan-cafe/01.jpg", "상가·사무실", "블라인드", "카페 · 우드블라인드"),
    ("2026-06-07-pohang-daejam-combi.html", "pohang-daejam/01.jpg", "상가·사무실", "블라인드", "임대 공간 · 진그레이 콤비"),
    ("2026-07-08-cheongsong-rollscreen.html", "cheongsong-garden/01.jpg", "상가·사무실", "롤스크린", "음식점 홀 · 채광조절 롤스크린"),
]


def build_home_gallery(posts):
    """홈 '시공 갤러리'를 GALLERY_ITEMS(공간·제품 태그)로 채운다."""
    existing = {p["file"] for p in posts}
    # 갤러리에 한 장도 안 들어간 후기가 있으면 크게 경고 (새 후기 넣고 갤러리 깜빡 방지)
    featured = {f for f, *_ in GALLERY_ITEMS}
    missing = [p["file"] for p in posts if p["file"] not in featured]
    if missing:
        print(f"[WARN] 갤러리에 안 들어간 후기 {len(missing)}건 → GALLERY_ITEMS에 추가하세요:")
        for f in missing:
            print(f"        - {f}")
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


# ── 지역 페이지 (areas/<slug>.html) ──────────────────────────────
# 후기가 1건 이상 있는 지역만 생성한다(빈 페이지 = 검색 감점). 새 후기가
# 쌓이면 build.py 실행만으로 해당 지역 페이지가 자동 생성·갱신된다.
AREA_TMPL = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__REGION__ 커튼·블라인드 시공 업체 | 따솜커튼블라인드 (무료 출장 실측)</title>
<meta name="description" content="__REGION__ 커튼·블라인드 출장 시공은 따솜커튼블라인드. __REGION__ 전지역 무료 방문 실측부터 속커튼·암막커튼·콤비블라인드·롤스크린 맞춤 시공까지. __REGION__ 담당 __MGR__ __TEL__. 실제 시공후기 확인.">
<link rel="canonical" href="https://ddasom.com/areas/__SLUG__.html">
<meta property="og:type" content="article">
<meta property="og:site_name" content="따솜커튼블라인드">
<meta property="og:title" content="__REGION__ 커튼·블라인드 시공 업체 | 따솜커튼블라인드">
<meta property="og:description" content="__REGION__ 전지역 커튼·블라인드 무료 출장 실측·맞춤 시공. __REGION__ 담당 __MGR__ __TEL__.">
<meta property="og:url" content="https://ddasom.com/areas/__SLUG__.html">
<meta property="og:image" content="__OGIMG__">
<script type="application/ld+json">
__JSONLD__
</script>
<style>
:root{--bg:#f7f4ee;--bg2:#efe9df;--ink:#211b14;--soft:#7b7061;--line:#e2dacb;--accent:#a4713f;--accent2:#8a5c31;--dark:#221b13;--white:#fff;--sans:-apple-system,'Pretendard','Noto Sans KR',sans-serif}
*{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{font-family:var(--sans);color:var(--ink);background:var(--bg);line-height:1.75;word-break:keep-all;font-size:17px;padding-bottom:80px}
.wrap{max-width:820px;margin:0 auto;padding:0 22px}
a{color:inherit;text-decoration:none}
.crumb{font-size:13px;color:var(--soft);padding:18px 0 0}
.crumb a{color:var(--accent2)}
.hero{padding:22px 0 26px;border-bottom:1px solid var(--line)}
.tag{display:inline-block;background:#fbf3ea;color:var(--accent2);border:1px solid #ecdcc7;border-radius:20px;padding:5px 14px;font-size:13px;font-weight:600;margin-bottom:14px}
h1{font-size:30px;font-weight:800;letter-spacing:-.035em;line-height:1.3}
.hero p{color:var(--soft);margin-top:12px;font-size:16px}
.mgr{display:flex;align-items:center;gap:12px;background:var(--white);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin-top:20px}
.mgr .who{font-size:14px;color:var(--soft)}
.mgr .tel{font-size:20px;font-weight:800;letter-spacing:-.02em}
.mgr a.call{margin-left:auto;background:var(--accent);color:#fff;border-radius:11px;padding:12px 18px;font-weight:700;font-size:15px}
h2{font-size:21px;font-weight:800;letter-spacing:-.03em;margin:38px 0 14px}
p.body{margin:0 0 9px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px;margin-top:6px}
.card{background:var(--white);border:1px solid var(--line);border-radius:14px;overflow:hidden;transition:.15s}
.card:hover{transform:translateY(-2px);box-shadow:0 8px 22px rgba(90,70,40,.1)}
.card img{width:100%;aspect-ratio:4/3;object-fit:cover;display:block}
.card .cap{padding:12px 14px}
.card .cap b{display:block;font-size:15px;font-weight:700}
.card .cap span{font-size:13px;color:var(--soft)}
.prod{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
.prod div{background:var(--bg2);border-radius:12px;padding:15px 16px}
.prod b{font-size:15px}
.prod p{font-size:14px;color:var(--soft);margin-top:3px}
.faq details{border:1px solid var(--line);border-radius:12px;background:var(--white);margin-bottom:10px;padding:2px 4px}
.faq summary{cursor:pointer;font-weight:700;font-size:16px;padding:14px 16px;list-style:none}
.faq summary::-webkit-details-marker{display:none}
.faq summary::after{content:"+";float:right;color:var(--accent);font-weight:800}
.faq details[open] summary::after{content:"−"}
.faq p{padding:0 16px 16px;color:var(--soft);font-size:15px}
.cta-final{background:var(--dark);color:#f3ece1;border-radius:16px;padding:28px 24px;margin:40px 0 10px;text-align:center}
.cta-final h2{color:#fff;margin:0 0 8px}
.cta-final p{color:#d8cbb6;font-size:15px;margin-bottom:18px}
.cta-final a{display:inline-block;background:var(--accent);color:#fff;font-weight:800;border-radius:12px;padding:14px 26px;font-size:17px}
.foot{text-align:center;color:var(--soft);font-size:13px;padding:28px 0;line-height:1.8}
.mbar{position:fixed;left:0;right:0;bottom:0;display:flex;background:var(--accent);z-index:30}
.mbar a{flex:1;text-align:center;color:#fff;font-weight:700;padding:16px 0;font-size:16px}
.mbar a+a{border-left:1px solid rgba(255,255,255,.25)}
@media(min-width:721px){.mbar{display:none}body{padding-bottom:0}}
</style>
</head>
<body>
<div class="wrap">
  <div class="crumb"><a href="../">따솜커튼블라인드</a> › __REGION__ 커튼·블라인드 시공</div>

  <div class="hero">
    <span class="tag">__REGION__ 전지역 출장 시공</span>
    <h1>__REGION__ 커튼·블라인드 시공,<br>따솜이 직접 방문합니다</h1>
    <p>__REGION__ 아파트·주택·상가 어디든 무료 방문 실측부터 맞춤 제작·설치까지.<br>창에 직접 원단을 대보고 색을 고른 뒤 시공하니 실패가 없습니다.</p>
    <div class="mgr">
      <div><div class="who">__REGION__ 담당</div><div class="tel">__MGR__ __TEL__</div></div>
      <a class="call" href="tel:__TEL__">전화 상담</a>
    </div>
  </div>

  <h2>__REGION__에서 커튼·블라인드, 어디서 해야 할까요?</h2>
  <p class="body">커튼·블라인드는 매장을 돌며 비교하기가 쉽지 않습니다.</p>
  <p class="body">따솜커튼블라인드는 <b>__REGION__ 전지역 출장 전문</b>입니다.</p>
  <p class="body">방문 실측 → 원단·색 상담 → 맞춤 제작 → 설치까지 한 번에 끝냅니다.</p>
  <p class="body">별도 매장을 방문하실 필요 없이,<br>__REGION__ 담당 <b>__MGR__(__TEL__)</b>이 직접 찾아갑니다.</p>
  <p class="body">창 사이즈를 재고 어울리는 제품을 제안해 드립니다.</p>
  <p class="body">실측과 견적은 <b>무료</b>입니다.</p>

  <h2>__REGION__ 실제 시공 후기</h2>
  <div class="cards">
__CARDS__
  </div>

  <h2>__REGION__에서 많이 하는 제품</h2>
  <div class="prod">
    <div><b>속커튼·암막커튼</b><p>거실·안방에 2중으로. 채광과 암막을 상황따라 조절</p></div>
    <div><b>콤비블라인드</b><p>투명·불투명 원단이 겹쳐 채광 조절이 자유로운 인기 제품</p></div>
    <div><b>롤스크린</b><p>단정하고 깔끔한 마감. 베란다·주방·상가에 적합</p></div>
    <div><b>우드·전동 블라인드</b><p>카페·사무실·통창에 어울리는 고급 마감과 편의</p></div>
  </div>

  <h2>__REGION__ 커튼 자주 묻는 질문</h2>
  <div class="faq">
    <details open><summary>__REGION__도 출장 시공되나요?</summary><p>네, __REGION__ 전지역에 출장 시공합니다.<br>__REGION__ 담당 __MGR__(__TEL__)이 직접 방문합니다.</p></details>
    <details><summary>실측·견적 비용이 드나요?</summary><p>__REGION__ 지역 방문 실측과 견적은 무료입니다.<br>창에 제품을 대보며 상담한 뒤 견적을 드립니다.</p></details>
    <details><summary>어떤 제품까지 시공하나요?</summary><p>속커튼·암막커튼·콤비블라인드·롤스크린까지,<br>우드·전동 블라인드도 맞춤 제작·시공합니다.</p></details>
    <details><summary>상담은 어떻게 하나요?</summary><p>전화나 문자로 __MGR__(__TEL__)에게 연락 주세요.<br><a href="../#apply" style="color:var(--accent2);font-weight:700">실측 신청 폼</a>에 성함·연락처·지역을 남기셔도 됩니다.</p></details>
  </div>

  <div class="cta-final">
    <h2>__REGION__ 커튼·블라인드, 무료로 상담받으세요</h2>
    <p>창 사진만 있어도 대략 견적 안내가 가능합니다.<br>__REGION__ 담당 __MGR__이 도와드립니다.</p>
    <a href="tel:__TEL__">__MGR__ __TEL__ 전화</a>
  </div>

  <p class="foot">따솜커튼블라인드 · 대구·경북 전지역 커튼·블라인드 출장 시공<br>
  <a href="../" style="color:var(--accent2)">ddasom.com 홈으로</a> · <a href="../reviews/" style="color:var(--accent2)">전체 시공후기</a></p>
</div>

<div class="mbar">
  <a href="tel:__TEL__">전화</a>
  <a href="sms:__TEL__?&body=__REGION__ 커튼·블라인드 실측 신청합니다.">문자</a>
</div>
</body>
</html>
"""


def _area_jsonld(region, slug, mgr, tel, ogimg):
    import json as _json
    graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebPage",
                "@id": f"https://ddasom.com/areas/{slug}.html#webpage",
                "url": f"https://ddasom.com/areas/{slug}.html",
                "name": f"{region} 커튼·블라인드 시공 업체 | 따솜커튼블라인드",
                "inLanguage": "ko",
                "about": {"@type": "City", "name": region},
                "isPartOf": {"@id": "https://ddasom.com/#website"},
                "provider": {"@id": "https://ddasom.com/#business"},
                "description": f"{region} 전지역 커튼·블라인드 무료 출장 실측 및 맞춤 시공. {region} 담당 {mgr} {tel}.",
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "따솜커튼블라인드", "item": "https://ddasom.com/"},
                    {"@type": "ListItem", "position": 2, "name": f"{region} 커튼·블라인드 시공", "item": f"https://ddasom.com/areas/{slug}.html"},
                ],
            },
            {
                "@type": "Service",
                "name": f"{region} 커튼·블라인드 출장 시공",
                "serviceType": "커튼·블라인드 맞춤 제작 및 시공",
                "provider": {"@id": "https://ddasom.com/#business"},
                "areaServed": {"@type": "City", "name": region},
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "KRW", "description": "방문 실측·견적 무료"},
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {"@type": "Question", "name": f"{region}에서 커튼·블라인드 시공을 맡길 수 있나요?",
                     "acceptedAnswer": {"@type": "Answer", "text": f"네. 따솜커튼블라인드는 {region} 전지역에 출장 시공합니다. {region} 지역은 {mgr}({tel})이 담당해 무료 방문 실측부터 맞춤 제작·설치까지 직접 진행합니다."}},
                    {"@type": "Question", "name": f"{region} 커튼 실측·견적 비용이 있나요?",
                     "acceptedAnswer": {"@type": "Answer", "text": f"{region} 지역 방문 실측과 견적은 무료입니다. 창에 직접 원단과 제품을 대보며 색과 스타일을 상담한 뒤 견적을 드립니다."}},
                    {"@type": "Question", "name": f"{region}에서 어떤 제품을 시공하나요?",
                     "acceptedAnswer": {"@type": "Answer", "text": f"속커튼·암막커튼 등 커튼류와 콤비블라인드·롤스크린·우드블라인드·전동 블라인드까지 {region} 아파트·주택·상가에 맞춤 시공합니다."}},
                ],
            },
        ],
    }
    if ogimg:
        graph["@graph"][0]["primaryImageOfPage"] = ogimg
    return _json.dumps(graph, ensure_ascii=False, indent=2)


def build_area_pages(posts):
    """후기가 있는 지역마다 areas/<slug>.html 생성. (지역, 슬러그, 후기수) 목록 반환."""
    area_dir = ROOT / "areas"
    area_dir.mkdir(exist_ok=True)
    by_region = {}
    for p in posts:
        r = region_of(p["title"])
        if r in REGION_SLUG:
            by_region.setdefault(r, []).append(p)
    infos = []
    for region, rposts in by_region.items():
        slug = REGION_SLUG[region]
        mgr, tel = manager_of(region)
        cards = []
        for p in rposts[:6]:  # 최신 6건까지
            thumb = (f'<img src="../reviews/{p["thumb"]}" alt="{p["title"]} 시공 사진" loading="lazy">'
                     if p["thumb"] else "")
            desc = p["desc"][:46] + ("…" if len(p["desc"]) > 46 else "")
            cards.append(
                f'    <a class="card" href="../reviews/{p["file"]}">{thumb}'
                f'<span class="cap"><b>{p["title"]}</b><span>{desc}</span></span></a>'
            )
        ogimg = f'{BASE_URL}/reviews/{rposts[0]["thumb"]}' if rposts[0]["thumb"] else ""
        html = (AREA_TMPL
                .replace("__JSONLD__", _area_jsonld(region, slug, mgr, tel, ogimg))
                .replace("__REGION__", region)
                .replace("__SLUG__", slug)
                .replace("__MGR__", mgr)
                .replace("__TEL__", tel)
                .replace("__OGIMG__", ogimg)
                .replace("__CARDS__", "\n".join(cards)))
        (area_dir / f"{slug}.html").write_text(html, encoding="utf-8")
        infos.append((region, slug, len(rposts)))
    infos.sort(key=lambda x: -x[2])  # 후기 많은 순
    print(f"[ok] areas/ 지역 페이지 {len(infos)}개: " + ", ".join(f"{r}({n})" for r, s, n in infos))
    return infos


def build_home_areas(infos):
    """홈 index.html의 AREAS:START~END 사이를 지역 페이지 링크로 채운다."""
    index = ROOT / "index.html"
    html = index.read_text(encoding="utf-8")
    if "AREAS:START" not in html:
        print("[skip] index.html에 AREAS 마커 없음")
        return
    links = "\n".join(
        f'      <a class="area-link" href="areas/{slug}.html">{region} 출장 시공 <span>후기 {n}건</span></a>'
        for region, slug, n in infos
    )
    html = re.sub(
        r"(<!-- AREAS:START.*?-->).*?(<!-- AREAS:END -->)",
        lambda m: m.group(1) + "\n" + links + "\n" + m.group(2),
        html, flags=re.S,
    )
    index.write_text(html, encoding="utf-8")
    print(f"[ok] home areas 섹션 ({len(infos)} links)")


def build_sitemap(posts, areas=()):
    if not BASE_URL:
        print("[skip] BASE_URL not set - sitemap.xml not generated (set it after deploy)")
        return
    today = date.today().isoformat()
    urls = [(f"{BASE_URL}/", today), (f"{BASE_URL}/reviews/", today)]
    urls += [(f"{BASE_URL}/areas/{slug}.html", today) for _r, slug, _n in areas]
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
    # 각 후기 CTA를 그 지역 담당 실장으로 통일
    for p in posts:
        apply_cta(REVIEWS / p["file"], region_of(p["title"]))
    build_list(posts)
    print(f"[ok] reviews/index.html ({len(posts)} posts, CTA=지역 담당 실장)")
    build_home_gallery(posts)
    areas = build_area_pages(posts)
    build_home_areas(areas)
    build_sitemap(posts, areas)


if __name__ == "__main__":
    sys.exit(main())
