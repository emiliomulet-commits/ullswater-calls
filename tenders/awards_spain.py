#!/usr/bin/env python3
"""Spanish public contract awards (adjudicaciones) for the free tender diagnosis.

Source: the same PLACSP open-data feeds as fetch_spain.py, monthly zips <feed>_YYYYMM.zip. We read entries whose status is
ADJ (adjudicada) or RES (resuelta) and keep, per lot: buyer, province, CPV group, budget, offers received, lowest and highest
offer and the winning amount. The winner's NIF is never stored in clear: only sha256("ES"+NIF).

Incremental: each month is read once into .cache/tenders/awards/<feed>_<YYYYMM>.json (the current month is read again every
run). At most AWARDS_MONTHS_PER_RUN new months per run, newest first, back to AWARDS_MONTHS_BACK months.

Writes .cache/tenders/awards_out/ (copied into the site by tenders/diagnostico/diag_build.py):
  competencia.json            competition model per buyer+CPV group, province+CPV group and CPV group (aggregates only:
                              number of offers and average rebate; no company names)
  adjudicatarios/<hh>.json    winners' profiles keyed by the first 16 hex characters of sha256("ES"+NIF): number of
                              contracts won, total, largest, main public buyers and average winning rebate
  adjudicatarios/meta.json    period covered
"""
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_spain as F  # noqa: E402

CACHE = F.CACHE / "awards"
OUT = F.CACHE / "awards_out"
MONTHS_BACK = int(os.environ.get("AWARDS_MONTHS_BACK", "36"))
PER_RUN = int(os.environ.get("AWARDS_MONTHS_PER_RUN", "3"))
TIME_BUDGET = int(os.environ.get("AWARDS_TIME_BUDGET", "2400"))
DONE = {"ADJ", "RES"}


def num(el, *path):
    try:
        v = float(F.txt(el, *path))
        return v if v > 0 else None
    except ValueError:
        return None


def nif_hash(nif):
    n = re.sub(r"[^0-9A-Z]", "", (nif or "").upper())
    if n.startswith("ES") and len(n) > 9:
        n = n[2:]
    return hashlib.sha256(("ES" + n).encode()).hexdigest() if len(n) >= 8 else None


def lot_budgets(cfs):
    """{lot id: budget without VAT}, '' = the whole contract."""
    out = {}
    pp = F.kid(cfs, "ProcurementProject")
    b = num(pp, "BudgetAmount", "TaxExclusiveAmount")
    if b:
        out[""] = b
    for lot in F.kids(cfs, "ProcurementProjectLot"):
        lid = F.txt(lot, "ID")
        lb = num(F.kid(lot, "ProcurementProject"), "BudgetAmount", "TaxExclusiveAmount")
        if lid and lb:
            out[lid] = lb
    return out


probed = False


