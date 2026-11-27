"""One-off: pick ONE open Spanish tender from PLACSP and download every official document of its notice.

Writes samples/ficha-licitacion/<id>/: entry.xml, docs/<n>_<type>.pdf, docs/<n>_<type>.txt (pdftotext -layout), index.json.
Run on GitHub Actions (PLACSP is not reachable from the dev container). SAMPLE_ID=<entry id tail> forces a tender.
"""
import json, os, re, subprocess, sys, time, urllib.request, xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

UA = "UllswaterTendersBot/1.0 (+https://tenders.ullswaterinvestments.com)"
FEED = "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"
OUT = Path(__file__).resolve().parent.parent / "samples" / "ficha-licitacion"
local = lambda t: t.rsplit("}", 1)[-1]  # noqa: E731


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=300) as r:
                return r.read(), r.headers.get("Content-Type", ""), r.headers.get("Content-Disposition", "")
        except Exception as e:  # noqa: BLE001
            print("retry", url[-80:], e)
            time.sleep(5 * (i + 1))
    raise RuntimeError(url)


def deep(el, name):
    return [e for e in el.iter() if local(e.tag) == name]


def first(el, name):
    r = deep(el, name)
    return (r[0].text or "").strip() if r else ""


def docs_of(cfs):
    out = []
    for e in cfs.iter():
        ln = local(e.tag)
        if ln.endswith("DocumentReference"):
            uri = first(e, "URI")
            if uri:
                out.append({"kind": ln.replace("DocumentReference", "") or "Doc", "name": first(e, "ID") or first(e, "FileName"),
                            "type": first(e, "DocumentTypeCode"), "uri": uri})
    seen, res = set(), []
    for d in out:
        if d["uri"] not in seen:
            seen.add(d["uri"]); res.append(d)
    return res


def score(entry):
    cfs = next((e for e in entry if local(e.tag) == "ContractFolderStatus"), None)
    if cfs is None or first(cfs, "ContractFolderStatusCode") != "PUB":
        return None
    dl = first(cfs, "EndDate")[:10]
    if not dl or dl < (date.today() + timedelta(days=12)).isoformat():
        return None
    ds = docs_of(cfs)
    kinds = {d["kind"] for d in ds}
    if not {"Legal", "Technical"} <= kinds:
        return None
    try:
        v = float(first(cfs, "TaxExclusiveAmount") or 0)
    except ValueError:
        v = 0
    if not 150_000 <= v <= 3_000_000:
        return None
    buyer = " ".join(e.text or "" for e in deep(cfs, "Name"))
    s = len(ds) + (5 if re.search(r"ayuntamiento|diputaci|ajuntament|concello", buyer, re.I) else 0)
    s += 3 * min(len(deep(cfs, "ProcurementProjectLot")), 3) + (2 if first(cfs, "TypeCode") in ("2", "3") else 0)
    return s, cfs, ds


def main():
    want = os.environ.get("SAMPLE_ID", "").strip()
    url, best, pages = FEED, None, 0
    while url and pages < 12:
        raw, _, _ = get(url); pages += 1
        root = ET.fromstring(raw)
        for entry in (e for e in root if local(e.tag) == "entry"):
            eid = first(entry, "id").rsplit("/", 1)[-1]
            if want and eid != want:
                continue
            r = score(entry) if not want else (99, next(e for e in entry if local(e.tag) == "ContractFolderStatus"), None)
            if r and (best is None or r[0] > best[0]):
                best = (r[0], eid, entry, r[1], r[2] or docs_of(r[1]))
        if want and best:
            break
        url = next((l.get("href") for l in root if local(l.tag) == "link" and l.get("rel") == "next"), None)
        print("page", pages, "best", best and (best[0], best[1]))
    if not best:
        sys.exit("no candidate")
    _, eid, entry, cfs, ds = best
    d = OUT / eid
    (d / "docs").mkdir(parents=True, exist_ok=True)
    (d / "entry.xml").write_bytes(ET.tostring(entry, encoding="utf-8"))
    idx = {"id": eid, "title": first(cfs, "Name"), "link": next((l.get("href") for l in entry if local(l.tag) == "link"), ""), "docs": []}
    for n, doc in enumerate(ds, 1):
        try:
            body, ctype, disp = get(doc["uri"])
        except RuntimeError:
            doc["error"] = "download failed"; idx["docs"].append(doc); continue
        ext = "pdf" if body[:4] == b"%PDF" else "html" if b"<html" in body[:500].lower() else "bin"
        if body[:2] == b"PK":
            ext = "zip"
        fn = f"{n:02d}_{doc['kind']}.{ext}"
        (d / "docs" / fn).write_bytes(body)
        doc.update(file=fn, bytes=len(body), content_type=ctype, disposition=disp[:200])
        if ext == "pdf":
            subprocess.run(["pdftotext", "-layout", str(d / "docs" / fn), str(d / "docs" / (fn[:-4] + ".txt"))], check=False)
            try:
                pg = subprocess.run(["pdfinfo", str(d / "docs" / fn)], capture_output=True, text=True).stdout
                doc["pages"] = int(re.search(r"Pages:\s+(\d+)", pg).group(1))
            except Exception:  # noqa: BLE001
                pass
        idx["docs"].append(doc)
        print("doc", fn, len(body), doc.get("pages"))
    (d / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    print("SAMPLE", eid, idx["title"])


if __name__ == "__main__":
    main()
