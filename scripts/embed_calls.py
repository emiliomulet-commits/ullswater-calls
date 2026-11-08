#!/usr/bin/env python3
"""Semantic index of the call texts for the "Ask EU Funding" agent (Worker search_calls).

Splits every open/forthcoming call text into overlapping passages, embeds them with
BAAI/bge-small-en-v1.5 (the same model the Worker uses for the query, @cf/baai/bge-small-en-v1.5)
and writes:
  site/data/vec.bin   int8 vectors, one row of DIM bytes per passage (L2-normalised, x127)
  site/data/vec.json  {"model", "dim", "updated", "ids": [call ids], "rows": [[call index, passage start], ...]}
  site/data/words.json {call id: "all distinct words of the call text"} for exact-term matching in the Worker
Unchanged passages are reused from .cache/embed (keyed by text hash), so daily runs only embed new text.
"""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MODEL = "BAAI/bge-small-en-v1.5"
DIM = 384
CHUNK, OVERLAP = 1100, 200
CACHE = ROOT / ".cache" / "embed" / "vectors.npz"


def passages(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= CHUNK:
        return [(0, text)] if text else []
    out, start = [], 0
    while start < len(text):
        end = min(len(text), start + CHUNK)
        if end < len(text):  # cut at a sentence or word boundary
            cut = max(text.rfind(". ", start + CHUNK // 2, end), text.rfind(" ", start + CHUNK // 2, end))
            end = cut + 1 if cut > 0 else end
        out.append((start, text[start:end].strip()))
        if end >= len(text):
            break
        start = max(end - OVERLAP, start + 1)
    return out


def main():
    calls = json.loads((ROOT / "site/data/calls.json").read_text(encoding="utf-8"))["calls"]
    tfile = ROOT / "data/topic_text.json"
    texts = json.loads(tfile.read_text(encoding="utf-8")) if tfile.exists() else {}
    ids, rows, docs = [], [], []
    for i, c in enumerate(calls):
        ids.append(c["id"])
        head = f"{c['title']}. {c.get('callTitle') or ''}. {' '.join(c.get('tags') or [])}"
        body = texts.get(c["id"]) or c.get("summary") or ""
        rows.append([i, -1]); docs.append(head)          # title passage
        for start, p in passages(body):
            rows.append([i, start]); docs.append(f"{c['title']}. {p}")

    keys = [hashlib.sha1(d.encode("utf-8")).hexdigest()[:16] for d in docs]
    cache = {}
    if CACHE.exists():
        z = np.load(CACHE)
        cache = dict(zip(z["keys"].tolist(), z["vecs"]))
    todo = [j for j, k in enumerate(keys) if k not in cache]
    if todo:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(MODEL, device="cpu")
        vecs = model.encode([docs[j] for j in todo], batch_size=64, normalize_embeddings=True, show_progress_bar=False)
        q = np.clip(np.round(vecs * 127), -127, 127).astype(np.int8)
        for j, v in zip(todo, q):
            cache[keys[j]] = v
    mat = np.stack([cache[k] for k in keys]).astype(np.int8)
    (ROOT / "site/data/vec.bin").write_bytes(mat.tobytes())
    (ROOT / "site/data/vec.json").write_text(json.dumps({
        "model": MODEL, "dim": DIM, "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ids": ids, "rows": rows}, separators=(",", ":")), encoding="utf-8")
    words = {c["id"]: " ".join(sorted(set(re.findall(r"[a-z][a-z0-9\-]{2,}", (texts.get(c["id"]) or c.get("summary") or "").lower())))) for c in calls}
    (ROOT / "site/data/words.json").write_text(json.dumps(words, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(CACHE, keys=np.array(keys), vecs=mat)
    print(f"{len(ids)} calls, {len(rows)} passages, {len(todo)} newly embedded, vec.bin {mat.nbytes // 1024} KB")


if __name__ == "__main__":
    main()
