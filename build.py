# -*- coding: utf-8 -*-
"""따솜커튼블라인드 사이트 빌드 스크립트.

reviews/YYYY-MM-DD-*.html 후기 페이지들을 읽어
  1) reviews/index.html 목록(REVIEWS:START~END 사이)을 다시 생성하고
  2) sitemap.xml 을 다시 생성한다.

사용법:  python build.py
새 후기를 올리는 절차는 reviews/_template.html 참고.
"""
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
REVIEWS = ROOT / "reviews"

BASE_URL = "https://ddasom.com"

# 대구는 구/군으로 안 나누고 "대구" 하나로 묶는다 (경북은 시·군별 유지).
# 후기 제목 첫 단어가 아래에 있으면 지역을 "대구"로 통일. (제목은 "대구 …"로 시작 권장)
DAEGU_ALIAS = {"대구", "동대구", "수성구", "달서구", "달성군", "군위군",
                "동구", "서구", "남구", "북구", "중구"}


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
# 의성은 이실장 담당이다. 홈페이지 지역 안내·견적 폼과 맞춘 값이다.
JEONG_REGIONS = {"대구", "경산", "구미", "김천", "청도", "칠곡", "성주", "군위", "고령"}


def manager_of(region: str):
    """지역 → (실장명, 전화번호). 정실장 담당이 아니면 이실장."""
    if region in JEONG_REGIONS:
        return ("정실장", "010-5495-9500")
    return ("이실장", "010-2825-7275")