def award(entry):
    """Atom entry → (id, updated, compact award record or None)."""
    global probed
    eid = F.txt(entry, "id")
    upd = F.txt(entry, "updated")
    cfs = next((e for e in entry if F.local(e.tag) == "ContractFolderStatus"), None)
    if cfs is None or F.txt(cfs, "ContractFolderStatusCode") not in DONE:
        return eid, upd, None
    results = F.kids(cfs, "TenderResult")
    if not results:
        return eid, upd, None
    if not probed:  # one example in the logs, to check the CODICE structure
        probed = True
        print("  probe ADJ entry:", ET.tostring(results[0], encoding="unicode")[:1500])
    party = F.kid(cfs, "LocatedContractingParty")
    p = F.kid(party, "Party")
    buyer = re.sub(r"\s+", " ", F.txt(p, "PartyName", "Name")).strip()[:160]
    pp = F.kid(cfs, "ProcurementProject")
    cpv = next(((c.text or "").strip()[:8] for c in F.deep(pp, "ItemClassificationCode") if c.text), "")
    nuts = [(e.text or "").strip() for e in F.deep(pp, "CountrySubentityCode") + F.deep(p, "CountrySubentityCode") if e.text]
    prov, _ = F.region_of(F.txt(p, "PostalAddress", "PostalZone"), nuts, [buyer] + F.parent_chain(party) + [F.txt(p, "PostalAddress", "CityName")])
    budgets = lot_budgets(cfs)
    lots = []
    for r in results:
        atp = F.kid(r, "AwardedTenderedProject")
        lid = F.txt(atp, "ProcurementProjectLotID")
        bud = budgets.get(lid) or (budgets.get("") if not lid or len(budgets) <= 2 else None)
        win = num(atp, "LegalMonetaryTotal", "TaxExclusiveAmount") or num(atp, "LegalMonetaryTotal", "PayableAmount")
        try:
            n = int(float(F.txt(r, "ReceivedTenderQuantity") or 0))
        except ValueError:
            n = 0
        wp = F.kid(r, "WinningParty")
        lots.append({"b": bud, "n": n, "lo": num(r, "LowerTenderAmount"), "hi": num(r, "HigherTenderAmount"), "w": win,
                     "h": nif_hash(F.txt(wp, "PartyIdentification", "ID")), "d": F.txt(r, "AwardDate")[:10]})
    if not lots:
        return eid, upd, None
    return eid, upd, {"buyer": buyer, "prov": prov, "cpv3": cpv[:3], "lots": lots}


def read_month(name, url, ym):
    zurl = url.replace(".atom", f"_{ym}.zip")
    best = {}
    with tempfile.TemporaryFile() as tmp:
        req = urllib.request.Request(zurl, headers={"User-Agent": F.UA})
        with urllib.request.urlopen(req, timeout=900) as r:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                tmp.write(chunk)
            ctype, status = r.headers.get("Content-Type", ""), r.status
        size = tmp.tell()
        tmp.seek(0)
        if not zipfile.is_zipfile(tmp):
            tmp.seek(0)
            raise ValueError(f"not a zip (HTTP {status}, {ctype}, {size} bytes): {tmp.read(300)!r}")
        tmp.seek(0)
        zf = zipfile.ZipFile(tmp)
        for m in (m for m in zf.namelist() if m.endswith(".atom")):
            for el in ET.fromstring(zf.read(m)):
                if F.local(el.tag) != "entry":
                    continue
                eid, upd, a = award(el)
                if a and eid and upd >= best.get(eid, ("", None))[0]:
                    best[eid] = (upd, a)
    print(f"  {name} {ym}: {size / 1e6:.0f} MB, {len(best):,} awarded tenders")
    return {eid: dict(a, upd=upd) for eid, (upd, a) in best.items()}


def rebate(x):
    if not x["b"] or not x["w"]:
        return None
    r = 1 - x["w"] / x["b"]
    return r if -0.05 <= r < 0.7 else None


def mean_rebate(x):
    """Average offer rebate of a lot: midpoint of the lowest and highest offers when given, else the winner's."""
    if x["b"] and x["lo"] and x["hi"] and x["n"] >= 2:
        r = 1 - (x["lo"] + x["hi"]) / 2 / x["b"]
        if -0.05 <= r < 0.7:
            return r, max(0.0, (x["hi"] - x["lo"]) / x["b"]) / 4
    r = rebate(x)
    return (r, None) if r is not None else (None, None)


def quantiles(vals, k=9):
    v = sorted(vals)
    return [v[min(len(v) - 1, int(len(v) * (i + 0.5) / k))] for i in range(k)]


