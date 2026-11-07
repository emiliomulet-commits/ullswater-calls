#!/usr/bin/env python3
"""Notify IndexNow (Bing, Yandex, Seznam, Naver...) of the site's URLs after each deploy.
Usage: python scripts/indexnow.py <sitemap.xml> <host>  (key read from content/indexnow_key.txt)"""
import json, re, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
key = (ROOT / "content" / "indexnow_key.txt").read_text().strip()
sitemap, host = sys.argv[1], sys.argv[2]
urls = re.findall(r"<loc>([^<]+)</loc>", Path(sitemap).read_text(encoding="utf-8"))
MAX = 50  # Bing accepts few URLs per day from sites it does not know yet; send in daily batches
if len(sys.argv) > 3:  # optional file with URLs already notified: send only new ones (plus home)
    seen_f = Path(sys.argv[3])
    seen = set(seen_f.read_text().split()) if seen_f.exists() else set()
    new = [u for u in urls if u not in seen]
    urls = (new or urls[:1])[:MAX]
    all_urls = sorted(seen | set(urls))
else:
    seen_f = None
    urls = urls[:MAX]
body = json.dumps({"host": host, "key": key, "keyLocation": f"https://{host}/{key}.txt", "urlList": urls[:10000]}).encode()
req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8"})
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        print("IndexNow", r.status, len(urls), "URLs")
        if seen_f is not None:  # record only after a successful notification
            seen_f.write_text("\n".join(all_urls))
except Exception as e:
    print("IndexNow failed:", e)