def 링크(경로):
    """내부 주소에서 .html 을 뗀다.

    ddasom.com(Cloudflare Pages)은 /services.html 을 308 로 /services 에 넘긴다.
    링크가 .html 을 가리키면 사람도 크롤러도 매번 한 번씩 튕겨서 간다.
    실측 2026-09-08 — 사이트 안 링크 1,200개가 전부 그랬다.
    """
    if not 경로 or not 경로.endswith(".html"):
        return 경로
    몸 = 경로[:-5]
    if 몸.rsplit("/", 1)[-1] == "index":
        앞 = 몸[:-len("index")]
        return 앞 if 앞 else "./"
    return 몸


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
                f'<a class="review-card" href="{링크(p["file"])}" data-region="{region}">{thumb}'
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
#   공간 ∈ {거실, 침실, 상가·사무실}  ·  제품 ∈ {커튼, 블라인드, 롤스크린, 홀딩도어}
#   ※ index.html의 필터 칩(data-filter)과 태그 문자열이 정확히 일치해야 함.
GALLERY_ITEMS = [
    # 2026-09~10 후기 (사진은 각 후기의 대표 이미지)
    ("2026-10-06-daegu-duryu-education-office-rollscreen.html", "daegu-duryu-education-office-rollscreen/1.jpg", "상가·사무실", "롤스크린", "교육장 · 롤스크린"),
    ("2026-10-08-pohang-chogok-hillstate-combi-blackout-curtain.html", "pohang-chogok-hillstate-combi-blackout-curtain/2.jpg", "거실", "블라인드", "ㄱ자 거실 · 콤비블라인드·속커튼"),
    ("2026-10-07-cheongsong-solgi-apartment-blackout-rollscreen.html", "cheongsong-solgi-apartment-blackout-rollscreen/11.jpg", "침실", "롤스크린", "작은방 · 암막 롤스크린"),
    ("2026-10-02-pohang-ocheon-hillstate-combi-blackout-folding-door.html", "pohang-ocheon-hillstate-combi-blackout-folding-door/2.jpg", "거실", "블라인드", "거실 · 콤비블라인드"),
    ("2026-10-01-uljin-hupo-ocean-castle-motorized-curtain.html", "uljin-hupo-ocean-castle-motorized-curtain/3.jpg", "거실", "커튼", "바다 쪽 거실 · 전동커튼"),
    ("2026-09-18-pohang-uhyeondong-curtain-combi-blind.html", "pohang-uhyeondong-curtain-combi-blind/1.jpg", "거실", "커튼", "거실 · 커튼과 콤비블라인드"),
    ("2026-09-18-uljin-apartment-livingroom-blackout-curtain.html", "uljin-apartment-livingroom-blackout-curtain/1.jpg", "거실", "커튼", "거실 · 형상기억 암막커튼"),
    ("2026-09-23-yeongcheon-mangjeong-house-entrance-curtain.html", "yeongcheon-mangjeong-house-entrance-curtain/1.jpg", "거실", "커튼", "주택 현관 · 암막커튼"),
    ("2026-10-02-ulsan-insurance-office-rollscreen.html", "ulsan-insurance-office-rollscreen/4.jpg", "상가·사무실", "롤스크린", "사무실 유리문 · 롤스크린"),
    ("2026-10-01-andong-insurance-office-rollscreen.html", "andong-insurance-office-rollscreen/5.jpg", "상가·사무실", "롤스크린", "사무실 유리 칸막이 · 롤스크린"),
    ("2026-09-18-uiseong-shop-blackout-rollscreen.html", "uiseong-shop-blackout-rollscreen/3.jpg", "상가·사무실", "롤스크린", "상가 통유리 · 암막 롤스크린"),
    ("2026-09-15-daegu-dongseongno-hotel-sheer-curtain.html", "daegu-dongseongno-hotel-sheer-curtain/1.jpg", "상가·사무실", "커튼", "호텔 객실 · 쉬폰·방음암막커튼"),
    # 거실
    ("2026-07-18-uljin-villa.html", "uljin-villa/1.jpg", "거실", "커튼", "거실 · 헤비쉬폰 두배나비주름"),
    ("2026-07-31-pohang-hyoja-skview.html", "pohang-hyoja-skview/1.jpg", "거실", "커튼", "거실 · 인디언핑크 암막커튼"),
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
    ("2026-07-21-uiseong-sunroom-rollscreen.html", "uiseong-sunroom-rollscreen/1.jpg", "거실", "롤스크린", "썬룸 · 화이트 암막롤스크린"),
    ("2026-07-22-yeongju-hwaseong-blackout-curtain.html", "yeongju-hwaseong-blackout-curtain/1.jpg", "거실", "커튼", "거실 · 그레이 암막커튼(콤비 위 이중)"),
    ("2026-07-23-uiseong-jugong2-rollscreen.html", "uiseong-jugong2-rollscreen/2.jpg", "거실", "롤스크린", "베란다 · 연블루 채광 롤스크린"),
    ("2026-07-23-pohang-xi-atherton-fullhouse.html", "pohang-xi-atherton-fullhouse/1.jpg", "거실", "커튼", "거실 · 화이트 쉬폰 두배나비주름"),
    ("2026-07-27-gyeongju-xi-fullhouse.html", "gyeongju-xi-fullhouse/1.jpg", "거실", "블라인드", "거실 · 미색 암막 콤비블라인드"),
    ("2026-07-28-pohang-chogok-trinien.html", "pohang-chogok-trinien/1.jpg", "거실", "커튼", "거실 · 쉬폰+베이지 암막 이중커튼"),
    ("2017-07-02-gyeongsan-sangga-house.html", "gyeongsan-sangga-house/1.jpg", "거실", "블라인드", "거실 · 그레이 트리플쉐이드"),
    ("2017-07-02-gyeongsan-sangga-house.html", "gyeongsan-sangga-house/4.jpg", "거실", "블라인드", "거실 · 트리플쉐이드 부분 조절"),
    # 침실
    ("2026-07-31-pohang-hyoja-skview.html", "pohang-hyoja-skview/3.jpg", "침실", "커튼", "안방 · 인디언핑크 암막커튼"),
    ("2026-07-31-pohang-hyoja-skview.html", "pohang-hyoja-skview/6.jpg", "침실", "커튼", "작은방 · 인디언핑크 암막커튼"),
    ("2026-07-26-pohang-hyoja-blackout-curtain.html", "pohang-hyoja-blackout-curtain/2.jpg", "침실", "커튼", "안방 · 백아이보리 속커튼+암막커튼"),
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
    ("2026-07-23-pohang-xi-atherton-fullhouse.html", "pohang-xi-atherton-fullhouse/2.jpg", "침실", "커튼", "안방 · 쉬폰 속커튼+100프로 암막"),
    ("2026-07-23-pohang-xi-atherton-fullhouse.html", "pohang-xi-atherton-fullhouse/3.jpg", "침실", "블라인드", "방 · 미색 콤비블라인드"),
    ("2026-07-23-pohang-xi-atherton-fullhouse.html", "pohang-xi-atherton-fullhouse/4.jpg", "침실", "롤스크린", "알파룸(컴퓨터방) · 블랙 암막롤스크린"),
    ("2026-07-27-gyeongju-xi-fullhouse.html", "gyeongju-xi-fullhouse/3.jpg", "침실", "블라인드", "안방 · 미색 암막 콤비블라인드"),
    ("2026-07-27-gyeongju-xi-fullhouse.html", "gyeongju-xi-fullhouse/4.jpg", "침실", "블라인드", "작은방 · 암막 콤비블라인드"),
    ("2026-07-28-pohang-chogok-trinien.html", "pohang-chogok-trinien/3.jpg", "침실", "커튼", "안방 · 백아이보리 100프로 암막커튼"),
    ("2026-07-28-pohang-chogok-trinien.html", "pohang-chogok-trinien/7.jpg", "침실", "블라인드", "작은방 · 베이지 콤비블라인드"),
    ("2026-07-28-pohang-chogok-trinien.html", "pohang-chogok-trinien/9.jpg", "침실", "블라인드", "드레스룸 · 다크그레이 콤비블라인드"),
    ("2017-07-02-gyeongsan-sangga-house.html", "gyeongsan-sangga-house/5.jpg", "침실", "블라인드", "안방 · 암막 콤비블라인드"),
    ("2026-08-21-yecheon-house-blackout-curtain.html", "yecheon-house-blackout-curtain/1.jpg", "침실", "커튼", "단독주택 방 · 밝은 회색 암막커튼(블라인드 위 이중)"),
    ("2026-08-21-yecheon-house-blackout-curtain.html", "yecheon-house-blackout-curtain/8.jpg", "침실", "커튼", "두 면 창 · 같은 원단으로 맞춘 암막커튼"),
    ("2026-08-21-yecheon-house-blackout-curtain.html", "yecheon-house-blackout-curtain/4.jpg", "침실", "커튼", "밝은 회색 암막 원단 근접"),
    ("2026-08-13-cheongdo-villa-blackout-combi.html", "cheongdo-villa-blackout-combi/2.jpg", "침실", "블라인드", "안방 · 그레이 암막 콤비블라인드(벽 폭 시공)"),
    ("2026-08-13-cheongdo-villa-blackout-combi.html", "cheongdo-villa-blackout-combi/6.jpg", "침실", "블라인드", "두 짝 이음 · 슬랫 높이 맞춤"),
    ("2026-08-13-cheongdo-villa-blackout-combi.html", "cheongdo-villa-blackout-combi/7.jpg", "침실", "블라인드", "암막 콤비 원단 근접"),
    # 상가·사무실
    ("2026-05-30-yeongdeok-office-rollscreen.html", "yeongdeok-office-rollscreen/1.jpg", "상가·사무실", "롤스크린", "워크스테이션 · 화이트 암막 롤스크린"),
    ("2026-07-22-dongdaegu-cafe-wood-blind.html", "dongdaegu-cafe-wood-blind/1.jpg", "상가·사무실", "블라인드", "카페 홀 · 통창 우드블라인드"),
    ("2026-07-22-dongdaegu-cafe-wood-blind.html", "dongdaegu-cafe-wood-blind/2.jpg", "상가·사무실", "블라인드", "카페 창가 좌석 · 우드블라인드"),
    ("2026-07-22-dongdaegu-cafe-wood-blind.html", "dongdaegu-cafe-wood-blind/9.jpg", "상가·사무실", "블라인드", "카페 카운터 · 우드블라인드"),
    ("2026-05-30-yeongdeok-office-rollscreen.html", "yeongdeok-office-rollscreen/6.jpg", "상가·사무실", "롤스크린", "라운지 · 바다 뷰 남긴 롤스크린"),
    ("2026-05-30-yeongdeok-office-rollscreen.html", "yeongdeok-office-rollscreen/3.jpg", "상가·사무실", "롤스크린", "창가 복도 · 아치창 롤스크린"),
    ("2026-08-03-yeongju-office-rollscreen.html", "yeongju-office-rollscreen/1.jpg", "상가·사무실", "롤스크린", "사무실 창가 · 아이보리 암막 롤스크린"),
    ("2026-08-03-yeongju-office-rollscreen.html", "yeongju-office-rollscreen/4.jpg", "상가·사무실", "롤스크린", "교육장 · 완전 차광 암막 롤스크린"),
    ("2026-08-03-yeongju-office-rollscreen.html", "yeongju-office-rollscreen/7.jpg", "상가·사무실", "롤스크린", "회의실 · 대형 암막 롤스크린"),
    ("2026-07-09-yeongcheon-combi.html", "yeongcheon-sangga/01.jpg", "상가·사무실", "블라인드", "상가 통창 · 콤비블라인드"),
    ("2026-06-05-pohang-unislat.html", "pohang-unislat/01.jpg", "상가·사무실", "블라인드", "상가 매장 · 유니슬랫"),
    ("2026-06-21-gyeongsan-cafe-wood.html", "gyeongsan-cafe/01.jpg", "상가·사무실", "블라인드", "카페 · 우드블라인드"),
    ("2026-06-07-pohang-daejam-combi.html", "pohang-daejam/01.jpg", "상가·사무실", "블라인드", "임대 공간 · 진그레이 콤비"),
    ("2026-07-08-cheongsong-rollscreen.html", "cheongsong-garden/01.jpg", "상가·사무실", "롤스크린", "음식점 홀 · 채광조절 롤스크린"),
    ("2026-07-19-gumi-nailshop.html", "gumi-nailshop/1.jpg", "상가·사무실", "블라인드", "네일샵 전면창 · 알루미늄 블라인드"),
    ("2026-07-27-yecheon-emart24.html", "yecheon-emart24/1.jpg", "상가·사무실", "블라인드", "편의점 창가 · 베이지 콤비블라인드"),
    ("2026-07-27-yecheon-emart24.html", "yecheon-emart24/6.jpg", "상가·사무실", "블라인드", "편의점 취식대 · 시스루 콤비블라인드"),
    ("2026-07-19-gumi-nailshop.html", "gumi-nailshop/3.jpg", "상가·사무실", "커튼", "네일샵 아치 · 헤비쉬폰 커튼"),
    ("2026-07-19-gyeongsan-skincare.html", "gyeongsan-skincare/1.jpg", "상가·사무실", "커튼", "피부관리샵 칸막이 · 헤비쉬폰 커튼"),
    ("2026-07-19-gyeongsan-skincare.html", "gyeongsan-skincare/4.jpg", "상가·사무실", "커튼", "관리샵 베란다 · 헤비쉬폰 커튼"),
    ("2017-05-31-uljin-restaurant-foldingdoor.html", "uljin-restaurant-foldingdoor/1.jpg", "상가·사무실", "홀딩도어", "식당 홀 칸막이 · 우드 홀딩도어(닫힘)"),
    ("2017-05-31-uljin-restaurant-foldingdoor.html", "uljin-restaurant-foldingdoor/4.jpg", "상가·사무실", "홀딩도어", "식당 홀 칸막이 · 접어서 홀로 합친 상태"),
    ("2017-05-31-uljin-restaurant-foldingdoor.html", "uljin-restaurant-foldingdoor/2.jpg", "상가·사무실", "홀딩도어", "중앙 양개 손잡이 · 화이트 프레임"),
    ("2026-07-13-yeongcheon-clinic-curtain.html", "yeongcheon-clinic-curtain/1.jpg", "상가·사무실", "커튼", "병원 처치실 · 방염 칸막이 커튼"),
    ("2026-07-13-yeongcheon-clinic-curtain.html", "yeongcheon-clinic-curtain/3.jpg", "상가·사무실", "커튼", "베드 곡선 레일 · 세이지그린 커튼"),
    ("2026-07-13-yeongcheon-clinic-curtain.html", "yeongcheon-clinic-curtain/7.jpg", "상가·사무실", "롤스크린", "처치실 창가 · 아이보리 롤스크린"),
    ("2026-08-27-andong-yongsang-office-blackout.html", "andong-yongsang-office-blackout/1.jpg", "상가·사무실", "블라인드", "사무실 전관 · 그레이 암막 블라인드"),
    ("2026-08-27-andong-yongsang-office-blackout.html", "andong-yongsang-office-blackout/8.jpg", "상가·사무실", "블라인드", "회의실 큰 창 · 그레이 암막 블라인드"),
    ("2026-08-27-andong-yongsang-office-blackout.html", "andong-yongsang-office-blackout/6.jpg", "상가·사무실", "블라인드", "사무실 창 정면 · 하단 바 창틀선 맞춤"),
    ("2026-09-08-daegu-dongseongno-hotel-soundproof.html", "daegu-dongseongno-hotel-soundproof/4.jpg", "상가·사무실", "커튼", "호텔 객실 · 베이지 3중겹 방음커튼"),
    ("2026-09-08-daegu-dongseongno-hotel-soundproof.html", "daegu-dongseongno-hotel-soundproof/7.jpg", "상가·사무실", "커튼", "3중겹 단면 · 암막＋벨벳＋벨벳"),
    ("2026-09-08-daegu-dongseongno-hotel-soundproof.html", "daegu-dongseongno-hotel-soundproof/2.jpg", "상가·사무실", "커튼", "객실 커튼 교체 · 블루에서 베이지로"),
    ("2026-09-12-cheongsong-staff-housing-combi-blind.html", "cheongsong-staff-housing-combi-blind/1.jpg", "침실", "블라인드", "직원숙소 방 · 바닥까지 두 폭 콤비블라인드"),
    ("2026-09-12-cheongsong-staff-housing-combi-blind.html", "cheongsong-staff-housing-combi-blind/4.jpg", "거실", "블라인드", "숙소 거실 큰 창 · 그레이 콤비 두 폭"),
    ("2026-09-12-cheongsong-staff-housing-combi-blind.html", "cheongsong-staff-housing-combi-blind/6.jpg", "침실", "블라인드", "작은 방 창 · 한 폭 콤비블라인드"),
("2026-09-11-andong-okdong-restaurant-combi-blind.html", "andong-okdong-restaurant-combi-blind/3.jpg", "상가·사무실", "블라인드", "식당 모서리 전면창 · 기둥마다 한 짝 콤비블라인드"),
("2026-09-11-andong-okdong-restaurant-combi-blind.html", "andong-okdong-restaurant-combi-blind/4.jpg", "상가·사무실", "블라인드", "테이블 옆 창 · 카멜 톤 콤비블라인드"),
("2026-09-11-andong-okdong-restaurant-combi-blind.html", "andong-okdong-restaurant-combi-blind/1.jpg", "상가·사무실", "블라인드", "몰딩 아래로 올린 전면창 콤비블라인드"),
("2026-09-16-pohang-middle-school-rollscreen.html", "pohang-middle-school-rollscreen/1.jpg", "상가·사무실", "롤스크린", "학교 넓은 창 · 칸마다 나눈 베이지 롤스크린"),
("2026-09-16-pohang-middle-school-rollscreen.html", "pohang-middle-school-rollscreen/2.jpg", "상가·사무실", "롤스크린", "학교 창 · 베이지와 암막 롤스크린 두 겹"),
("2026-09-16-pohang-middle-school-rollscreen.html", "pohang-middle-school-rollscreen/8.jpg", "상가·사무실", "블라인드", "상담실 실내 창 · 허니콤블라인드"),
    ("2026-08-13-pohang-uhyeon-restaurant-rollscreen.html", "pohang-uhyeon-restaurant-rollscreen/2.jpg", "상가·사무실", "롤스크린", "식당 홀 · 화이트 방염 채광 롤스크린"),
    ("2026-08-13-pohang-uhyeon-restaurant-rollscreen.html", "pohang-uhyeon-restaurant-rollscreen/6.jpg", "상가·사무실", "롤스크린", "창 정면 · 아래 난간대는 남긴 길이"),
    ("2026-08-13-pohang-uhyeon-restaurant-rollscreen.html", "pohang-uhyeon-restaurant-rollscreen/7.jpg", "상가·사무실", "롤스크린", "세 면 창 · 한 줄로 이어진 라인"),
    ("2026-08-11-gyeongju-airbnb-blackout-curtain.html", "gyeongju-airbnb-blackout-curtain/2.jpg", "침실", "커튼", "숙소 객실 · 천장 레일 암막커튼(벽 전체)"),
    ("2026-08-11-gyeongju-airbnb-blackout-curtain.html", "gyeongju-airbnb-blackout-curtain/4.jpg", "침실", "커튼", "코너까지 이어진 암막커튼"),
    ("2026-08-11-gyeongju-airbnb-blackout-curtain.html", "gyeongju-airbnb-blackout-curtain/10.jpg", "침실", "롤스크린", "작은방 · 화이트 암막 롤스크린"),
    ("2026-08-11-gyeongju-airbnb-blackout-curtain.html", "gyeongju-airbnb-blackout-curtain/11.jpg", "거실", "커튼", "숙소 거실 · 화이트 쉬폰커튼"),
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
            f'      <a class="g-item" href="reviews/{링크(f)}" data-tags="{space} {product}">'
            f'<img src="reviews/img/{img}" alt="{label} 시공 사진" loading="lazy">'
            f'<span class="g-label">{label}</span></a>'
        )
    if not items:
        print("[skip] gallery unchanged (no items)")
        return
    block = "\n".join(items) + '\n      <div class="gallery-empty">해당 조건의 시공 사진이 아직 없습니다.</div>'
    index = ROOT / "gallery.html"
    html = index.read_text(encoding="utf-8")
    html = re.sub(
        r"(<!-- GALLERY:START.*?-->).*?(<!-- GALLERY:END -->)",
        lambda m: m.group(1) + "\n" + block + "\n" + m.group(2),
        html,
        flags=re.S,
    )
    index.write_text(html, encoding="utf-8")
    print(f"[ok] home gallery ({len(items)} items, filterable)")


