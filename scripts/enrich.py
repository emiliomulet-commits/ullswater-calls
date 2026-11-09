"""Editorial overlays for calls whose portal record is thin (mostly cascade calls run by EIT KICs, projects, etc.).

One JSON file per call in content/enrich/<anything>.json with {"id": "<call id in calls.json>", ...}.
Top-level fields replace the portal values (title, summary, maxEU, ...); the "extra" object
(official_url, conditions, resources, sessions, source_checked) is rendered on the call page by call_pages.py.
Every fact must come from the official page named in extra.official_url. Used by fetch_calls.py and build_site.py.
"""
import json
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "content" / "enrich"
REPLACE = {"title", "summary", "minEU", "maxEU", "grants", "tags"}


def load():
    out = {}
    for f in sorted(DIR.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        out[d["id"]] = d
    return out


def apply(calls):
    ov = load()
    n = 0
    for c in calls:
        o = ov.get(c["id"])
        if not o:
            continue
        for k in REPLACE & o.keys():
            c[k] = o[k]
        if o.get("extra"):
            c["extra"] = o["extra"]
        n += 1
    if n:
        print(f"  editorial overlays applied: {n}")
    return calls