def aggregate(records):
    groups = defaultdict(list)
    for a in records:
        if not a["cpv3"]:
            continue
        for x in a["lots"]:
            if x["n"] < 1:
                continue
            for level, key in (("órgano", f"{a['buyer']}|{a['cpv3']}"), ("provincia", f"{a['prov']}|{a['cpv3']}"), ("cpv", a["cpv3"])):
                if level == "provincia" and not a["prov"]:
                    continue
                groups[(level, key)].append(x)
    out = {"órgano": {}, "provincia": {}, "cpv": {}}
    for (level, key), xs in groups.items():
        if len(xs) < 5:
            continue
        mids, spreads = [], []
        for x in xs:
            m, s = mean_rebate(x)
            if m is not None:
                mids.append(m)
                if s is not None:
                    spreads.append(s)
        if len(mids) < 5:
            continue
        mu = sum(mids) / len(mids)
        between = math.sqrt(sum((m - mu) ** 2 for m in mids) / len(mids))
        within = sum(spreads) / len(spreads) if spreads else 0.04
        dates = sorted(x["d"] for x in xs if x["d"])
        out[level][key] = {"samples": len(xs), "n_offers": quantiles([max(1, x["n"]) for x in xs]),
                           "mu": round(max(0.0, mu), 4), "sd": round(min(0.15, max(0.02, math.sqrt(between ** 2 + within ** 2))), 4),
                           "from": dates[0] if dates else "", "to": dates[-1] if dates else ""}
    return out


def winners(records):
    prof = {}
    for a in records:
        for x in a["lots"]:
            if not x["h"]:
                continue
            p = prof.setdefault(x["h"][:16], {"n": 0, "total": 0, "max": 0, "buyers": defaultdict(int), "reb": []})
            p["n"] += 1
            p["total"] += x["w"] or 0
            p["max"] = max(p["max"], x["w"] or 0)
            p["buyers"][a["buyer"]] += 1
            r = rebate(x)
            if r is not None:
                p["reb"].append(r)
    shards = defaultdict(dict)
    for k, p in prof.items():
        shards[k[:2]][k] = {"n": p["n"], "total": round(p["total"]), "max": round(p["max"]),
                            "buyers": [b for b, _ in sorted(p["buyers"].items(), key=lambda t: -t[1])[:3]],
                            "rebaja": round(sum(p["reb"]) / len(p["reb"]), 3) if p["reb"] else None}
    return shards


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    months = F.months_back(now, MONTHS_BACK * 31)[-MONTHS_BACK:]
    current = months[-1]
    t0, done, fails = time.time(), 0, 0
    for ym in reversed(months):
        for name, url in F.FEEDS.items():
            f = CACHE / f"{name}_{ym}.json"
            if f.exists() and ym != current:
                continue
            if ym != current and done >= PER_RUN * len(F.FEEDS):
                continue
            if time.time() - t0 > TIME_BUDGET:
                print("  time budget reached; the rest next run")
                break
            if fails >= 4:
                break
            try:
                f.write_text(json.dumps(read_month(name, url, ym), ensure_ascii=False), encoding="utf-8")
                done += 1
                fails = 0
            except Exception as e:  # a missing or broken month must not stop the others, but stop hammering a blocked source
                fails += 1
                print(f"  {name} {ym}: {e}" + ("; stopping for this run" if fails >= 4 else ""), file=sys.stderr)
    seen, records = {}, []
    for f in sorted(CACHE.glob("*_*.json")):
        for eid, a in json.loads(f.read_text(encoding="utf-8")).items():
            if eid not in seen or a["upd"] > seen[eid]["upd"]:
                seen[eid] = a
    records = list(seen.values())
    files = sorted(CACHE.glob("*_*.json"))
    first = min((f.stem.split("_")[-1] for f in files), default=current)
    print(f"  awards: {len(records):,} awarded tenders, {sum(len(a['lots']) for a in records):,} lots, months from {first}")
    comp = aggregate(records)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "competencia.json").write_text(json.dumps(comp, ensure_ascii=False), encoding="utf-8")
    adj = OUT / "adjudicatarios"
    adj.mkdir(exist_ok=True)
    for old in adj.glob("*.json"):
        old.unlink()
    for hh, d in winners(records).items():
        (adj / f"{hh}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    (adj / "meta.json").write_text(json.dumps({"from": f"{first[:4]}-{first[4:]}-01", "updated": now.date().isoformat(),
                                               "contracts": len(records)}), encoding="utf-8")
    print(f"  competencia: {', '.join(f'{k} {len(v)}' for k, v in comp.items())}")


if __name__ == "__main__":
    main()