# ── 입주 예정 단지 (ipju/<file>) ─────────────────────────────────
# 커튼은 입주할 때 산다. 입주 두세 달 전에 단지명 페이지를 깔아두면 검색을 선점한다.
# 페이지 본문은 입주장페이지_생성.py 가 만든다. 여기서는 지역 페이지에서 거는 링크만 관리한다.
# 입주가 끝난 단지는 이 표에서 지운다(지난 일정을 걸어두면 오히려 감점).
# 한 지역에 단지가 여럿일 수 있다 — 입주가 빠른 순서로 적는다.
IPJU = {
    "영주": [("영주자이시그니처", "2026년 11월", "yeongju-xi-signature.html")],
    "포항": [("포항자이디오션", "2026년 10월", "pohang-xi-dioceon.html"),
             ("힐스테이트 더샵 상생공원", "2027년 9월", "pohang-sangsaeng-park.html")],
    "안동": [("위파크안동호반", "2027년 1월", "wepark-andong-hoban.html"),
             ("안동 용상 하늘채 리버스카이", "2027년 10월", "andong-yongsang-haneulchae.html")],
    "구미": [("힐스테이트 구미더퍼스트", "2027년 4월", "gumi-hillstate-the-first.html")],
}


def _ipju_all():
    return [t for v in IPJU.values() for t in v]


# ── 티스토리 비교 노트 (지역별 1편) ──────────────────────────
# 왜 외부 도메인으로 링크를 내보내나 — 티스토리 61편이 구글에 0편 색인이다(2026-09-06 확인).
# 원인은 들어오는 링크가 0개라 구글봇이 한 번도 온 적이 없다는 것("최근 크롤링: 해당사항 없음").
# 홈페이지는 이미 색인돼 있으니(29장) 여기서 걸어주면 크롤러가 그 길로 따라 들어간다.
# ★우리가 직접 쓴 글만 건다. 다른 브랜드 이름이 남아 있는 글은 정리가 끝날 때까지 뺀다.
# 읽는 사람에게도 맞다 — 그 지역 시공을 다 본 사람이 "그래서 뭘 골라야 하나"를 묻는다.
_T = "https://gunggwol19.tistory.com/entry/"
NOTES = {
    "포항": ("암막롤스크린 vs 암막커튼, 안방엔 뭐가 맞을까", _T + "%EC%95%94%EB%A7%89%EB%A1%A4%EC%8A%A4%ED%81%AC%EB%A6%B0-vs-%EC%95%94%EB%A7%89%EC%BB%A4%ED%8A%BC-%EC%95%88%EB%B0%A9%EC%97%94-%EB%AD%90%EA%B0%80-%EB%A7%9E%EC%9D%84%EA%B9%8C-%ED%8F%AC%ED%95%AD-%ED%9A%A8%EC%9E%90%EB%8F%99-%EA%B5%90%EC%B2%B4-%ED%9B%84%EA%B8%B0"),
    "영주": ("얇은 커튼 vs 암막커튼, 블라인드 단독 vs 이중", _T + "%EC%96%87%EC%9D%80-%EC%BB%A4%ED%8A%BC-vs-%EC%95%94%EB%A7%89%EC%BB%A4%ED%8A%BC-%EB%B8%94%EB%9D%BC%EC%9D%B8%EB%93%9C-%EB%8B%A8%EB%8F%85-vs-%EC%9D%B4%EC%A4%91-%E2%80%94-%EC%98%81%EC%A3%BC-%ED%99%94%EC%84%B1%EB%A6%AC%EB%B2%84%EB%B9%8C-%EA%B1%B0%EC%8B%A4-%EB%B9%84%EA%B5%90"),
    "의성": ("채광 롤스크린 vs 암막 롤스크린, 베란다는 왜 채광일까", _T + "%EC%B1%84%EA%B4%91-%EB%A1%A4%EC%8A%A4%ED%81%AC%EB%A6%B0-vs-%EC%95%94%EB%A7%89-%EB%A1%A4%EC%8A%A4%ED%81%AC%EB%A6%B0-%E2%80%94-%EC%9D%98%EC%84%B1-%EC%A3%BC%EA%B3%B52%EB%8B%A8%EC%A7%80-%EB%B2%A0%EB%9E%80%EB%8B%A4%EB%8A%94-%EC%99%9C-%EC%B1%84%EA%B4%91%EC%9D%BC%EA%B9%8C"),
    "경주": ("콤비블라인드 vs 롤스크린 vs 암막커튼, 집 전체를 통일한다면", _T + "%EC%BD%A4%EB%B9%84%EB%B8%94%EB%9D%BC%EC%9D%B8%EB%93%9C-vs-%EB%A1%A4%EC%8A%A4%ED%81%AC%EB%A6%B0-vs-%EC%95%94%EB%A7%89%EC%BB%A4%ED%8A%BC-%EC%A7%91-%EC%A0%84%EC%B2%B4%EB%A5%BC-%ED%95%98%EB%82%98%EB%A1%9C-%ED%86%B5%EC%9D%BC%ED%95%9C%EB%8B%A4%EB%A9%B4-%EB%AD%90%EA%B0%80-%EB%A7%9E%EC%9D%84%EA%B9%8C-%EA%B2%BD%EC%A3%BC-%EC%9E%90%EC%9D%B4%EC%95%84%ED%8C%8C%ED%8A%B8-%EB%B9%84%EA%B5%90"),
    "예천": ("매장 창에 롤스크린 vs 콤비블라인드 vs 버티컬", _T + "%EB%A7%A4%EC%9E%A5-%EC%B0%BD%EC%97%90-%EB%A1%A4%EC%8A%A4%ED%81%AC%EB%A6%B0-vs-%EC%BD%A4%EB%B9%84%EB%B8%94%EB%9D%BC%EC%9D%B8%EB%93%9C-vs-%EB%B2%84%ED%8B%B0%EC%BB%AC-%EB%AD%90%EA%B0%80-%EB%A7%9E%EC%9D%84%EA%B9%8C-%EC%98%88%EC%B2%9C-%ED%8E%B8%EC%9D%98%EC%A0%90-%EC%8B%9C%EA%B3%B5-%EB%B9%84%EA%B5%90"),
}


def _danji_block(region):
    if region not in DANJI:
        return ""
    out = "\n  <h2>이미 시공한 단지 — 이사 들어가실 때</h2>\n"
    for danji, file in DANJI[region]:
        out += (f'  <p class="body"><a href="../danji/{링크(file)}" '
                f'style="color:var(--accent2);font-weight:700">{danji} 커튼, 이사 들어갈 때 다시 맞추기 →</a></p>\n')
    return out


# 입주 3~5년차 단지 중 우리가 실제로 시공한 곳(danji/). 단지페이지_생성.py 가 만든다.
DANJI = {
    "포항": [("힐스테이트 포항", "hillstate-pohang.html")],
}


def _ipju_block(region):
    if region not in IPJU:
        return _danji_block(region)
    out = "\n  <h2>입주 예정 단지</h2>\n"
    for danji, when, _file in IPJU[region]:
        조사 = "이" if "가" <= danji[-1] <= "힣" and (ord(danji[-1]) - 0xAC00) % 28 else "가"
        out += f'  <p class="body">{danji}{조사} {when}에 입주합니다.</p>\n'
    out += ('  <p class="body">실측이 언제 몰리는지, 사전점검일에 무엇을 적어 오시면 되는지 '
            "날짜로 정리해 두었습니다.</p>\n")
    for danji, _when, file in IPJU[region]:
        out += (f'  <p class="body"><a href="../ipju/{링크(file)}" '
                f'style="color:var(--accent2);font-weight:700">{danji} 커튼 입주 일정 보기 →</a></p>\n')
    return out + _danji_block(region)


