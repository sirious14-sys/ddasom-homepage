# -*- coding: utf-8 -*-
import sys, build
from pathlib import Path

def posts():
    return sorted((build.parse_post(p) for p in build.REVIEWS.glob("2*.html")),
                  key=lambda p: p["date"], reverse=True)

ph = sys.argv[1]
P = posts()

if ph == "cta":
    for p in P:
        build.apply_cta(build.REVIEWS / p["file"], build.region_of(p["title"]))
    print("cta ok", len(P))
elif ph.startswith("enrich"):
    a, b = int(sys.argv[2]), int(sys.argv[3])
    n = 0
    for f in sorted(build.REVIEWS.glob("2*.html"))[a:b]:
        o = f.read_text(encoding="utf-8")
        s, qa = build.머리보강(o, f.name)
        s = build.지연로딩(s)
        if s != o:
            f.write_text(s, encoding="utf-8"); n += 1
        print("  ", f.name, qa)
    print("enrich ok", n)
elif ph == "list":
    build.build_list(P); print("list ok")
elif ph == "gallery":
    build.build_home_gallery(P); print("gallery ok")
elif ph == "areas":
    a = build.build_area_pages(P); build.build_home_areas(a); print("areas ok", len(a))
elif ph == "tail":
    build.enrich_site_tail(); print("tail ok")
elif ph == "webp":
    build.build_webp(); print("webp ok")
elif ph == "picture":
    build.build_picture(); print("picture ok")
elif ph == "sitemap":
    a = build.build_area_pages(P); build.build_sitemap(P, a); print("sitemap ok")
elif ph == "rsslink":
    build.build_rss_link(); build.build_robots(); print("rsslink ok")
elif ph == "rss":
    build.build_rss(P); print("rss ok")
