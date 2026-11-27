#!/usr/bin/env python3
"""Phase 1 probe: measure the real volume and field shape of EU tenders.

Runs in GitHub Actions (the EU APIs are reachable there). Prints:
- F&T portal (SEDIA) facets for type/status and a sample of tender records
- TED v3: which fields the search API accepts, how many active notices there are,
  and their split by country and contract nature.
Writes tenders/probe-report.json (uploaded as a workflow artifact).
"""
import json, sys, time, urllib.request, urllib.error, uuid
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from fetch_calls import api, first  # same SEDIA client as the calls site

OUT = Path(__file__).resolve().parent / "probe-report.json"
TED = "https://api.ted.europa.eu/v3/notices/search"
UA = "UllswaterTendersBot/1.0 (+https://tenders.ullswaterinvestments.com)"
report = {}


def ted(body):
    req = urllib.request.Request(TED, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:1500]


def sedia():
    print("== F&T portal facets ==")
    f = api("facet", {"bool": {"must": []}}, size=1)
    facets = {}
    for x in f.get("facets", []):
        if x.get("name") in ("type", "status", "procedureType", "contractType", "tenderType", "frameworkProgramme"):
            facets[x["name"]] = [(v.get("rawValue"), v.get("value"), v.get("count")) for v in x.get("values", [])][:60]
    print(json.dumps(facets, indent=1, ensure_ascii=False)[:6000])
    report["sedia_facets"] = facets
    # Tenders are type 0 in SEDIA; try with and without status filter
    for label, q in [
        ("type0_all", {"bool": {"must": [{"terms": {"type": ["0"]}}]}}),
        ("type0_open_fc", {"bool": {"must": [{"terms": {"type": ["0"]}}, {"terms": {"status": ["31094501", "31094502"]}}]}}),
    ]:
        try:
            r = api("search", q, 1, size=5)
        except Exception as e:
            print(label, "ERROR", e); continue
        print(f"\n{label}: totalResults={r.get('totalResults')}")
        report[label] = {"total": r.get("totalResults"), "sample": [x.get("metadata", {}) for x in r.get("results", [])[:3]]}
        for x in r.get("results", [])[:2]:
            m = x.get("metadata", {})
            print(" keys:", sorted(m.keys()))
            print(" ", {k: (m.get(k) or [""])[0][:160] if isinstance(m.get(k), list) and m.get(k) else m.get(k) for k in sorted(m.keys())})
    # status facet within tenders
    try:
        f2 = api("facet", {"bool": {"must": [{"terms": {"type": ["0"]}}]}}, size=1)
        for x in f2.get("facets", []):
            if x.get("name") in ("status", "procedureType", "contractType", "deadlineModel", "typeOfMainContract"):
                print("tender facet", x["name"], [(v.get("rawValue"), v.get("value"), v.get("count")) for v in x.get("values", [])][:30])
                report.setdefault("tender_facets", {})[x["name"]] = [(v.get("rawValue"), v.get("value"), v.get("count")) for v in x.get("values", [])][:30]
    except Exception as e:
        print("tender facets ERROR", e)


CANDIDATE_FIELDS = [
    "publication-number", "notice-title", "notice-type", "publication-date", "buyer-name", "buyer-country",
    "organisation-country-buyer", "organisation-name-buyer", "buyer-city", "deadline-receipt-tender-date-lot",
    "deadline-date-lot", "classification-cpv", "main-classification-proc", "contract-nature", "contract-nature-main-proc",
    "procedure-type", "estimated-value-lot", "estimated-value-proc", "estimated-value-cur-proc", "estimated-value-glo",
    "place-of-performance", "place-of-performance-country-proc", "title-proc", "description-proc", "description-lot",
    "links", "document-url-lot", "framework-agreement-lot", "sme-lot", "official-language", "form-type", "notice-version",
]


def ted_probe():
    print("\n== TED v3 ==")
    today = date.today().strftime("%Y%m%d")
    ok = []
    for fld in CANDIDATE_FIELDS:
        s, r = ted({"query": "publication-date>=20261101", "fields": [fld], "limit": 1})
        print(f" field {fld}: {s}" + ("" if s == 200 else f" {str(r)[:200]}"))
        if s == 200:
            ok.append(fld)
        time.sleep(0.3)
    report["ted_ok_fields"] = ok
    queries = {
        "cn_deadline_future": f"notice-type IN (cn-standard cn-social cn-desg) AND deadline-receipt-tender-date-lot>={today}",
        "form_cn_deadline_future": f"form-type=competition AND deadline-receipt-tender-date-lot>={today}",
        "published_last_30d_cn": f"notice-type IN (cn-standard cn-social) AND publication-date>={(date.today()-timedelta(days=30)).strftime('%Y%m%d')}",
    }
    for label, q in queries.items():
        for scope in ("ACTIVE", "LATEST"):
            s, r = ted({"query": q, "fields": ok[:12] or ["publication-number"], "limit": 3, "scope": scope})
            tot = r.get("totalNoticeCount") if isinstance(r, dict) else None
            print(f"\n {label} scope={scope}: status={s} total={tot}")
            if s != 200:
                print("  ", str(r)[:600]); continue
            report[f"{label}_{scope}"] = {"total": tot, "sample": r.get("notices", [])[:2]}
            for n in r.get("notices", [])[:2]:
                print("  ", json.dumps(n, ensure_ascii=False)[:1500])
    # Split of active competition notices by country / nature (first 5 pages of 250)
    q = queries["cn_deadline_future"]
    fields = [f for f in ("buyer-country", "organisation-country-buyer", "contract-nature", "classification-cpv") if f in ok]
    cc, nat, cpv, n = Counter(), Counter(), Counter(), 0
    for page in range(1, 6):
        s, r = ted({"query": q, "fields": fields or ["publication-number"], "limit": 250, "page": page, "scope": "ACTIVE"})
        if s != 200:
            print(" split error", s, str(r)[:300]); break
        for x in r.get("notices", []):
            n += 1
            for k in ("buyer-country", "organisation-country-buyer"):
                v = x.get(k)
                if v: cc[(v if isinstance(v, str) else v[0])] += 1; break
            v = x.get("contract-nature")
            if v: nat[(v if isinstance(v, str) else v[0])] += 1
            v = x.get("classification-cpv")
            if v: cpv[str(v if isinstance(v, str) else v[0])[:2]] += 1
        time.sleep(0.5)
    print(f"\n split over {n} notices: countries {cc.most_common(30)}\n nature {nat.most_common()}\n cpv2 {cpv.most_common(20)}")
    report["ted_split"] = {"n": n, "countries": cc.most_common(), "nature": nat.most_common(), "cpv2": cpv.most_common()}


if __name__ == "__main__":
    for fn in (sedia, ted_probe):
        try:
            fn()
        except Exception as e:
            print(fn.__name__, "FAILED", repr(e))
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str))
    print("\nwrote", OUT)