# ── 지역 페이지 (areas/<slug>.html) ──────────────────────────────
# 후기가 1건 이상 있는 지역만 생성한다(빈 페이지 = 검색 감점). 새 후기가
# 쌓이면 build.py 실행만으로 해당 지역 페이지가 자동 생성·갱신된다.
AREA_TMPL = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__REGION__ 커튼·블라인드 출장 시공 | __DONGS__ - 따솜커튼블라인드</title>
<meta name="description" content="__DONGSD__ 실제로 시공한 집들입니다. 창 사진을 보내주시면 방문 전에 대략적인 견적을 먼저 알려드리고, 방문 실측 후 확정합니다. 속커튼·암막커튼·콤비블라인드·롤스크린·우드블라인드. __REGION__ 담당 __MGR__ __TEL__.">
<link rel="canonical" href="https://ddasom.com/areas/__SLUG__">
<meta property="og:type" content="article">
<meta property="og:site_name" content="따솜커튼블라인드">
<meta property="og:title" content="__REGION__ 커튼·블라인드 출장 시공 | __DONGS__">
<meta property="og:description" content="__REGION__ 커튼 시공·블라인드 설치, 전지역 출장 실측. __REGION__ 담당 __MGR__ __TEL__.">
<meta property="og:url" content="https://ddasom.com/areas/__SLUG__">
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
.sitebar{background:var(--white);border-bottom:1px solid var(--line)}
.sitebar-in{max-width:820px;margin:0 auto;padding:10px 22px;display:flex;align-items:center;gap:16px}
.sitebar-brand{font-weight:800;letter-spacing:-.03em;font-size:15px;white-space:nowrap}
.sitebar-nav{display:flex;gap:14px;overflow-x:auto;scrollbar-width:none}
.sitebar-nav::-webkit-scrollbar{display:none}
.sitebar-nav a{font-size:14px;color:var(--soft);white-space:nowrap;padding:4px 0}
.sitebar-nav a:hover{color:var(--ink)}
.sitebar-cta{color:var(--accent2);font-weight:700}
@media(max-width:640px){.sitebar-in{padding:9px 16px;gap:12px}.sitebar-brand{font-size:14px}}
.area-more{margin:34px 0 0;padding-top:22px;border-top:1px solid var(--line)}
.area-more h2{font-size:17px;margin:0 0 10px}
.area-more-list{font-size:15px;color:var(--soft);line-height:2}
.area-more-list a{color:var(--accent2);font-weight:600}
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
<header class="sitebar">
  <div class="sitebar-in">
    <a class="sitebar-brand" href="../">따솜커튼블라인드</a>
    <nav class="sitebar-nav" aria-label="주요 메뉴">
      <a href="../services">서비스</a>
      <a href="../gallery">갤러리</a>
      <a href="../reviews/">시공후기</a>
      <a href="../guides/">커튼 가이드</a>
      <a href="../b2b">기업·기관</a>
      <a href="../areas">출장지역</a>
      <a class="sitebar-cta" href="../apply">견적요청</a>
    </nav>
  </div>
</header>
<main class="wrap">
  <nav class="crumb" aria-label="현재 위치"><a href="../">따솜커튼블라인드</a> › <a href="../areas">출장지역</a> › __REGION__ 커튼·블라인드 시공</nav>

  <div class="hero">
    <span class="tag">__REGION__ 전지역 출장 시공</span>
    <h1>__REGION__ 커튼·블라인드 시공,<br>따솜이 직접 방문합니다</h1>
    <p>__REGION__ 아파트·주택·상가 어디든 방문 실측부터 맞춤 제작·설치까지.<br>창에 직접 원단을 대보고 색을 고른 뒤 시공하니 실패가 없습니다.</p>
    <div class="mgr">
      <div><div class="who">__REGION__ 담당</div><div class="tel">__MGR__ __TEL__</div></div>
      <a class="call" href="tel:__TEL__">전화 상담</a>
    </div>
  </div>

__IPJU__
  <h2>__REGION__ 커튼집을 찾고 계신가요?</h2>
  <p class="body">커튼·블라인드는 매장을 돌며 비교하기가 쉽지 않습니다.</p>
  <p class="body">따솜커튼블라인드는 <b>__REGION__ 전지역 출장 전문</b>입니다.<br>__REGION__ 커튼 시공 업체를 알아보고 계시다면, 매장까지 오실 필요 없습니다.</p>
  <p class="body">방문 실측 → 원단·색 상담 → 맞춤 제작 → 설치까지 한 번에 끝냅니다.</p>
  <p class="body">별도 매장을 방문하실 필요 없이,<br>__REGION__ 담당 <b>__MGR__(__TEL__)</b>이 직접 찾아갑니다.</p>
  <p class="body">창 사이즈를 재고 어울리는 제품을 제안해 드립니다.</p>
  <p class="body">온라인 판매가 그대로, 시공까지 그 가격으로 해드립니다.</p>

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

  <h2>__REGION__ 호텔·모텔·펜션 객실 방음커튼</h2>
  <p class="body">객실은 집과 문제가 다릅니다.</p>
  <p class="body">옆방과 복도 소리, 그리고 새벽에 들어오는 빛이 손님 후기를 좌우합니다.</p>
  <p class="body">따솜커튼블라인드는 __REGION__ 숙박업소 객실에 <b>방음커튼과 객실 암막커튼</b>을 시공합니다.</p>
  <p class="body">두꺼운 암막 원단을 주름 넉넉히 잡아 소리를 먹이고, 창 옆·위로 새는 틈까지 덮습니다.</p>
  <p class="body">객실 수가 많으면 같은 사양으로 반복 제작해 한 번에 끝냅니다.</p>
  <p class="body"><a href="../b2b-hotel" style="color:var(--accent2);font-weight:700">호텔·모텔 방음커튼 시공 자세히 보기</a></p>

  <h2>__REGION__ 커튼 시공 자주 묻는 질문</h2>
  <div class="faq">
    <details open><summary>__REGION__도 출장 시공되나요?</summary><p>네, __REGION__ 전지역에 출장 시공합니다.<br>커튼 설치와 블라인드 설치 모두 __REGION__ 담당 __MGR__(__TEL__)이 직접 방문해 진행합니다.</p></details>
    <details><summary>견적은 어떻게 받나요?</summary><p>창 사진을 보내주시면 방문 전에 대략 견적을 먼저 알려드립니다.<br>방문 실측 후 최종 견적을 확정하고, 온라인 판매가 그대로 시공까지 진행합니다.</p></details>
    <details><summary>어떤 제품까지 시공하나요?</summary><p>속커튼·암막커튼·콤비블라인드·롤스크린까지,<br>우드·전동 블라인드도 맞춤 제작·시공합니다.</p></details>
    <details><summary>__REGION__ 호텔·모텔 객실 방음커튼도 되나요?</summary><p>네, 숙박업소 객실 시공도 합니다.<br>두꺼운 암막 원단으로 소리와 빛을 함께 잡고, 객실 수가 많으면 같은 사양으로 반복 제작합니다.<br><a href="../b2b-hotel" style="color:var(--accent2);font-weight:700">호텔·모텔 방음커튼 안내</a></p></details>
    <details><summary>상담은 어떻게 하나요?</summary><p>전화나 문자로 __MGR__(__TEL__)에게 연락 주세요.<br><a href="../apply" style="color:var(--accent2);font-weight:700">실측 신청 폼</a>에 성함·연락처·지역을 남기셔도 됩니다.</p></details>
  </div>

  <div class="cta-final">
    <h2>__REGION__ 커튼·블라인드, 편하게 상담받으세요</h2>
    <p>창 사진만 있어도 대략 견적 안내가 가능합니다.<br>__REGION__ 담당 __MGR__이 도와드립니다.</p>
    <a href="tel:__TEL__">__MGR__ __TEL__ 전화</a>
  </div>

  <nav class="area-more" aria-label="다른 지역">
    <h2>다른 지역 시공</h2>
    <p class="area-more-list">__OTHERAREAS__</p>
    <p class="area-more-list"><a href="../areas">출장 지역 전체 보기</a> · <a href="../services">커튼·블라인드 종류와 진행 과정</a> · <a href="../b2b">기업·기관 시공</a> · <a href="../b2b-hotel">호텔·모텔 방음커튼</a></p>
    <p class="area-more-list"><a href="../gallery">시공 사진 모아보기</a> · <a href="../guides/curtain-vs-blind">커튼과 블라인드 중 무엇을 고를까</a> · <a href="../guides/blackout-light-leak">암막커튼 빛샘은 어디서 오나</a> · <a href="../guides/curtain-washing">커튼 세탁, 집에서 해도 되는 것</a> · <a href="../guides/jeonse-curtain">전세집 커튼, 벽을 못 뚫을 때</a> · <a href="../guides/soundproof-curtain">방음커튼은 어디까지 되나</a></p>
  </nav>
</main>

