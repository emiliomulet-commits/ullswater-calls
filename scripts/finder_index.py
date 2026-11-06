#!/usr/bin/env python3
"""Compact search index for the Fund Finder (site/data/finder.json).

For each open/forthcoming call: the 40 most characteristic terms (TF-IDF over the
call texts), plus the metadata the finder filters on. Matching runs in the browser.
"""
import json
import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer

ROOT = Path(__file__).resolve().parent.parent


def action_type(c):
    a = " ".join(c.get("actions") or []).lower()
    if c["kind"] == "cascade": return "cascade"
    if "innovation action" in a and "research and" not in a: return "IA"
    if "research and innovation" in a: return "RIA"
    if "coordination and support" in a: return "CSA"
    if "eic" in a or "accelerator" in c["id"].lower(): return "EIC"
    if "msca" in c["id"].lower(): return "MSCA"
    if "pre-commercial" in a or "procurement" in a: return "PCP"
    return "other"


def main():
    calls = json.loads((ROOT / "site/data/calls.json").read_text(encoding="utf-8"))["calls"]
    texts = json.loads((ROOT / "data/topic_text.json").read_text(encoding="utf-8"))
    docs = [texts.get(c["id"]) or c["title"] for c in calls]
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1, max_df=0.3, sublinear_tf=True,
                          token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9\-]{2,}\b")
    X = vec.fit_transform(docs)
    vocab = vec.get_feature_names_out()
    out = []
    for i, c in enumerate(calls):
        row = X.getrow(i)
        pairs = sorted(zip(row.indices, row.data), key=lambda t: -t[1])[:40]
        out.append({
            "id": c["id"], "t": c["title"], "p": c["programme"], "s": c["status"], "d": c.get("deadline"), "k": c["kind"],
            "a": action_type(c), "b": c.get("budget"), "lo": c.get("minEU"), "hi": c.get("maxEU"),
            "w": {vocab[j]: round(float(v), 3) for j, v in pairs},
        })
    (ROOT / "site/data/finder.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Finder index: {len(out)} calls")


if __name__ == "__main__":
    main()
