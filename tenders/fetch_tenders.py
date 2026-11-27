#!/usr/bin/env python3
"""Fetch open and forthcoming public tenders for tenders.ullswaterinvestments.com.

Two public sources, no registration needed:
1. EU institutions and agencies: EU Funding & Tenders Portal, SEDIA search API (type 0 = tender),
   the same client as scripts/fetch_calls.py.
2. National, regional and local tenders of every EU/EEA country: TED (Tenders Electronic Daily)
   search API v3, competition notices whose tender deadline is still ahead (scope ACTIVE).

Writes site-tenders/data/:
  eu.json             every EU-institution tender (full records)
  ted/<ISO3>.json     TED notices of one buyer country (compact records)
  stats.json          figures for the home page of www and of this site
TED is rate-limited (HTTP 429 after a short burst), so calls are spaced and retried with back-off.
A cache of the previous run (.cache/tenders/) keeps the site alive if a source is down.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from fetch_calls import api, first, strip_html, parse_date  # noqa: E402

OUT = ROOT / "site-tenders" / "data"
CACHE = ROOT / ".cache" / "tenders"
TED = "https://api.ted.europa.eu/v3/notices/search"
UA = "UllswaterTendersBot/1.0 (+https://tenders.ullswaterinvestments.com)"
STATUS = {"31094501": "forthcoming", "31094502": "open"}
CONTRACT = {"31095498": "services", "31095499": "supplies", "31095501": "works"}
TED_NATURE = {"services": "services", "supplies": "supplies", "works": "works", "combined": "services"}
PROC = {  # F&T procedure codes (numeric eForms ids and legacy names) → short label
    "47396220": "Open procedure", "OPEN": "Open procedure", "open": "Open procedure",
    "47396214": "Negotiated procedure (middle/low value)", "EX_ANTE_PUBLICITY": "Negotiated procedure (middle/low value)",
    "47396224": "Restricted procedure", "RESTRICTED_PROCEDURE": "Restricted procedure",
    "47396222": "Planned call for tenders", "PRIOR_INFORMATION_NOTICE": "Planned call for tenders",
    "47396208": "Competitive procedure with negotiation", "NEGOTIATED_COMPETITIVE": "Competitive procedure with negotiation",
    "47396202": "Call for expression of interest", "CALL_EXPRESSION_INTEREST_PC": "Call for expression of interest",
    "47396204": "Call for expression of interest (vendor list)", "CALL_EXPRESSION_INTEREST_VL": "Call for expression of interest (vendor list)",
    "47396198": "Accelerated open procedure", "ACCELERATED_OPEN": "Accelerated open procedure",
    "47396206": "Competitive dialogue", "COMPETITIVE_DIALOGUE": "Competitive dialogue",
    "47396212": "Dynamic purchasing system", "47396210": "Design contest", "DESIGN_CONTEST": "Design contest",
    "47396216": "Innovation partnership", "INNOVATION_PARTNERSHIP": "Innovation partnership", "47396226": "Other procedure",
}
TED_PROC = {"open": "Open procedure", "restricted": "Restricted procedure", "neg-w-call": "Competitive procedure with negotiation",
            "comp-dial": "Competitive dialogue", "innovation": "Innovation partnership", "oth-single": "Other single-stage procedure",
            "oth-mult": "Other multi-stage procedure", "neg-wo-call": "Negotiated without call"}
TED_FIELDS = ["publication-number", "notice-title", "notice-type", "publication-date", "buyer-name", "buyer-country",
              "organisation-country-buyer", "buyer-city", "deadline-receipt-tender-date-lot", "classification-cpv",
              "contract-nature-main-proc", "procedure-type", "estimated-value-proc", "estimated-value-cur-proc",
              "place-of-performance-country-proc", "description-proc"]
TED_QUERY = "notice-type IN (cn-standard cn-social cn-desg) AND deadline-receipt-tender-date-lot>={today}"
LANG_PREF = ["eng", "spa", "fra", "deu", "ita", "por", "nld"]


# ---------- EU institutions (F&T portal) ----------

def _json(s, default):
    try:
        return json.loads(s) if isinstance(s, str) and s else default
    except ValueError:
        return default


def _dates_in(obj, keys=("deadline", "submission", "receipt")):
    """Every ISO date found under a key that looks like a deadline, anywhere in a nested JSON value."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and any(x in k.lower() for x in keys):
                m = re.match(r"(\d{4}-\d{2}-\d{2})", v)
                if m:
                    out.append(m.group(1))
            else:
                out += _dates_in(v, keys)
    elif isinstance(obj, list):
        for v in obj:
            out += _dates_in(v, keys)
    return out