<footer class="foot">따솜커튼블라인드 · 대구·경북 전 지역 커튼·블라인드 출장 시공 · 기업·기관은 부산·울산·경남까지<br>
  <a href="../" style="color:var(--accent2)">ddasom.com 홈으로</a> · <a href="../reviews/" style="color:var(--accent2)">전체 시공후기</a></footer>

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
                "@id": f"https://ddasom.com/areas/{slug}#webpage",
                "url": f"https://ddasom.com/areas/{slug}",
                "name": f"{region} 커튼집·블라인드 전문점 | 따솜커튼블라인드",
                "inLanguage": "ko",
                "about": {"@type": "City", "name": region},
                "isPartOf": {"@id": "https://ddasom.com/#website"},
                "provider": {"@id": "https://ddasom.com/#business"},
                "description": f"{region} 커튼 시공 업체·블라인드 설치. 전지역 출장 실측. {region} 담당 {mgr} {tel}.",
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "따솜커튼블라인드", "item": "https://ddasom.com/"},
                    {"@type": "ListItem", "position": 2, "name": f"{region} 커튼·블라인드 시공", "item": f"https://ddasom.com/areas/{slug}"},
                ],
            },
            {
                "@type": "Service",
                "name": f"{region} 커튼·블라인드 출장 시공",
                "serviceType": "커튼·블라인드 맞춤 제작 및 시공",
                "provider": {"@id": "https://ddasom.com/#business"},
                "areaServed": {"@type": "City", "name": region},
                "offers": {"@type": "Offer", "priceCurrency": "KRW", "description": "온라인 판매가 그대로 시공까지"},
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {"@type": "Question", "name": f"{region}에서 커튼·블라인드 시공을 맡길 수 있나요?",
                     "acceptedAnswer": {"@type": "Answer", "text": f"네. 따솜커튼블라인드는 {region} 전지역에 출장 시공합니다. {region} 지역은 {mgr}({tel})이 담당해 방문 실측부터 맞춤 제작·설치까지 직접 진행합니다."}},
                    {"@type": "Question", "name": f"{region} 커튼 견적은 어떻게 받나요?",
                     "acceptedAnswer": {"@type": "Answer", "text": f"창 사진을 보내주시면 방문 전에 대략 견적을 먼저 알려드립니다. {region} 방문 실측 후 최종 견적을 확정하며, 온라인 판매가 그대로 시공까지 진행합니다."}},
                    {"@type": "Question", "name": f"{region} 호텔·모텔 객실 방음커튼도 시공하나요?",
                     "acceptedAnswer": {"@type": "Answer", "text": f"네. {region} 호텔·모텔·펜션 객실에 방음커튼과 객실 암막커튼을 시공합니다. 두꺼운 암막 원단을 주름 넉넉히 잡아 옆방·복도 소리와 새벽 빛을 함께 줄이고, 객실 수가 많으면 같은 사양으로 반복 제작합니다."}},
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
    # 다른 지역 링크를 만들려면 전체 지역을 먼저 알아야 한다 — 한 번 훑고 시작한다.
    전체지역 = [(r, REGION_SLUG[r], len(ps)) for r, ps in by_region.items()]
    전체지역.sort(key=lambda x: -x[2])
    for region, rposts in by_region.items():
        slug = REGION_SLUG[region]
        mgr, tel = manager_of(region)
        cards = []
        for p in rposts[:6]:  # 최신 6건까지
            thumb = (f'<img src="../reviews/{p["thumb"]}" alt="{p["title"]} 시공 사진" loading="lazy">'
                     if p["thumb"] else "")
            desc = p["desc"][:46] + ("…" if len(p["desc"]) > 46 else "")
            cards.append(
                f'    <a class="card" href="../reviews/{링크(p["file"])}">{thumb}'
                f'<span class="cap"><b>{p["title"]}</b><span>{desc}</span></span></a>'
            )
        ogimg = f'{BASE_URL}/reviews/{rposts[0]["thumb"]}' if rposts[0]["thumb"] else ""
        # 제목에 쓸 실제 동네 이름 (후기 제목에서 뽑는다). 없으면 일반 문구로.
        # 동/읍/면/리로 끝나지만 지명이 아닌 말들 — 이게 없으면 「아이보리」가 동네가 된다.
        _NOT_DONG = {
            "아이보리", "마무리", "처리", "유리", "관리", "정리", "거리", "우리", "소리",
            "자동", "전동", "이동", "활동", "운동", "공동", "작동", "감동", "반자동", "수동", "진동", "가동",
            "전면", "후면", "측면", "정면", "양면", "벽면", "표면", "단면", "세면", "도면", "지면",
        }
        _dongs = []
        for p in rposts:
            for tok in re.findall(r"[가-힣]+(?:동|읍|면|리)(?=\s|$)", p["title"]):
                if len(tok) < 2 or tok in _NOT_DONG or tok == region:
                    continue
                if tok not in _dongs:
                    _dongs.append(tok)
        _dongs = _dongs[:3]
        if _dongs:
            dongs_t = "·".join(_dongs) + " 시공후기"
            dongs_d = region + " " + "·".join(_dongs) + " 등에서"
        else:
            # 후기 수가 적을 때 숫자를 쓰면 약점만 드러난다. 하는 일을 쓴다.
            dongs_t = "방문 실측부터 설치까지"
            dongs_d = region + "에서"

        html = (AREA_TMPL
                .replace("__JSONLD__", _area_jsonld(region, slug, mgr, tel, ogimg))
                .replace("__DONGS__", dongs_t)
                .replace("__DONGSD__", dongs_d)
                .replace("__REGION__", region)
                .replace("__SLUG__", slug)
                .replace("__MGR__", mgr)
                .replace("__TEL__", tel)
                .replace("__OGIMG__", ogimg)
                .replace("__CARDS__", "\n".join(cards))
                .replace("__IPJU__", _ipju_block(region))
                .replace("__OTHERAREAS__", " · ".join(
                    f'<a href="{s2}">{r2} 커튼·블라인드</a>'
                    for r2, s2, _n in 전체지역 if s2 != slug)))
        # 대구·경북 밖 지역(대전 등)은 "전지역 출장" 과장 표현을 뺀다 (사례는 있되 기본 권역 아님)
        if region not in GB_REGIONS:
            html = html.replace(f"{region} 전지역", region)
        (area_dir / f"{slug}.html").write_text(html, encoding="utf-8")
        infos.append((region, slug, len(rposts)))
    infos.sort(key=lambda x: -x[2])  # 후기 많은 순
    print(f"[ok] areas/ 지역 페이지 {len(infos)}개: " + ", ".join(f"{r}({n})" for r, s, n in infos))
    return infos


def build_home_areas(infos):
    """홈 index.html의 AREAS:START~END 사이를 지역 페이지 링크로 채운다."""
    index = ROOT / "areas.html"
    html = index.read_text(encoding="utf-8")
    if "AREAS:START" not in html:
        print("[skip] areas.html에 AREAS 마커 없음")
        return
    links = "\n".join(
        f'      <a class="area-link" href="areas/{slug}">{region} 출장 시공 <span>후기 {n}건</span></a>'
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
    urls = [(f"{BASE_URL}/", today), (f"{BASE_URL}/b2b", today), (f"{BASE_URL}/b2b-bangyeom", today), (f"{BASE_URL}/b2b-office", today), (f"{BASE_URL}/b2b-school", today), (f"{BASE_URL}/b2b-clinic", today), (f"{BASE_URL}/b2b-shop", today), (f"{BASE_URL}/b2b-hotel", today), (f"{BASE_URL}/partner", today), (f"{BASE_URL}/services", today), (f"{BASE_URL}/gallery", today), (f"{BASE_URL}/areas", today), (f"{BASE_URL}/apply", today), (f"{BASE_URL}/reviews/", today), (f"{BASE_URL}/privacy", today)]
    urls += [(f"{BASE_URL}/areas/{slug}", today) for _r, slug, _n in areas]
    urls += [(f"{BASE_URL}/ipju/", today)]
    urls += [(f"{BASE_URL}/danji/{p.stem}", today) for p in sorted((ROOT / "danji").glob("*.html"))]
    urls += [(f"{BASE_URL}/ipju/{file.removesuffix('.html')}", today) for _d, _w, file in _ipju_all()]
    # guides/ 정보글 — 파일을 두면 자동으로 사이트맵에 들어간다.
    guides = sorted(p.stem for p in (ROOT / "guides").glob("*.html") if p.stem != "index")
    urls += [(f"{BASE_URL}/guides/", today)]
    urls += [(f"{BASE_URL}/guides/{slug}", today) for slug in guides]
    urls += [(f"{BASE_URL}/reviews/{p['file'].removesuffix('.html')}", p["date"]) for p in posts]
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


def _rfc822(날짜):
    """RSS 는 날짜 형식이 따로 있다. 사이트맵의 2026-08-26 형식을 못 알아듣는다.

    글에는 시각이 없으니 그날 오전 9시(한국시간)로 둔다.
    시각이 다 같으면 수집기가 순서를 못 정하므로 순서는 pubDate 가 아니라 나열 순서로 정해진다.
    """
    try:
        y, m, d = (int(x) for x in 날짜.split("-"))
    except Exception:
        return ""
    요일 = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[date(y, m, d).weekday()]
    달 = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")[m - 1]
    return f"{요일}, {d:02d} {달} {y} 09:00:00 +0900"


def _xml탈출(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def build_rss(posts, 개수=20):
    """최신 시공후기 RSS.

    네이버는 사이트맵보다 RSS 를 자주 읽는다. 새 후기가 검색에 잡히는 속도가 달라진다.

    정렬은 시공일이 아니라 **발행일**이다. 2017년에 한 시공을 2026년에 올린 글이 있어서,
    시공일로 정렬하면 방금 올린 글이 목록 맨 아래로 가 버린다. 그러면 RSS 를 쓰는 의미가 없다.
    """
    if not BASE_URL:
        print("[skip] BASE_URL not set - rss.xml not generated")
        return
    # 발행일이 같은 글이 여러 개면 파일명(=시공일) 역순으로 갈라 준다.
    최신 = sorted(posts, key=lambda p: (발행일(p["file"]), p["file"]), reverse=True)[:개수]
    항목 = []
    for p in 최신:
        주소 = f"{BASE_URL}/reviews/{p['file']}"
        # link 는 canonical 과 같은 확장자 없는 주소로 — .html 은 308 을 한 번 더 거쳐 서치콘솔
        # 「리디렉션 오류」로 잡혔다(2026-10-08). guid 는 그대로 둬야 리더가 같은 글을 새 글로 다시 받지 않는다.
        조각 = [
            f"    <title>{_xml탈출(p['title'])}</title>",
            f"    <link>{BASE_URL}/reviews/{링크(p['file'])}</link>",
            f"    <guid isPermaLink=\"false\">{주소}</guid>",
            f"    <description>{_xml탈출(p['desc'])}</description>",
        ]
        날 = _rfc822(발행일(p["file"]))
        if 날:
            조각.append(f"    <pubDate>{날}</pubDate>")
        if p.get("thumb"):
            조각.append(f'    <enclosure url="{BASE_URL}/reviews/{p["thumb"]}" type="image/jpeg"/>')
        항목.append("  <item>\n" + "\n".join(조각) + "\n  </item>")

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "<channel>\n"
        "  <title>따솜커튼블라인드 시공후기</title>\n"
        f"  <link>{BASE_URL}/reviews/</link>\n"
        "  <description>대구·경북 커튼·블라인드 방문 실측 시공 사례입니다.</description>\n"
        "  <language>ko</language>\n"
        f'  <atom:link href="{BASE_URL}/rss.xml" rel="self" type="application/rss+xml"/>\n'
        + "\n".join(항목) + "\n</channel>\n</rss>\n"
    )
    (ROOT / "rss.xml").write_text(xml, encoding="utf-8")
    print(f"[ok] rss.xml ({len(최신)} items)")


def build_webp(품질=82):
    """사진 옆에 같은 이름의 .webp 를 만든다. 원본 JPG 는 지우지 않는다.

    커튼을 알아보는 사람은 대부분 집이나 가게에서 폰으로 본다.
    사진이 무거우면 다 뜨기 전에 나간다.

    원본을 남기는 이유는 두 가지다.
      - webp 를 못 읽는 옛 브라우저가 아직 있다 (<picture> 로 JPG 를 대안으로 준다)
      - 되돌리려면 <picture> 만 벗기면 된다. 사진을 다시 만들 필요가 없다

    이미 만든 것은 건너뛴다. 원본이 더 새로우면 다시 만든다.
    """
    try:
        from PIL import Image
    except ImportError:
        print("[skip] Pillow 가 없어 webp 를 못 만든다 (pip install Pillow)")
        return
    만듦 = 건너뜀 = 0
    원본합 = 결과합 = 0
    for j in sorted(ROOT.rglob("*.jpg")):
        if "_to_delete" in j.parts:
            continue
        w = j.with_suffix(".webp")
        원본합 += j.stat().st_size
        if w.exists() and w.stat().st_mtime >= j.stat().st_mtime:
            결과합 += w.stat().st_size
            건너뜀 += 1
            continue
        with Image.open(j) as im:
            im.convert("RGB").save(w, "WEBP", quality=품질, method=4)
        결과합 += w.stat().st_size
        만듦 += 1
    if 만듦 or 건너뜀:
        준것 = (1 - 결과합 / 원본합) * 100 if 원본합 else 0
        print(f"[ok] webp {만듦}장 생성 · {건너뜀}장 그대로 "
              f"({원본합/1048576:.1f}MB → {결과합/1048576:.1f}MB, {준것:.0f}% 감소)")


_그림 = re.compile(r"(<picture>.*?</picture>)|(<img[^>]*>)", re.S)


def build_picture():
    """<img src="…jpg"> 를 <picture> 로 감싸 webp 를 먼저 주게 한다.

    webp 를 읽는 브라우저는 webp 를, 못 읽는 브라우저는 그대로 JPG 를 받는다.
    화면에 보이는 것은 달라지지 않는다.

    이미 감싼 것은 건드리지 않는다(멱등). webp 파일이 실제로 있는 것만 감싼다 —
    없는 주소를 가리키면 사진이 통째로 안 뜬다.
    """
    감쌈 = 0
    for f in sorted(ROOT.rglob("*.html")):
        if "_to_delete" in f.parts or "tests" in f.parts or f.name == "_template.html":
            continue
        t = f.read_text(encoding="utf-8", errors="replace")
        놓친것 = [0]

        def one(m):
            if m.group(1):
                return m.group(1)          # 이미 감싼 것
            태그 = m.group(2)
            s = re.search(r'src="([^"]+\.jpg)"', 태그, re.I)
            if not s:
                return 태그
            주소 = s.group(1)
            if 주소.startswith(("http://", "https://", "//")):
                return 태그                # 남의 서버 사진은 우리가 못 바꾼다
            실제 = (f.parent / 주소).resolve()
            if not 실제.with_suffix(".webp").exists():
                놓친것[0] += 1
                return 태그
            웹 = 주소.rsplit(".", 1)[0] + ".webp"
            return (f'<picture><source srcset="{웹}" type="image/webp">'
                    f'{태그}</picture>')

        새것 = _그림.sub(one, t)
        if 새것 != t:
            f.write_text(새것, encoding="utf-8")
            감쌈 += 1
        if 놓친것[0]:
            print(f"   [주의] {f.name}: webp 가 없어 그대로 둔 사진 {놓친것[0]}장")
    if 감쌈:
        print(f"[ok] <picture> 적용 {감쌈}장")


_RSS표 = '<!-- AUTO:rss-link -->'


def build_rss_link():
    """홈과 후기 목록 <head> 에 RSS 위치를 알려 주는 줄을 넣는다.

    수집기와 피드 리더가 주소를 모르면 rss.xml 이 있어도 못 찾는다.
    후기 개별 글에는 넣지 않는다 — 목록이 있는 자리에만 있으면 된다.
    """
    if not BASE_URL:
        return
    줄 = (f'{_RSS표}<link rel="alternate" type="application/rss+xml" '
          f'title="따솜커튼블라인드 시공후기" href="{BASE_URL}/rss.xml">')
    바뀜 = 0
    for 상대 in ("index.html", "reviews/index.html"):
        f = ROOT / 상대
        if not f.exists():
            continue
        t = f.read_text(encoding="utf-8")
        새것 = (re.sub(re.escape(_RSS표) + r'<link[^>]*>', 줄, t)
                if _RSS표 in t else t.replace("</head>", 줄 + "\n</head>", 1))
        if 새것 != t:
            f.write_text(새것, encoding="utf-8")
            바뀜 += 1
    if 바뀜:
        print(f"[ok] RSS 자동발견 링크 {바뀜}장")


def build_robots():
    """네이버 봇(Yeti)을 따로 적어 준다.

    `User-agent: *` 에 이미 포함되므로 지금도 수집은 된다(실제로 색인돼 있다).
    명시해 두면 네이버 웹마스터의 robots.txt 검증에서 분명하게 잡힌다.
    """
    if not BASE_URL:
        return
    t = ("User-agent: *\n"
         "Allow: /\n\n"
         "User-agent: Yeti\n"
         "Allow: /\n\n"
         "User-agent: Googlebot\n"
         "Allow: /\n\n"
         f"Sitemap: {BASE_URL}/sitemap.xml\n")
    옛 = ROOT / "robots.txt"
    if not 옛.exists() or 옛.read_text(encoding="utf-8") != t:
        옛.write_text(t, encoding="utf-8")
        print("[ok] robots.txt (Yeti·Googlebot 명시)")



# ─────────────────────────────────────────────────────────────
# 후기 페이지 보강 — 색인과 공유에 필요한 것을 자동으로 채운다.
#
#   1) 지연 로딩   첫 사진만 빼고 loading="lazy"
#                  첫 사진은 화면에 바로 보이는 자리라 lazy 를 걸면 오히려 늦어진다.
#   2) canonical · og   카톡·블로그에 링크를 나눌 때 미리보기 사진이 뜨게
#   3) 구조화 데이터    Article + BreadcrumbList (+ 자주 묻는 질문이 있으면 FAQPage)
#                  지역 페이지가 이미 쓰는 #business · #website 를 그대로 참조한다.
#
# 여러 번 돌려도 결과가 같다. 넣은 자리에 표식을 남겨 통째로 갈아끼운다.
# ─────────────────────────────────────────────────────────────
시작표 = "<!-- AUTO:review-meta -->"
끝표 = "<!-- /AUTO:review-meta -->"


def 첫사진(html):
    m = re.search(r'<img[^>]+src="(img/[^"]+)"', html)
    return m.group(1) if m else ""


def 사진들(html):
    return re.findall(r"<img[^>]*>", html)


def 질문답(html):
    """<p><strong>Q. 질문</strong><br>답변</p> 를 뽑는다."""
    나온것 = []
    for m in re.finditer(
            r"<p>\s*<strong>\s*Q\.\s*(.*?)</strong>\s*<br>\s*(.*?)</p>", html, re.S):
        q = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        a = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if q and a:
            나온것.append((q, a))
    return 나온것


def 시공일(html, 파일명):
    """파일명 앞의 날짜 = 시공한 날."""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})-", 파일명)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


