#!/usr/bin/env python3
"""Fetch open and forthcoming EU funding opportunities from the European
Commission Funding & Tenders Portal (SEDIA public search API) and write
site/data/calls.json + site/data/stats.json.

Run weekly by GitHub Actions (.github/workflows/update-calls.yml).
No API key registration needed: the portal's public key "SEDIA" is used.
"""
import html
import json
import re
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.tech.ec.europa.eu/search-api/prod/rest"
KEY = "SEDIA"
OUT = Path(__file__).resolve().parent.parent / "site" / "data"
ROOT_DATA = Path(__file__).resolve().parent.parent / "data"  # build-only data, not published
STATUS = {"31094501": "forthcoming", "31094502": "open"}
PAGE_SIZE = 100
UA = "UllswaterCallsBot/1.0 (+https://calls.ullswaterinvestments.com)"


def _multipart(fields):
    b = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(
            f'--{b}\r\nContent-Disposition: form-data; name="{name}"\r\n'
            f"Content-Type: application/json\r\n\r\n{value}\r\n"
        )
    parts.append(f"--{b}--\r\n")
    return "".join(parts).encode(), f"multipart/form-data; boundary={b}"


def api(endpoint, query, page=1, size=PAGE_SIZE, retries=4):
    # A stable sort is essential: the default relevance sort is not deterministic
    # across pages and silently drops/duplicates ~10% of results.
    fields = {"query": json.dumps(query), "languages": '["en"]'}
    if endpoint == "search":
        fields["sort"] = json.dumps({"field": "ccm2Id", "order": "ASC"})
    body, ctype = _multipart(fields)
    url = f"{API}/{endpoint}?apiKey={KEY}&text=***&pageSize={size}&pageNumber={page}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": ctype, "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as e:  # network hiccup: back off and retry
            if attempt == retries - 1:
                raise
            print(f"  retry {attempt + 1}: {e}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))


def first(m, k, default=""):
    v = m.get(k) or []
    return v[0] if v else default


def strip_html(s, limit=420):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(re.sub(r"\s+", " ", s)).strip()
    s = re.sub(r"^(Expected Outcome|ExpectedOutcome)\s*:\s*", "", s, flags=re.I)
    if len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0] + "…"
    return s


def parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00").replace("+0000", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def topic_budget(m, identifier):
    """Budget, indicative number of grants and contribution range for this topic (from budgetOverview)."""
    raw = first(m, "budgetOverview")
    res = {"budget": None, "grants": None, "minEU": None, "maxEU": None}
    if not raw:
        return res
    try:
        bo = json.loads(raw)
    except ValueError:
        return res
    total, grants, mins, maxs = 0, 0, [], []
    for actions in (bo.get("budgetTopicActionMap") or {}).values():
        for a in actions:
            if identifier and str(a.get("action", "")).split(" - ")[0].strip() != identifier:
                continue
            for v in (a.get("budgetYearMap") or {}).values():
                try:
                    total += float(v)
                except (TypeError, ValueError):
                    pass
            grants += int(a.get("expectedGrants") or 0)
            if a.get("minContribution"): mins.append(float(a["minContribution"]))
            if a.get("maxContribution"): maxs.append(float(a["maxContribution"]))
    res.update(budget=int(total) or None, grants=grants or None,
               minEU=int(min(mins)) if mins else None, maxEU=int(max(maxs)) if maxs else None)
    return res


def programme_names():
    facets = api("facet", {"bool": {"must": [{"terms": {"type": ["1", "2", "8"]}}]}}, size=1)
    names = {}
    for f in facets.get("facets", []):
        if f.get("name") == "frameworkProgramme":
            for v in f.get("values", []):
                names[str(v.get("rawValue"))] = v.get("value")
    return names


def short_programme(name):
    m = re.search(r"\(([^)]+)\)\s*$", name or "")
    code = (m.group(1) if m else name or "Other").strip()
    return re.sub(r"\s+", " ", code).split(" - ")[0].strip() or "Other"


def fetch_all(types, statuses):
    q = {"bool": {"must": [{"terms": {"type": types}}, {"terms": {"status": statuses}}]}}
    first_page = api("search", q, 1)
    total = first_page.get("totalResults", 0)
    results = list(first_page.get("results", []))
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    for p in range(2, pages + 1):
        results += api("search", q, p).get("results", [])
        time.sleep(0.5)
    print(f"  types={types} statuses={statuses}: {len(results)}/{total}")
    return results