def ted_key(identifier):
    """'2026S123-456789' → '456789-2026' (TED publication number), to drop TED duplicates of F&T tenders."""
    m = re.match(r"(\d{4})/?S\s?\d+-0*(\d+)", identifier or "")
    return f"{m.group(2)}-{m.group(1)}" if m else None


def fetch_eu(today):
    q = {"bool": {"must": [{"terms": {"type": ["0"]}}, {"terms": {"status": list(STATUS)}}]}}
    first_page = api("search", q, 1)
    total = first_page.get("totalResults", 0)
    raw = list(first_page.get("results", []))
    for p in range(2, (total + 99) // 100 + 1):
        raw += api("search", q, p).get("results", [])
        time.sleep(0.4)
    print(f"  F&T tenders flagged open/forthcoming: {len(raw)}/{total}")
    out, seen, dropped = [], set(), Counter()
    for r in raw:
        m = r.get("metadata", {})
        status = STATUS.get(first(m, "status"))
        ident = first(m, "identifier") or first(m, "cftId")
        if not status or ident in seen:
            continue
        seen.add(ident)
        lots = _json(first(m, "lots"), {})
        cands = [d.date().isoformat() for d in (parse_date(x) for x in (m.get("deadlineDate") or []) + (m.get("closingDate") or [])) if d]
        cands += _dates_in(lots)
        exa = first(m, "cftEXARegistrationDeadline")[:10]
        if re.match(r"\d{4}-\d{2}-\d{2}", exa):
            cands.append(exa)
        future = sorted(d for d in cands if d >= today)
        start = (first(m, "startDate") or first(m, "cftPublicationDateEForm"))[:10]
        planned = first(m, "cftPlannedDate")[:10]
        if cands and not future:
            dropped["deadline passed"] += 1
            continue
        if not cands:  # no deadline published: keep only recent notices (the portal leaves old ones flagged open)
            ref = planned if re.match(r"\d{4}-\d{2}-\d{2}", planned) else start
            if not ref or ref < (date.fromisoformat(today) - timedelta(days=180)).isoformat():
                dropped["no deadline, older than 6 months"] += 1
                continue
        leads = _json(first(m, "cftLeadContractingAuthorityCode"), [])
        buyer = (leads[0].get("name") if leads and isinstance(leads[0], dict) else "") or ""
        value = first(m, "cftEstimatedTotalProcedureValue")
        try:
            value = int(float(value)) or None
        except (TypeError, ValueError):
            value = None
        cpv = first(m, "mainCpv") or (_json(first(m, "mainCpvCode"), {}) or {}).get("mainCode", "")
        nlots = len((lots or {}).get("procurementProjectLots") or []) if isinstance(lots, dict) else 0
        out.append({
            "id": re.sub(r"[^A-Za-z0-9-]+", "-", ident).strip("-"),
            "src": "eu",
            "ref": first(m, "callIdentifier") or ident,
            "title": (first(m, "title") or r.get("summary") or "").strip(),
            "buyer": buyer.strip() or first(m, "caName"),
            "country": "EU",
            "status": status,
            "nature": CONTRACT.get(first(m, "contractType") or first(m, "cftProcurementType"), ""),
            "procedure": PROC.get(first(m, "procedureType"), ""),
            "cpv": cpv[:8],
            "published": start or None,
            "deadline": future[0] if future else None,
            "planned": planned if re.match(r"\d{4}-\d{2}-\d{2}", planned) else None,
            "value": value,
            "currency": (first(m, "cftEstimatedOverallContractCurrency") or "EUR") if value else None,
            "lots": nlots or None,
            "summary": strip_html(first(m, "description"), 600),
            "lang": first(m, "language"),
            "url": first(m, "url") or r.get("url", ""),
            "tedKey": ted_key(ident),
        })
    print(f"  F&T tenders kept: {len(out)}; dropped: {dict(dropped)}")
    return out


# ---------- TED (national tenders) ----------

def ted_post(body, retries=7):
    data = json.dumps(body).encode()
    for attempt in range(retries):
        req = urllib.request.Request(TED, data=data, headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                wait = min(120, 8 * 2 ** attempt)
                print(f"  TED {e.code}, waiting {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise RuntimeError(f"TED {e.code}: {e.read().decode('utf-8', 'replace')[:400]}")
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == retries - 1:
                raise
            time.sleep(10 * (attempt + 1))


def pick_lang(v, prefer=LANG_PREF):
    """TED multilingual value {'eng': [...], 'deu': [...]} → (text, lang)."""
    if isinstance(v, str):
        return v, ""
    if isinstance(v, list):
        return (str(v[0]) if v else ""), ""
    if not isinstance(v, dict) or not v:
        return "", ""
    for lang in prefer:
        if v.get(lang):
            x = v[lang]
            return (x[0] if isinstance(x, list) else x), lang
    lang = next(iter(v))
    x = v[lang]
    return (x[0] if isinstance(x, list) else x), lang


def one(v):
    if isinstance(v, list):
        return v[0] if v else None
    return v


def clean_title(t):
    """TED titles read 'Country – CPV label – Buyer's own title': keep the buyer's title."""
    t = re.sub(r"\s+", " ", t or "").strip()
    parts = t.split(" – ", 2)
    return parts[2] if len(parts) == 3 and len(parts[2]) > 8 else t


def ted_record(n, today):
    pub = n.get("publication-number", "")
    dls = sorted({str(x)[:10] for x in (n.get("deadline-receipt-tender-date-lot") or []) if str(x)[:10] >= today})
    if not dls:
        return None
    title, tlang = pick_lang(n.get("notice-title"))
    title_es, _ = pick_lang(n.get("notice-title"), ["spa", "eng"])
    buyer, _ = pick_lang(n.get("buyer-name"))
    desc, _ = pick_lang(n.get("description-proc"))
    country = one(n.get("buyer-country")) or one(n.get("organisation-country-buyer")) or one(n.get("place-of-performance-country-proc")) or "XXX"
    cpvs = []
    for c in n.get("classification-cpv") or []:
        c = str(c)[:8]
        if c not in cpvs:
            cpvs.append(c)
    val = one(n.get("estimated-value-proc"))
    try:
        val = int(float(val)) or None
    except (TypeError, ValueError):
        val = None
    rec = {
        "id": pub, "src": "ted", "title": clean_title(title)[:300],
        "buyer": re.sub(r"\s+", " ", buyer).strip()[:160], "city": (one(n.get("buyer-city")) or "")[:60] if isinstance(one(n.get("buyer-city")), str) else "",
        "country": country, "status": "open",
        "nature": TED_NATURE.get(str(one(n.get("contract-nature-main-proc")) or ""), ""),
        "procedure": TED_PROC.get(str(one(n.get("procedure-type")) or ""), ""),
        "cpv": cpvs[:3], "published": str(n.get("publication-date") or "")[:10] or None, "deadline": dls[0],
        "value": val, "currency": one(n.get("estimated-value-cur-proc")) if val else None,
        "summary": strip_html(desc, 200),
        "url": f"https://ted.europa.eu/en/notice/-/detail/{pub}",
    }
    if title_es and title_es != title:
        rec["title_es"] = clean_title(title_es)[:300]
    if rec.get("title_es") == rec["title"]:
        rec.pop("title_es")
    if isinstance(rec["city"], list):
        rec["city"] = ""
    return rec


def fetch_ted(today):
    q = TED_QUERY.format(today=today.replace("-", ""))
    body = {"query": q, "fields": TED_FIELDS, "limit": 250, "scope": "ACTIVE", "paginationMode": "ITERATION"}
    out, seen, token, pages, total = [], set(), None, 0, None
    while True:
        b = dict(body)
        if token:
            b["iterationNextToken"] = token
        r = ted_post(b)
        pages += 1
        total = r.get("totalNoticeCount", total)
        for n in r.get("notices", []):
            rec = ted_record(n, today)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                out.append(rec)
        token = r.get("iterationNextToken")
        if pages % 20 == 0:
            print(f"  TED page {pages}: {len(out)} kept of {total}")
        if not token or not r.get("notices") or pages > 400:
            break
        time.sleep(2.5)  # stay under the anonymous rate limit
    print(f"  TED active competition notices: {len(out)} kept of {total} ({pages} pages)")
    return out


def main():
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    CACHE.mkdir(parents=True, exist_ok=True)
    (OUT / "ted").mkdir(parents=True, exist_ok=True)
    srcs = {}
    for name, fn, minimum in (("eu", fetch_eu, 20), ("ted", fetch_ted, 2000)):
        cache = CACHE / f"{name}.json"
        try:
            print(f"Fetching {name}…")
            recs = fn(today)
            if len(recs) < minimum:
                raise RuntimeError(f"only {len(recs)} records (sanity minimum {minimum})")
            cache.write_text(json.dumps(recs, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"::warning::{name} source failed ({e}); using the cache of the previous run")
            recs = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else []
            recs = [x for x in recs if not x.get("deadline") or x["deadline"] >= today]
        srcs[name] = recs
    eu, ted = srcs["eu"], srcs["ted"]
    eu_keys = {x["tedKey"] for x in eu if x.get("tedKey")}
    ted = [x for x in ted if x["id"] not in eu_keys]
    eu.sort(key=lambda x: (x["status"] != "open", x["deadline"] or x.get("planned") or "9999"))
    ted.sort(key=lambda x: x["deadline"])

    by_country = {}
    for x in ted:
        by_country.setdefault(x["country"], []).append(x)
    for old in (OUT / "ted").glob("*.json"):
        old.unlink()
    for cc, recs in by_country.items():
        (OUT / "ted" / f"{cc}.json").write_text(json.dumps(recs, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUT / "eu.json").write_text(json.dumps(eu, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    soon = (now.date() + timedelta(days=30)).isoformat()
    week = (now.date() + timedelta(days=7)).isoformat()
    stats = {
        "updated": now.isoformat(timespec="seconds"),
        "eu": len(eu), "euOpen": sum(1 for x in eu if x["status"] == "open"), "euForthcoming": sum(1 for x in eu if x["status"] == "forthcoming"),
        "ted": len(ted), "total": len(eu) + len(ted),
        "closingIn30Days": sum(1 for x in eu + ted if x.get("deadline") and x["deadline"] <= soon),
        "closingIn7Days": sum(1 for x in eu + ted if x.get("deadline") and x["deadline"] <= week),
        "countries": {cc: len(v) for cc, v in sorted(by_country.items(), key=lambda kv: -len(kv[1]))},
        "nature": dict(Counter(x["nature"] or "other" for x in eu + ted)),
        "sources": ["European Commission – Funding & Tenders Portal (SEDIA search API)", "Publications Office of the EU – TED (search API v3)"],
    }
    (OUT / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in stats.items() if k != "countries"}, indent=1))
    print("top countries:", list(stats["countries"].items())[:15])


if __name__ == "__main__":
    main()