_발행일캐시 = {}


def 발행일(파일명):
    """글이 실제로 올라간 날. git 의 최초 커밋 날짜를 쓴다.

    시공일을 datePublished 로 쓰면 안 된다. 2017년에 한 시공을 2026년에 올린 글도 있어서,
    그대로 넣으면 구글에 "9년 전에 발행된 글"이라고 알리는 꼴이 된다.
    git 을 못 읽으면 시공일로 물러선다.
    """
    if 파일명 in _발행일캐시:
        return _발행일캐시[파일명]
    날 = ""
    try:
        import subprocess
        r = subprocess.run(
            ["git", "log", "--diff-filter=A", "--follow",
             "--format=%ad", "--date=short", "-1", "--", f"reviews/{파일명}"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=20)
        날 = r.stdout.strip().splitlines()[0].strip() if r.stdout.strip() else ""
    except Exception:
        날 = ""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", 날 or ""):
        날 = 시공일("", 파일명)
    _발행일캐시[파일명] = 날
    return 날


def 지연로딩(html):
    """첫 사진을 뺀 나머지에 lazy 를 건다. 이미 있으면 그대로 둔다."""
    n = 0
    def one(m):
        nonlocal n
        태그 = m.group(0)
        n += 1
        if n == 1:
            # 첫 사진은 즉시 받는다. 대신 우선순위를 올려 준다.
            if "fetchpriority" not in 태그:
                태그 = 태그[:-1].rstrip() + ' fetchpriority="high">'
            return 태그
        if "loading=" in 태그:
            return 태그
        return 태그[:-1].rstrip() + ' loading="lazy" decoding="async">'
    return re.sub(r"<img[^>]*>", one, html)


def 머리보강(html, 파일명):
    제목 = re.search(r"<title>(.*?)</title>", html, re.S)
    제목 = 제목.group(1).strip() if 제목 else 파일명
    설명 = re.search(r'<meta name="description" content="(.*?)"', html, re.S)
    설명 = 설명.group(1).strip() if 설명 else ""
    사진 = 첫사진(html)
    주소 = f"{BASE_URL}/reviews/{파일명}".removesuffix(".html")
    이미지주소 = f"{BASE_URL}/reviews/{사진}" if 사진 else f"{BASE_URL}/promo-img/og.jpg"
    시공 = 시공일(html, 파일명)
    날짜 = 발행일(파일명) or 시공
    h1 = re.search(r"<h1>(.*?)</h1>", html, re.S)
    헤드라인 = re.sub(r"<[^>]+>", " ", h1.group(1)).strip() if h1 else 제목

    그래프 = [
        {
            "@type": "Article",
            "@id": 주소 + "#article",
            "headline": 헤드라인[:110],
            "description": 설명,
            "image": [이미지주소],
            "datePublished": 날짜,
            "dateModified": 날짜,
            "inLanguage": "ko",
            "mainEntityOfPage": {"@type": "WebPage", "@id": 주소},
            "author": {"@id": f"{BASE_URL}/#business"},
            "publisher": {"@id": f"{BASE_URL}/#business"},
            "isPartOf": {"@id": f"{BASE_URL}/#website"},
        },
        {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "따솜커튼블라인드",
                 "item": f"{BASE_URL}/"},
                {"@type": "ListItem", "position": 2, "name": "시공후기",
                 "item": f"{BASE_URL}/reviews/"},
                {"@type": "ListItem", "position": 3, "name": 헤드라인[:80], "item": 주소},
            ],
        },
    ]
    qa = 질문답(html)
    if len(qa) >= 2:
        그래프.append({
            "@type": "FAQPage",
            "@id": 주소 + "#faq",
            "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a in qa
            ],
        })

    덩어리 = (
        f'{시작표}\n'
        # max-image-preview:large — 없으면 Discover 에 큰 그림이 안 실리고
        # 일반 검색의 그림 미리보기도 작아진다(구글 Discover 문서).
        # 시공후기는 편당 사진 5장이 걸린 글이라 이 한 줄이 제일 크게 작용한다.
        f'<meta name="robots" content="max-image-preview:large">\n'
        f'<link rel="canonical" href="{주소}">\n'
        f'<meta property="og:type" content="article">\n'
        f'<meta property="og:site_name" content="따솜커튼블라인드">\n'
        f'<meta property="og:title" content="{제목}">\n'
        f'<meta property="og:description" content="{설명}">\n'
        f'<meta property="og:url" content="{주소}">\n'
        f'<meta property="og:image" content="{이미지주소}">\n'
        f'<meta name="twitter:card" content="summary_large_image">\n'
        f'<script type="application/ld+json">'
        + json.dumps({"@context": "https://schema.org", "@graph": 그래프},
                     ensure_ascii=False, separators=(",", ":"))
        + f'</script>\n{끝표}'
    )

    # 이미 넣은 게 있으면 통째로 갈아끼운다
    if 시작표 in html:
        return re.sub(re.escape(시작표) + r".*?" + re.escape(끝표), 덩어리, html, flags=re.S), len(qa)
    return html.replace("</head>", 덩어리 + "\n</head>", 1), len(qa)


