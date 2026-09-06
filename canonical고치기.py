# -*- coding: utf-8 -*-
"""canonical·og:url·sitemap 이 리다이렉트되는 `.html` 주소를 가리키는 것을 고친다.

## 왜 (2026-09-06 실측)

  사이트맵  →  https://ddasom.com/areas/pohang.html
                 ↓ 라이브가 리다이렉트
             https://ddasom.com/areas/pohang
                 ↓ 그 페이지의 canonical
             https://ddasom.com/areas/pohang.html   ← 다시 리다이렉트되는 주소

  canonical 이 자기를 리다이렉트하는 주소를 정식이라고 지목하는 구성이다.
  구글은 사이트맵 주소를 크롤하러 갔다가 리다이렉트되고, 도착지에서 다시 원래 주소가
  정식이라고 듣는다. 「페이지에 리디렉션이 있음」 으로 분류돼 색인이 늦거나 안 된다.

  실측: sitemap 75쪽 중 색인 29쪽. 지역 페이지 15개 중 4개만 색인
  (울진·영주·예천·대전만 되고 포항·경주·안동·경산·구미·대구가 전부 빠졌다).
  canonical 75개 중 73개가 `.html`, og:url 도 73개.

## 무엇을 고치나

  1) *.html 안의 `rel="canonical"` 과 `og:url` 에서 `.html` 을 뗀다
  2) build.py 의 사이트맵 생성부에서 `.html` 을 뗀다 (사이트맵은 build.py 가 만든다)
  3) sitemap.xml 을 직접 고치지는 않는다 — build.py 를 돌리면 다시 만들어진다

  ※ `/reviews/` 처럼 이미 슬래시로 끝나는 주소와 `index.html` 은 건드리지 않는다.

## 쓰기

  python canonical고치기.py            ← 미리보기만 한다 (아무것도 안 바꿈)
  python canonical고치기.py --적용     ← 실제로 고친다
  git diff                             ← 무엇이 바뀌었는지 본다
  git checkout .                       ← 되돌린다

★적용 후에도 **배포는 별개다.** `배포.py` 를 돌려야 라이브에 간다.
  배포 뒤 서치콘솔에서 주력 지역부터 색인 요청: 포항·경주·안동·경산·구미·대구.
"""
import re
import sys
from pathlib import Path

여기 = Path(__file__).parent
적용 = "--적용" in sys.argv

# canonical/og:url 의 https://ddasom.com/... .html → 확장자 뗀 주소
# index.html 은 남긴다(루트 문서). 슬래시로 끝나는 주소는 애초에 안 걸린다.
꼴 = re.compile(r'(https://ddasom\.com/[^"\']*?)\.html(?=["\'])')


def 뗄까(주소):
    """index.html 은 그대로 둔다."""
    return not 주소.endswith("/index")


def html고치기():
    바뀐파일, 바뀐줄 = 0, 0
    for f in sorted(여기.rglob("*.html")):
        if ".wrangler" in f.parts or "node_modules" in f.parts:
            continue
        원 = f.read_text(encoding="utf-8")
        새 = 원
        for 줄패턴 in (r'(<link[^>]*rel="canonical"[^>]*>)',
                     r'(<meta[^>]*property="og:url"[^>]*>)'):
            def 한줄(m):
                nonlocal 바뀐줄
                태그 = m.group(1)
                고침 = 꼴.sub(lambda x: x.group(1) if 뗄까(x.group(1)) else x.group(0), 태그)
                if 고침 != 태그:
                    바뀐줄 += 1
                return 고침
            새 = re.sub(줄패턴, 한줄, 새)
        if 새 != 원:
            바뀐파일 += 1
            if 적용:
                f.write_text(새, encoding="utf-8")
            else:
                보기 = [l.strip() for l in 원.splitlines()
                       if 'rel="canonical"' in l or 'og:url' in l]
                if 바뀐파일 <= 3:
                    print(f"  {f.relative_to(여기)}")
                    for l in 보기[:2]:
                        print(f"    전 {l[:96]}")
                        print(f"    후 {꼴.sub(lambda x: x.group(1) if 뗄까(x.group(1)) else x.group(0), l)[:96]}")
    return 바뀐파일, 바뀐줄


def build고치기():
    f = 여기 / "build.py"
    원 = f.read_text(encoding="utf-8")
    새 = 원.replace(
        'urls += [(f"{BASE_URL}/areas/{slug}.html", today) for _r, slug, _n in areas]',
        'urls += [(f"{BASE_URL}/areas/{slug}", today) for _r, slug, _n in areas]')
    for 이름 in ("b2b", "b2b-bangyeom", "b2b-office", "b2b-school", "b2b-clinic",
              "b2b-shop", "services", "gallery", "areas", "apply", "privacy"):
        새 = 새.replace(f'{{BASE_URL}}/{이름}.html', f'{{BASE_URL}}/{이름}')
    # 후기·입주 페이지는 파일명이 변수로 들어온다 — 붙일 때 확장자를 뗀다
    새 = 새.replace(
        'urls += [(f"{BASE_URL}/reviews/{p[\'file\']}", p["date"]) for p in posts]',
        'urls += [(f"{BASE_URL}/reviews/{p[\'file\'].removesuffix(\'.html\')}", p["date"]) for p in posts]')
    새 = 새.replace(
        'urls += [(f"{BASE_URL}/ipju/{file}", today) for _d, _w, file in IPJU.values()]',
        'urls += [(f"{BASE_URL}/ipju/{file.removesuffix(\'.html\')}", today) for _d, _w, file in IPJU.values()]')
    달라짐 = 새 != 원
    if 달라짐 and 적용:
        f.write_text(새, encoding="utf-8")
    return 달라짐


def main():
    print("=== canonical·og:url ===")
    파일, 줄 = html고치기()
    print(f"  고칠 파일 {파일}개 · 태그 {줄}곳" + ("  → 적용함" if 적용 else "  (미리보기)"))
    print("\n=== build.py 사이트맵 생성부 ===")
    바뀜 = build고치기()
    print("  " + ("고칠 곳 있음" + ("  → 적용함" if 적용 else "  (미리보기)")
                 if 바뀜 else "이미 고쳐져 있음 또는 패턴을 못 찾음"))
    if not 적용:
        print("\n실제로 고치려면:  python canonical고치기.py --적용")
        print("고친 뒤 확인:      git diff   ·  되돌리기: git checkout .")
        print("★배포는 별개입니다 — 배포.py 를 돌려야 라이브에 갑니다.")
    else:
        print("\n다음: python build.py  (사이트맵 다시 생성) → git diff 로 확인 → 배포.py")


if __name__ == "__main__":
    main()
