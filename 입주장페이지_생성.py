# -*- coding: utf-8 -*-
"""입주 예정 단지별 페이지 생성 (ipju/).

블로그 선점글과 문장이 겹치면 안 된다 — 블로그는 읽을거리, 여기는 실무 안내다.
그 단지에서 시공한 적이 없으므로 사례를 지어내지 않는다.
후기 카드는 「그 지역」 후기임을 제목에 명시한다.
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "ipju")

STYLE = open(os.path.join(HERE, "areas", "yeongju.html"), encoding="utf-8").read()
STYLE = STYLE[STYLE.index("<style>"):STYLE.index("</style>") + 8]

EXTRA = """<style>
table.sched{width:100%;border-collapse:collapse;background:var(--white);border:1px solid var(--line);border-radius:14px;overflow:hidden;font-size:15px;margin-top:6px}
table.sched th,table.sched td{padding:12px 14px;text-align:left;border-bottom:1px solid var(--line)}
table.sched th{background:var(--bg2);font-weight:700;font-size:14px;color:var(--accent2);white-space:nowrap}
table.sched tr:last-child td{border-bottom:none}
table.sched td:first-child{font-weight:700;white-space:nowrap}
.wrapx{overflow-x:auto}
ul.chk{list-style:none;background:var(--white);border:1px solid var(--line);border-radius:14px;padding:6px 4px;margin-top:6px}
ul.chk li{padding:12px 16px 12px 44px;position:relative;border-bottom:1px solid var(--line);font-size:16px}
ul.chk li:last-child{border-bottom:none}
ul.chk li:before{content:"";position:absolute;left:16px;top:17px;width:15px;height:15px;border:2px solid var(--accent);border-radius:4px}
ul.chk li b{display:block;font-size:14px;color:var(--soft);font-weight:500;margin-top:2px}
.note{background:var(--bg2);border-left:3px solid var(--accent);border-radius:0 10px 10px 0;padding:14px 16px;font-size:15px;color:#4a4034;margin-top:16px}
.hdr{font-size:14px;color:var(--soft);margin-top:8px}
.spec{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:6px}
.spec div{background:var(--white);border:1px solid var(--line);border-radius:12px;padding:13px 15px}
.spec b{display:block;font-size:19px;font-weight:800;letter-spacing:-.02em}
.spec span{font-size:13px;color:var(--soft)}
</style>"""

TAIL = """<!-- AUTO:site-tail -->
<div class="auto-policy" style="text-align:center;padding:18px 16px 26px;font-size:13px;opacity:.7"><a href="../privacy.html">개인정보처리방침</a></div>
<script type="text/javascript">(function(c,l,a,r,i,t,y){c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);})(window,document,"clarity","script","y88nlkwv9e");</script>
<!-- /AUTO:site-tail -->"""


import re


def 후기카드(area, n):
    """지역 페이지에서 실제 후기 카드 블록을 그대로 가져온다. 상대경로 깊이가 같다."""
    t = open(os.path.join(HERE, "areas", area + ".html"), encoding="utf-8").read()
    카드들 = re.findall(r'<a class="card".*?</a>', t, re.S)
    if not 카드들:
        raise SystemExit("후기 카드를 못 찾았다: " + area)
    return chr(10).join(카드들[:n])


def 페이지(d):
    url = "https://ddasom.com/ipju/%s" % d["file"]
    def 맨글(x):
        """JSON-LD에는 태그 없는 순수 문장만 넣는다. 따옴표는 json이 이스케이프한다."""
        return " ".join(re.sub(r"<[^>]+>", " ", x.replace("<br>", " ")).split())

    faq_ld = ",\n        ".join(
        json.dumps({"@type": "Question", "name": 맨글(q),
                    "acceptedAnswer": {"@type": "Answer", "text": 맨글(a)}},
                   ensure_ascii=False)
        for q, a in d["faq"])
    faq_html = "\n    ".join(
        "<details%s><summary>%s</summary><p>%s</p></details>" % (" open" if i == 0 else "", q, a)
        for i, (q, a) in enumerate(d["faq"]))
    sched = "\n      ".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % r for r in d["sched"])
    chk = "\n    ".join("<li>%s<b>%s</b></li>" % c for c in d["chk"])
    spec = "\n    ".join("<div><b>%s</b><span>%s</span></div>" % s for s in d["spec"])
    본문 = "\n\n  ".join(d["body"])

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
<meta property="og:title" content="%(ogtitle)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:url" content="%(url)s">
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebPage",
      "@id": "%(url)s#webpage",
      "url": "%(url)s",
      "name": "%(ogtitle)s",
      "inLanguage": "ko",
      "isPartOf": {"@id": "https://ddasom.com/#website"},
      "provider": {"@id": "https://ddasom.com/#business"},
      "description": "%(desc)s"
    },
    {
      "@type": "BreadcrumbList",
      "itemListElement": [
        {"@type":"ListItem","position":1,"name":"따솜커튼블라인드","item":"https://ddasom.com/"},
        {"@type":"ListItem","position":2,"name":"%(city)s 커튼·블라인드 시공","item":"https://ddasom.com/areas/%(area)s.html"},
        {"@type":"ListItem","position":3,"name":"%(danji)s 커튼·블라인드","item":"%(url)s"}
      ]
    },
    {
      "@type": "Service",
      "name": "%(danji)s 커튼·블라인드 입주 시공",
      "serviceType": "커튼·블라인드 맞춤 제작 및 시공",
      "provider": {"@id": "https://ddasom.com/#business"},
      "areaServed": {"@type": "Place", "name": "%(loc)s"}
    },
    {
      "@type": "FAQPage",
      "mainEntity": [
        %(faq_ld)s
      ]
    }
  ]
}
</script>
%(style)s
%(extra)s
<meta name="robots" content="max-image-preview:large">
</head>
<body>
<div class="wrap">
  <div class="crumb"><a href="../">따솜커튼블라인드</a> › <a href="../areas/%(area)s.html">%(city)s</a> › %(danji)s</div>

  <div class="hero">
    <span class="tag">%(movein)s 입주 · %(city)s</span>
    <h1>%(h1)s</h1>
    <p>%(lead)s</p>
    <div class="mgr">
      <div><div class="who">%(city)s 담당</div><div class="tel">%(mgr)s %(tel)s</div></div>
      <a class="call" href="tel:%(tel)s">전화 상담</a>
    </div>
  </div>

  <h2>이 단지 규모</h2>
  <div class="spec">
    %(spec)s
  </div>
  <p class="hdr">%(specnote)s</p>

  %(body)s

  <h2>%(movein)s 입주면 언제 뭘 하시면 되나</h2>
  <div class="wrapx">
  <table class="sched">
    <tr><th>시기</th><th>하실 일</th><th>왜</th></tr>
      %(sched)s
  </table>
  </div>
  <div class="note">%(schednote)s</div>

  <h2>사전점검일에 적어 오실 것</h2>
  <p class="body">사전점검은 법으로 정해져 있습니다.</p>
  <p class="body">주택법 제48조의2에 따라 시공사는 입주지정기간이 시작되기 45일 전까지, 이틀 이상 사전점검을 열어야 합니다.</p>
  <p class="body">실제로는 입주 두세 달 전에 하는 경우가 많습니다.</p>
  <p class="body">그날이 잔금 전에 세대 안에 들어가실 수 있는 거의 유일한 날입니다.</p>
  <p class="body">줄자를 꼭 챙겨 가십시오.</p>
  <ul class="chk">
    %(chk)s
  </ul>
  <p class="body">이 정도만 있으면 방문 전에 대략적인 견적을 먼저 알려드릴 수 있습니다.</p>
  <p class="body">정확한 치수는 열쇠를 받으신 다음에 저희가 다시 잽니다.</p>

  <h2>이웃과 날짜를 맞추시면 서로 빠릅니다</h2>
  <p class="body">입주 기간에는 엘리베이터에 이삿짐이 계속 오르내립니다.</p>
  <p class="body">같은 날 같은 라인에 두세 집이 모이면 한 번에 올라가 끝냅니다.</p>
  <p class="body">저희도 빠르고 입주민들도 기다리는 시간이 줄어듭니다.</p>
  <p class="body">이웃과 같이 문의하시는 경우 일정을 붙여서 잡아 드립니다.</p>

  <h2>%(city)s에서 실제로 한 시공입니다</h2>
  <p class="body">%(danji)s는 아직 입주 전이라 이 단지 시공 사례는 없습니다.</p>
  <p class="body">아래는 %(city)s 다른 곳에서 저희가 실제로 시공한 집들입니다.</p>
  <div class="cards">
    %(cards)s
  </div>

  <h2>자주 묻는 것</h2>
  <div class="faq">
    %(faq_html)s
  </div>

  <div class="cta-final">
    <h2>%(danji)s 입주 준비, 지금 상담하세요</h2>
    <p>창 사진만 있어도 대략적인 견적 안내가 가능합니다.<br>%(city)s 담당 %(mgr)s이 직접 방문합니다.</p>
    <a href="tel:%(tel)s">%(mgr)s %(tel)s 전화</a>
  </div>

  <p class="foot">따솜커튼블라인드 · 대구·경북 전지역 커튼·블라인드 출장 시공<br>
  <a href="../" style="color:var(--accent2)">ddasom.com 홈으로</a> · <a href="../areas/%(area)s.html" style="color:var(--accent2)">%(city)s 커튼·블라인드</a> · <a href="../quote.html" style="color:var(--accent2)">가격 안내</a></p>
</div>

<div class="mbar">
  <a href="tel:%(tel)s">전화</a>
  <a href="sms:%(tel)s?&body=%(danji)s 커튼 실측 문의합니다.">문자</a>
</div>
%(tail)s
</body>
</html>
""" % dict(d, url=url, style=STYLE, extra=EXTRA, tail=TAIL, faq_ld=faq_ld,
           faq_html=faq_html, sched=sched, chk=chk, spec=spec, body=본문,
           cards=후기카드(d["area"], d["ncards"]))


from 입주장_단지데이터 import 단지들


def main():
    os.makedirs(OUT, exist_ok=True)
    for d in 단지들:
        html = 페이지(d)
        나쁜말 = [w for w in ("개략", "카카오톡", "카톡", "무료") if w in html]
        # 「무료」는 통째로 잡는다 — 「무료 방문 실측」처럼 목록에 없는 표현이 샌 적이 있다(2026-09-06)
        if 나쁜말:
            raise SystemExit("금지어: %s (%s)" % (나쁜말, d["file"]))
        제어 = sum(1 for c in html if ord(c) < 32 and c not in "\n\r\t")
        if 제어:
            raise SystemExit("제어문자 %d개 (%s)" % (제어, d["file"]))
        open(os.path.join(OUT, d["file"]), "w", encoding="utf-8").write(html)
        print("%-16s %7d바이트  ipju/%s" % (d["danji"], len(html.encode("utf-8")), d["file"]))
    print("")
    print("%d개 생성" % len(단지들))


if __name__ == "__main__":
    main()
