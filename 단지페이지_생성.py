# -*- coding: utf-8 -*-
"""입주 3~5년차 단지 페이지 (danji/).

★사진을 넣지 않는다 — 그 집 사진은 이미 후기 페이지에 다 쓰였다. 같은 사진을 또 쓰면 중복이다
  (사장님 지시 「사진 절대 중복 사용 금지」 2026-09-07). 사진은 후기 링크로 보게 한다.

2026-09-07 사장님 지시: 「신축입주는 피하자 — 가격경쟁이 너무 치열하다. 3~5년 된 아파트가 낫다.
전세가 만기되고 다른 사람이 또 입주할 수 있으니」.
입주장 페이지(ipju/)와 다른 점 — 우리가 이미 시공한 단지만 만든다. 사례·사진은 그 단지 후기에서만 가져온다.
각도는 일정 역산이 아니라 「이사 들어갈 때 / 앞사람 커튼 / 전세라 못 뚫을 때」.
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "danji")

STYLE = open(os.path.join(HERE, "areas", "pohang.html"), encoding="utf-8").read()
STYLE = STYLE[STYLE.index("<style>"):STYLE.index("</style>") + 8]

EXTRA = """<style>
.spec{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:6px}
.spec div{background:var(--white);border:1px solid var(--line);border-radius:12px;padding:13px 15px}
.spec b{display:block;font-size:19px;font-weight:800;letter-spacing:-.02em}
.spec span{font-size:13px;color:var(--soft)}
.case{background:var(--white);border:1px solid var(--line);border-radius:14px;overflow:hidden;margin-top:10px}
.case img{width:100%;max-height:460px;object-fit:cover;display:block}
.case div{padding:14px 16px}
.note{background:var(--bg2);border-left:3px solid var(--accent);border-radius:0 10px 10px 0;padding:14px 16px;font-size:15px;color:#4a4034;margin-top:16px}
ul.chk{list-style:none;background:var(--white);border:1px solid var(--line);border-radius:14px;padding:6px 4px;margin-top:6px}
ul.chk li{padding:12px 16px 12px 44px;position:relative;border-bottom:1px solid var(--line);font-size:16px}
ul.chk li:last-child{border-bottom:none}
ul.chk li:before{content:"";position:absolute;left:16px;top:17px;width:15px;height:15px;border:2px solid var(--accent);border-radius:4px}
ul.chk li b{display:block;font-size:14px;color:var(--soft);font-weight:500;margin-top:2px}
</style>"""

TAIL = """<!-- AUTO:site-tail -->
<div class="auto-policy" style="text-align:center;padding:18px 16px 26px;font-size:13px;opacity:.7"><a href="../privacy">개인정보처리방침</a></div>
<!-- /AUTO:site-tail -->"""

단지들 = [
    dict(
        file="hillstate-pohang.html", city="포항", danji="힐스테이트 포항",
        loc="경상북도 포항시 남구 오천읍", mgr="이실장", tel="010-2825-7275",
        title="힐스테이트 포항(오천) 커튼·블라인드 | 이사 들어갈 때 다시 맞추기 - 따솜커튼블라인드",
        desc="오천 힐스테이트 포항 1,717세대, 2023년 4월 입주. 이 단지에서 직접 시공한 사례와 함께, 이사 들어갈 때 앞사람 커튼을 쓸 수 있는지·전세라 벽을 못 뚫을 때 고르는 법을 정리했습니다. 포항 담당 이실장 010-2825-7275.",
        h1="힐스테이트 포항 커튼,<br>이사 들어갈 때 다시 맞추기",
        lead="2023년 4월에 입주한 단지입니다. 이제 처음 들어온 분들이 나가고 새로 들어오는 집이 생길 때입니다.<br>저희가 이 단지에서 실제로 시공한 집을 먼저 보여드립니다.",
        spec=[("1,717세대", "20개동 · 지상 최고 17층"), ("80·95·106㎡", "전용면적"),
              ("2023년 4월", "입주"), ("현대건설", "시공")],
        specnote="공개된 단지 정보에서 확인한 내용입니다.",
        review="../reviews/2026-10-02-pohang-ocheon-hillstate-combi-blackout-folding-door",
        img="../reviews/img/pohang-ocheon-hillstate-combi-blackout-folding-door/2.jpg",
        imgalt="오천 힐스테이트 거실 화이트 콤비블라인드",
        case=[
            "<b>2026년 10월, 이 단지의 한 집</b>",
            "예전 주인이 작은방 벽을 헐어 거실을 넓혀 둔 집이었습니다. 그 자리에 서랍장이 놓이면서 거실 어디서나 수납이 그대로 보였습니다.",
            "벽을 다시 쌓는 대신 천장 레일에 거는 화이트 홀딩도어로 그 자리를 나눴습니다. 거실 창은 화이트 콤비블라인드, 안방은 백아이보리 형상기억 암막커튼입니다.",
            "앞사람이 바꿔 둔 구조에 맞춰 다시 정한 집입니다. 지은 지 몇 년 된 단지에서는 이런 일이 흔합니다.",
        ],
        faq=[
            ("앞사람이 두고 간 커튼을 그대로 써도 되나요?",
             "레일과 봉이 멀쩡하면 그대로 쓰시는 편이 낫습니다. 원단만 바꾸면 비용이 줄어듭니다.<br>다만 앞사람이 창보다 짧게 맞춘 커튼이면 빛이 새고, 바닥에 끌리게 맞췄으면 해가 지나며 밑단이 변색돼 있기도 합니다. 사진을 보내주시면 쓸 것과 바꿀 것을 나눠 말씀드립니다."),
            ("전세라 벽에 구멍을 내기 어렵습니다.",
             "커튼박스 안쪽이나 기존 레일 자리를 쓰면 새로 뚫지 않고 해결되는 경우가 많습니다.<br>집주인과 원상복구 조건을 먼저 확인하시고, 자세한 방법은 <a href=\"../guides/jeonse-curtain\" style=\"color:var(--accent2);font-weight:700\">전세집 커튼 가이드</a>에 정리해 두었습니다."),
            ("이사 날짜가 정해졌는데 언제 연락드리면 되나요?",
             "열쇠를 받으시는 날을 알려주시면 그 뒤로 실측을 잡습니다. 맞춤 제작이라 재고가 없으니 이사 날짜가 정해지는 대로 창 사진부터 보내주시면 됩니다.<br>제작 기간은 제품과 시기에 따라 달라 실측 때 안내드립니다."),
        ],
    ),
]

공통체크 = [
    ("레일·봉이 어디에 달려 있는지", "커튼박스 안인지, 천장인지, 창틀 위 벽인지에 따라 새로 뚫어야 하는지가 갈립니다"),
    ("앞사람 커튼의 길이", "바닥에서 몇 cm 뜨는지, 끌리는지. 빛샘과 변색을 보는 기준입니다"),
    ("벽을 헐었거나 확장한 자리", "구조가 바뀐 집은 창과 가림이 필요한 자리가 달라집니다"),
    ("각 방을 무엇으로 쓰실지", "같은 평면이어도 앞사람과 쓰임이 다르면 답이 달라집니다"),
]


def 맨글(x):
    return " ".join(re.sub(r"<[^>]+>", " ", x.replace("<br>", " ")).split())


def 페이지(d):
    url = "https://ddasom.com/danji/%s" % d["file"].removesuffix(".html")
    faq_ld = ",\n        ".join(
        json.dumps({"@type": "Question", "name": 맨글(q),
                    "acceptedAnswer": {"@type": "Answer", "text": 맨글(a)}}, ensure_ascii=False)
        for q, a in d["faq"])
    faq_html = "\n    ".join(
        "<details%s><summary>%s</summary><p>%s</p></details>" % (" open" if i == 0 else "", q, a)
        for i, (q, a) in enumerate(d["faq"]))
    spec = "\n    ".join("<div><b>%s</b><span>%s</span></div>" % s for s in d["spec"])
    case = "\n      ".join('<p class="body">%s</p>' % p for p in d["case"])
    chk = "\n    ".join("<li>%s<b>%s</b></li>" % c for c in 공통체크)
    return """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>%(title)s</title>
<meta name="description" content="%(desc)s">
<link rel="canonical" href="%(url)s">
<meta property="og:type" content="article">
<meta property="og:site_name" content="따솜커튼블라인드">
<meta property="og:title" content="%(danji)s 커튼·블라인드 — 이사 들어갈 때">
<meta property="og:description" content="%(desc)s">
<meta property="og:url" content="%(url)s">
<meta property="og:image" content="https://ddasom.com/promo-img/og-ipju-card.jpg">
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {"@type": "WebPage", "@id": "%(url)s#webpage", "url": "%(url)s", "name": "%(danji)s 커튼·블라인드",
     "inLanguage": "ko", "isPartOf": {"@id": "https://ddasom.com/#website"}, "about": {"@id": "https://ddasom.com/#business"}},
    {"@type": "FAQPage", "mainEntity": [
        %(faq_ld)s
    ]}
  ]
}
</script>
%(style)s
%(extra)s
</head>
<body>
<main style="max-width:760px;margin:0 auto;padding:28px 16px 40px">
  <p style="font-size:14px"><a href="../" style="color:var(--accent2)">따솜커튼블라인드</a> · <a href="../areas/pohang" style="color:var(--accent2)">%(city)s 출장 시공</a></p>
  <span class="tag">%(city)s · 입주 3년 차 단지</span>
  <h1>%(h1)s</h1>
  <p class="body">%(lead)s</p>

  <div class="spec">
    %(spec)s
  </div>
  <p class="hdr" style="font-size:13px;color:var(--soft);margin-top:8px">%(specnote)s</p>

  <h2>저희가 이 단지에서 한 시공</h2>
  <div class="case">
    <div>
      %(case)s
      <p class="body"><a href="%(review)s" style="color:var(--accent2);font-weight:700">이 집 시공후기 전체 보기 →</a></p>
    </div>
  </div>

  <h2>이사 들어가기 전에 보실 것</h2>
  <p class="body">지은 지 몇 년 된 집은 새 아파트와 다릅니다. 앞사람이 남긴 것과 바꿔 둔 것부터 보시면 비용이 줄어듭니다.</p>
  <ul class="chk">
    %(chk)s
  </ul>
  <div class="note">이 네 가지를 사진으로 보내주시면 쓸 것과 바꿀 것을 나눠서 대략적인 견적을 먼저 알려드립니다. 정확한 치수는 방문해서 잽니다.</div>

  <h2>자주 묻는 것</h2>
  <div class="faq">
    %(faq_html)s
  </div>

  <div class="cta-final">
    <h2>%(danji)s, 이사 준비 중이시면</h2>
    <p class="body">창 사진을 방별로 보내주시면 됩니다. %(city)s 담당 %(mgr)s이 직접 실측하고 설치합니다.</p>
    <p class="body"><a class="btn btn-accent" href="tel:%(tel)s">%(mgr)s %(tel)s</a> <a class="btn" href="../apply">견적 요청</a></p>
  </div>
</main>
%(tail)s
</body>
</html>
""" % dict(d, url=url, style=STYLE, extra=EXTRA, tail=TAIL, faq_ld=faq_ld, faq_html=faq_html,
           spec=spec, case=case, chk=chk, img_abs=d["img"].replace("../", ""))


def main():
    os.makedirs(OUT, exist_ok=True)
    for d in 단지들:
        html = 페이지(d)
        나쁜말 = [w for w in ("개략", "카카오톡", "카톡", "무료") if w in html]
        if 나쁜말:
            raise SystemExit("금지어: %s (%s)" % (나쁜말, d["file"]))
        open(os.path.join(OUT, d["file"]), "w", encoding="utf-8").write(html)
        print("%-12s %7d바이트  danji/%s" % (d["danji"], len(html.encode("utf-8")), d["file"]))


if __name__ == "__main__":
    main()