def main():
    now = datetime.now(timezone.utc)
    print("Loading programme names…")
    progs = programme_names()
    print("Fetching EU topics and cascade-funding calls…")
    raw = fetch_all(["1"], list(STATUS)) + fetch_all(["8"], list(STATUS))

    calls, seen, texts = [], set(), {}
    for r in raw:
        m = r.get("metadata", {})
        kind = "cascade" if first(m, "type") == "8" else "topic"
        status = STATUS.get(first(m, "status"))
        if not status:
            continue
        ident = first(m, "identifier")
        url = first(m, "url") or r.get("url", "")
        key = url or ident
        if key in seen:
            continue
        seen.add(key)

        deadlines = sorted(d for d in (parse_date(x) for x in m.get("deadlineDate", [])) if d)
        upcoming = [d for d in deadlines if d >= now]
        if deadlines and not upcoming:
            continue  # portal still flags it open/forthcoming but every deadline has passed
        deadline = (upcoming or deadlines or [None])[0]
        opening = parse_date(first(m, "startDate"))

        prog_full = progs.get(first(m, "frameworkProgramme"), "")
        if kind == "cascade":
            title = first(m, "caName") or first(m, "callTitle") or r.get("summary", "")
            summary = strip_html(first(m, "furtherInformation") or first(m, "description"))
            tb = {}
            budget = None
            try:
                budget = int(float(first(m, "budget"))) or None
            except ValueError:
                pass
            if budget and budget < 10000:  # some cascade calls enter budget in k€ or as a count: unreliable
                budget = None
            call_id = first(m, "projectAcronym")
        else:
            title = first(m, "title") or r.get("summary", "")
            summary = strip_html(first(m, "descriptionByte"))
            tb = topic_budget(m, ident)
            budget = tb["budget"]
            call_id = first(m, "callIdentifier")

        cid = ident if kind == "topic" else f"{call_id}-{first(m, 'ccm2Id')}"
        texts[cid] = " ".join([title, first(m, "callTitle"), " ".join(m.get("tags") or []), " ".join(m.get("keywords") or []),
                               strip_html(first(m, "descriptionByte") or first(m, "furtherInformation") or first(m, "description"), 8000)])
        calls.append({
            "id": cid,
            "title": title.strip(),
            "call": call_id,
            "callTitle": first(m, "callTitle"),
            "programme": short_programme(prog_full),
            "programmeName": prog_full or "Other",
            "kind": kind,
            "status": status,
            "opening": opening.date().isoformat() if opening else None,
            "deadline": deadline.date().isoformat() if deadline else None,
            "deadlineModel": first(m, "deadlineModel"),
            "budget": budget,
            "grants": tb.get("grants"),
            "minEU": tb.get("minEU"),
            "maxEU": tb.get("maxEU"),
            "actions": m.get("typesOfAction", [])[:3],
            "tags": (m.get("tags") or [])[:8],
            "summary": summary,
            "url": url,
        })

    calls.sort(key=lambda c: (c["status"] != "open", c["deadline"] or "9999"))
    if len([c for c in calls if c["status"] == "open"]) < 50:
        sys.exit("Sanity check failed: fewer than 50 open calls — not overwriting data.")

    OUT.mkdir(parents=True, exist_ok=True)
    open_calls = [c for c in calls if c["status"] == "open"]
    stats = {
        "updated": now.isoformat(timespec="seconds"),
        "open": len(open_calls),
        "forthcoming": len(calls) - len(open_calls),
        "total": len(calls),
        "closingIn30Days": sum(1 for c in open_calls if c["deadline"] and (datetime.fromisoformat(c["deadline"]).replace(tzinfo=timezone.utc) - now).days <= 30),
        "programmes": len({c["programme"] for c in calls}),
        "source": "European Commission – Funding & Tenders Portal (SEDIA search API)",
    }
    (OUT / "calls.json").write_text(json.dumps({"stats": stats, "calls": calls}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (ROOT_DATA).mkdir(parents=True, exist_ok=True)
    (ROOT_DATA / "topic_text.json").write_text(json.dumps({c["id"]: texts.get(c["id"], "") for c in calls}, ensure_ascii=False), encoding="utf-8")
    (OUT / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