def enrich_reviews(확인만=False):
    바뀜, faq수 = [], 0
    for f in sorted(REVIEWS.glob("2*.html")):
        원본 = f.read_text(encoding="utf-8")
        새것, qa = 머리보강(원본, f.name)
        새것 = 지연로딩(새것)
        if qa >= 2:
            faq수 += 1
        if 새것 != 원본:
            if not 확인만:
                f.write_text(새것, encoding="utf-8")
            바뀜.append((f.name, qa))
    print(f"[ok] 후기 보강 {len(바뀜)}편 (구조화 데이터·og·지연 로딩) · FAQ {faq수}편")
    return 바뀜



# ─────────────────────────────────────────────────────────────
# 접속 분석 · 개인정보처리방침 링크
#
# CLARITY_ID 가 비어 있으면 아무것도 넣지 않는다.
# clarity.microsoft.com 에서 프로젝트를 만들면 받는 10자 안팎의 아이디를 넣으면
# 그때부터 모든 페이지에 붙는다.
#
# 분석 도구를 켜는 순간 방문 기록을 모으게 되므로 privacy.html 안내가 같이 가야 한다.
# 그래서 이 함수가 푸터의 개인정보처리방침 링크도 함께 챙긴다.
# ─────────────────────────────────────────────────────────────
CLARITY_ID = "y88nlkwv9e"      # clarity.microsoft.com 프로젝트 ID

# 네이버 애널리틱스(wcslog). 파워링크 캠페인의 추적기능을 AUTO_TRACKING_MODE 로 켜 두었는데,
# 그 값을 받아 "어느 키워드가 문의로 이어졌는지" 집계해 줄 곳이 이것뿐이다.
# 아이디는 analytics.naver.com 에서 사이트를 등록하면 나오는 10자 안팎의 값.
NAVER_WA_ID = "1b00676df2f64c0"   # 비어 있으면 넣지 않는다

# 검색광고 전환추적용 「네이버공통키」(na_account_id). ★위 애널리틱스 ID 와 다른 값이다.
# 검색광고 → 도구 → 프리미엄 로그분석 에서 발급된다(신청 후 영업일 1~2일).
# 2026-09-21 네이버CTS 「스크립트 검수 보류」 메일 — 애널리틱스 ID 만 있어 검색광고 쪽이 안 잡혔다.
# 공식 가이드: naver.github.io/conversion-tracking (01 · 07 페이지)
# 애널리틱스와 둘 다 두면 로그가 2개 나가는 것이 정상이라고 가이드에 적혀 있다.
NAVER_SA_KEY = "s_15fd98e8a618"   # 2026-09-22 전환 추적 관리 화면에서 확인(상태 신청중)

_A_시작, _A_끝 = "<!-- AUTO:site-tail -->", "<!-- /AUTO:site-tail -->"


def _clarity_snippet():
    if not CLARITY_ID.strip():
        return ""
    return (
        '<script type="text/javascript">'
        '(function(c,l,a,r,i,t,y){c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};'
        't=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;'
        'y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);'
        '})(window,document,"clarity","script","%s");</script>' % CLARITY_ID.strip()
    )


def _naver_wa_snippet():
    if not NAVER_WA_ID.strip():
        return ""
    return (
        '<script type="text/javascript" src="//wcs.pstatic.net/wcslog.js"></script>'
        '<script type="text/javascript">'
        'if(!wcs_add) var wcs_add = {};'
        'wcs_add["wa"] = "%s";'
        'if(window.wcs) { wcs_do(); }'
        '</script>' % NAVER_WA_ID.strip()
    ) + _naver_sa_snippet()


def _naver_sa_snippet():
    # 공식 가이드 순서: 식별자 → wcs.inflow(쿠키 도메인) → wcs_do(PV) → 전환은 wcs.trans.
    # 완료 페이지가 없는 구조라 전환은 클릭 시점에 보낸다.
    #   tel: 클릭 → type "call" / 견적 문자 내용 완성 → type "custom001"(보고서 이름: 견적 문자 작성)
    # lead 를 쓰지 않는다 — 문자 내용을 만들어도 실제 발송은 확인할 수 없어 네이버의 lead(상담 신청 완료) 정의와 다르다.
    # 2026-10-07 이전에는 submit 캡처에서 lead 를 보냈으므로 그 전후 수치는 같은 기준이 아니다.
    # 옛 방식(wcs.cnv)과 섞으면 전환이 두 번 잡히므로 쓰지 않는다.
    if not NAVER_SA_KEY.strip():
        return ""
    return (
        '<script type="text/javascript">'
        'if(window.wcs){'
        'if(!wcs_add) var wcs_add = {};'
        'wcs_add["wa"] = "%s";'
        'wcs.inflow("ddasom.com");'
        'wcs_do();'
        'document.addEventListener("click",function(e){'
        'var a=e.target&&e.target.closest?e.target.closest(\'a[href^="tel:"]\'):null;'
        'if(a&&window.wcs&&wcs.trans){try{wcs_add["wa"]="%s";wcs.trans({type:"call"});}catch(x){}}'
        '},true);'
        'document.addEventListener("quote:prepared",function(){'
        'if(window.wcs&&wcs.trans){try{wcs_add["wa"]="%s";wcs.trans({type:"custom001"});}catch(x){}}'
        '});'
        '}'
        '</script>' % ((NAVER_SA_KEY.strip(),) * 3)
    )


# 푸터 사이트 안내에 싣는 목적지.
# 헤더 nav 는 8칸이라 협력 제휴·숙박 방음관이 들어갈 자리가 없다.
# 그 둘은 내부링크가 7개뿐이어서 푸터가 유일한 전 페이지 진입로다.
_사이트안내 = [
    ("services",   "커튼·블라인드 서비스"),
    ("gallery",    "시공 갤러리"),
    ("reviews/",   "시공후기"),
    ("guides/",    "커튼 가이드"),
    ("b2b",        "기업·기관 전용관"),
    ("b2b-hotel",  "호텔·모텔 방음커튼"),
    ("partner",    "인테리어·시공사 제휴"),
    ("areas",      "출장지역"),
    ("apply",      "견적 요청"),
]


def _sitenav(깊이, 현재):
    """전 페이지 공통 푸터 안내. 자기 페이지는 링크하지 않는다."""
    칸 = []
    for 경로, 이름 in _사이트안내:
        if 경로.rstrip("/") == 현재.rstrip("/"):
            칸.append('<span style="opacity:.55">%s</span>' % 이름)
        else:
            칸.append('<a href="%s%s">%s</a>' % (깊이, 경로, 이름))
    return ('<nav class="auto-sitenav" aria-label="사이트 안내" '
            'style="max-width:960px;margin:0 auto;padding:26px 16px 4px;'
            'border-top:1px solid rgba(0,0,0,.09);text-align:center;'
            'font-size:14px;line-height:2.1">'
            + ' · '.join(칸) + '</nav>')


def enrich_site_tail():
    """모든 공개 페이지에 사이트 안내·분석 스크립트·개인정보처리방침 링크를 넣는다.

    푸터 생김새가 페이지마다 달라서(홈은 크고, 후기는 한 줄, 지역 페이지는 아예 없음)
    푸터 안을 건드리지 않고 본문 끝에 한 줄을 붙이는 쪽으로 통일한다.
    여러 번 돌려도 결과가 같다.
    """
    링크 = ('<div class="auto-policy" style="text-align:center;padding:18px 16px 26px;'
            'font-size:13px;opacity:.7">'
            '<a href="%sprivacy">개인정보처리방침</a></div>')
    분석 = "".join(s for s in (_clarity_snippet(), _naver_wa_snippet()) if s)
    바뀜 = 0
    for f in sorted(ROOT.rglob("*.html")):
        if "_to_delete" in f.parts or "tests" in f.parts or f.name == "_template.html":
            continue
        t = f.read_text(encoding="utf-8", errors="replace")
        if "noindex" in t.lower():
            continue                       # 내부용 페이지는 건드리지 않는다
        자기링크빼기 = (f.name == "privacy.html")   # 방침 페이지가 자기를 링크할 이유는 없다
        깊이 = "../" * (len(f.relative_to(ROOT).parts) - 1)
        rel = f.relative_to(ROOT).as_posix()
        현재 = rel[:-len("index.html")] if f.name == "index.html" else rel[:-len(".html")]
        조각 = [_A_시작, _sitenav(깊이, 현재)]
        if not 자기링크빼기:
            조각.append(링크 % 깊이)
        if 분석:
            조각.append(분석)
        조각.append(_A_끝)
        덩어리 = "\n".join(조각)
        if _A_시작 in t:
            새것 = re.sub(re.escape(_A_시작) + r".*?" + re.escape(_A_끝), 덩어리, t, flags=re.S)
        else:
            새것 = t.replace("</body>", 덩어리 + "\n</body>", 1)
        if 새것 != t:
            f.write_text(새것, encoding="utf-8")
            바뀜 += 1
    켬 = "clarity %s · 네이버 %s" % (
        "켜짐" if CLARITY_ID.strip() else "꺼짐(CLARITY_ID 비어 있음)",
        "켜짐" if NAVER_WA_ID.strip() else "꺼짐(NAVER_WA_ID 비어 있음)")
    print(f"[ok] 방침 링크·분석 스크립트 {바뀜}장 (분석: {켬})")



