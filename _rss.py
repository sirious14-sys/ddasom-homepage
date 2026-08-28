# -*- coding: utf-8 -*-
import json, build, datetime
m = json.load(open('/tmp/pubdates.json', encoding='utf-8'))
today = datetime.date.today().isoformat()
for f in build.REVIEWS.glob("2*.html"):
    build._발행일캐시[f.name] = m.get(f.name) or today
P = sorted((build.parse_post(p) for p in build.REVIEWS.glob("2*.html")),
           key=lambda p: p["date"], reverse=True)
build.build_rss(P)