# ── 아래 둘은 2026-09-02 신설 ─────────────────────────────
#   근거: SEO·GEO 외부조사 208건 (AI컴퍼니 `정보수집\SEO\종합_외부조사_20260902.md`)

_R_시작 = "<!-- AUTO:robots -->"
_R_끝 = "<!-- /AUTO:robots -->"


def 로봇메타():
    """모든 공개 페이지에 max-image-preview:large 를 넣는다.

    없으면 구글 Discover 에 큰 그림이 안 실리고 일반 검색의 그림 미리보기도 작아진다.
    커튼·블라인드는 눈으로 고르는 물건이라 그림이 곧 유입이다.

    이미 robots 메타가 있는 페이지(noindex 내부용)는 건드리지 않는다 —
    한 페이지에 robots 메타가 둘이면 구글이 합쳐 읽긴 하지만 지저분하다.
    여러 번 돌려도 결과가 같다.
    """
    덩어리 = (_R_시작 + '\n<meta name="robots" content="max-image-preview:large">\n' + _R_끝)
    바뀜 = 건너뜀 = 0
    for f in sorted(ROOT.rglob("*.html")):
        if "_to_delete" in f.parts or "tests" in f.parts or f.name == "_template.html":
            continue
        t = f.read_text(encoding="utf-8", errors="replace")
        if _R_시작 in t:
            새것 = re.sub(re.escape(_R_시작) + r".*?" + re.escape(_R_끝), 덩어리, t, flags=re.S)
        else:
            # 후기는 머리보강() 이 이미 넣는다. 남의 자리를 두 번 채우지 않는다.
            if 'name="robots"' in t:
                건너뜀 += 1
                continue
            if "</head>" not in t:
                continue
            새것 = t.replace("</head>", 덩어리 + "\n</head>", 1)
        if 새것 != t:
            f.write_text(새것, encoding="utf-8")
            바뀜 += 1
    print(f"[ok] robots 메타(max-image-preview) {바뀜}장 · 이미 있어 건너뜀 {건너뜀}장")


_L_시작 = "<!-- AUTO:related -->"
_L_끝 = "<!-- /AUTO:related -->"

# 제목에서 뽑을 제품 낱말. 겹치는 게 많을수록 비슷한 시공이다.
_제품말 = ["암막", "콤비", "롤스크린", "우드", "버티컬", "쉬폰", "속커튼", "커튼",
           "블라인드", "전동", "로만쉐이드", "허니콤", "방염", "채광", "린넨", "이중"]


def _제품(제목):
    return {w for w in _제품말 if w in 제목}


def 관련후기(posts):
    """후기 본문 끝(연락처 앞)에 비슷한 시공 4편을 건다.

    왜 여기인가 — 다 읽은 사람에게 **비슷한 시공을 보여준 뒤** 연락처로 간다.
    증거를 먼저 주고 그 다음에 청하는 순서다.

    고르는 기준
        같은 지역          +10   "포항 사람은 포항 시공을 본다"
        겹치는 제품 낱말   +3 씩
        최근 것            +0~2  (오래된 후기만 걸리지 않게)
    자기 자신은 뺀다. 4편이 안 되면 있는 만큼만 건다.

    지금까지 후기끼리 본문 링크가 **0개**였다(2026-09-02 실측 44편 전부).
    목록 페이지 하나에만 매달려 있어서 크롤러가 한 장씩 훑어 내려가야 했다.
    """
    if len(posts) < 2:
        return
    최신 = posts[0]["date"]
    바뀜 = 0
    for 나 in posts:
        내지역 = region_of(나["title"])
        내제품 = _제품(나["title"])
        점수 = []
        for 남 in posts:
            if 남["file"] == 나["file"]:
                continue
            s = 0
            if region_of(남["title"]) == 내지역:
                s += 10
            s += 3 * len(내제품 & _제품(남["title"]))
            s += 2 if 남["date"] >= 최신[:4] + "-07" else 0
            점수.append((s, 남["date"], 남))
        # 점수 높은 것 먼저, 점수가 같으면 최근 것 먼저
        점수.sort(key=lambda x: (x[0], x[1]), reverse=True)
        고른것 = [x[2] for x in 점수[:4]]
        if not 고른것:
            continue

        줄 = []
        for q in 고른것:
            y, mo, d = q["date"].split("-")
            썸 = (f'<span class="rel-thumb"><img src="{q["thumb"]}" alt="{q["title"]}" '
                  f'loading="lazy" decoding="async"></span>') if q["thumb"] else '<span class="rel-thumb"></span>'
            줄.append(
                f'<li><a href="{링크(q["file"])}">{썸}'
                f'<span class="rel-txt"><strong>{q["title"]}</strong>'
                f'<em>{y}.{mo}.{d} 시공</em></span></a></li>')
        # 그 지역에 입주 예정 단지가 있으면 한 줄 더 건다.
        # 왜 — 새로 만든 ipju/ 페이지가 지역 페이지 하나에서만 연결돼 있어
        # 구글이 못 찾고 있다(2026-09-06 URL 검사: "아직 알려지지 않은 URL").
        # 후기는 이미 색인된 페이지라 여기서 걸어주면 크롤러가 따라 들어간다.
        # 읽는 사람에게도 맞다 — 그 지역 시공을 보고 있는 사람이 그 지역 입주 예정자다.
        입주줄 = ""
        for 단지, 시기, 파일 in IPJU.get(내지역, []):
            입주줄 += (f'\n  <p class="rel-ipju"><a href="../ipju/{링크(파일)}">'
                      f'{단지}({시기} 입주) 커튼 준비 일정 보기 →</a></p>')

        # 그 지역 비교 노트 한 줄. 위 IPJU 주석과 같은 이유로 건다.
        노트줄 = ""
        if 내지역 in NOTES:
            제목, 주소 = NOTES[내지역]
            노트줄 = (f'\n  <p class="rel-note"><a href="{주소}" '
                     f'target="_blank" rel="noopener">{제목} →</a></p>')


        덩어리 = (_L_시작 +
                 '\n<section class="related">\n  <h2>비슷한 시공</h2>\n  <ul class="rel-list">\n    '
                 + "\n    ".join(줄) +
                 '\n  </ul>' + 입주줄 + 노트줄 + '\n</section>\n' + _L_끝)

        f = REVIEWS / 나["file"]
        t = f.read_text(encoding="utf-8")
        if _L_시작 in t:
            새것 = re.sub(re.escape(_L_시작) + r".*?" + re.escape(_L_끝), 덩어리, t, flags=re.S)
        elif '<div class="post-cta">' in t:
            새것 = t.replace('<div class="post-cta">', 덩어리 + '\n\n  <div class="post-cta">', 1)
        elif "</main>" in t:
            새것 = t.replace("</main>", 덩어리 + "\n</main>", 1)
        else:
            continue
        if 새것 != t:
            f.write_text(새것, encoding="utf-8")
            바뀜 += 1
    print(f"[ok] 비슷한 시공 링크 {바뀜}장 (편당 최대 4편)")



def css버전():
    """post.css 내용에서 버전을 뽑아 후기 46편의 ?v= 를 맞춘다.

    예전에는 `post.css?v=260830` 이 파일마다 손으로 박혀 있었다.
    CSS 를 고쳐도 이 숫자를 안 바꾸면 브라우저가 옛 CSS 를 계속 쓴다 —
    **고친 사람은 고쳤다고 믿고, 방문자는 옛 화면을 본다.**
    내용이 바뀌면 숫자가 저절로 바뀌게 한다.
    """
    css = REVIEWS / "post.css"
    if not css.exists():
        return
    v = hashlib.md5(css.read_bytes()).hexdigest()[:8]
    바뀜 = 0
    for f in sorted(REVIEWS.glob("*.html")):
        t = f.read_text(encoding="utf-8")
        새것 = re.sub(r"post\.css\?v=[0-9a-z]+", f"post.css?v={v}", t)
        if 새것 != t:
            f.write_text(새것, encoding="utf-8")
            바뀜 += 1
    print(f"[ok] post.css 버전 {v} — {바뀜}장")


def main():
    posts = sorted(
        (parse_post(p) for p in REVIEWS.glob("2*.html")),
        key=lambda p: p["date"],
        reverse=True,
    )
    # 각 후기 CTA를 그 지역 담당 실장으로 통일
    for p in posts:
        apply_cta(REVIEWS / p["file"], region_of(p["title"]))
    enrich_reviews()
    build_list(posts)
    print(f"[ok] reviews/index.html ({len(posts)} posts, CTA=지역 담당 실장)")
    build_home_gallery(posts)
    areas = build_area_pages(posts)
    build_home_areas(areas)
    관련후기(posts)      # 사진 감싸기 전에 — build_picture 가 <img> 를 <picture> 로 바꾼다
    enrich_site_tail()
    로봇메타()            # 후기 말고 나머지 페이지들
    css버전()             # CSS 고쳤으면 ?v= 를 저절로 바꾼다
    # 사진은 맨 나중에 감싼다. build_list·build_home_gallery 가 목록을 통째로 다시 쓰기 때문에
    # 먼저 감싸면 그 자리에서 <picture> 가 지워진다.
    build_webp()
    build_picture()
    build_sitemap(posts, areas)
    build_rss(posts)
    build_rss_link()
    build_robots()


if __name__ == "__main__":
    sys.exit(main())
