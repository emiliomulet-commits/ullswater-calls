"""Per-call pages with the "Find partners" section (imported by build_site.py)."""
import json
import re
import urllib.request
from datetime import date
from html import escape

import csv
import io

BOARD_CSV = ("https://docs.google.com/spreadsheets/d/e/2PACX-1vQFlSKgfShj44obux_LhMrxiJ0KpxLOkAqqxsyEwBDv0_R2Ojf-v3dT0K4cn-Z-T1bI8V_xz1XH001c"
             "/pub?gid=0&single=true&output=csv")
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSdIi27JIDNU6-KVL4J_vJ_6rjGrtIoUJi1QDX01XgOlg-uqHw/viewform"
FORM_CALL_FIELD = "entry.301116469"
CONTACT = "eufunding@ullswaterinvestments.com"


def form_link(call_id=""):
    from urllib.parse import quote
    return f"{FORM_URL}?usp=pp_url&{FORM_CALL_FIELD}={quote(call_id)}" if call_id else FORM_URL


def load_board():
    """Approved partner requests (public fields only) from the moderation sheet's Published tab."""
    try:
        import time
        req = urllib.request.Request(f"{BOARD_CSV}&t={int(time.time())}", headers={"User-Agent": "UllswaterCallsBot/1.0"})
        text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
        rows = [r for r in csv.DictReader(io.StringIO(text)) if (r.get("id") and r.get("call") and r.get("organisation"))]
    except Exception as e:
        print(f"  partner board unavailable: {e}")
        return {}
    board = {}
    for r in rows:
        board.setdefault(r["call"].strip().upper(), []).append({k: (v or "").strip() for k, v in r.items()})
    return board


def board_cards(reqs, show_call=False, calls_by_id=None):
    out = []
    for r in reqs:
        seeking = r["kind"].lower().startswith("we are looking")
        tag = '<span class="tag open">Looking for partners</span>' if seeking else '<span class="tag fc">Wants to join a consortium</span>'
        web = r.get("website") or ""
        if web and not web.startswith("http"):
            web = "https://" + web
        org = f'<a href="{escape(web)}" target="_blank" rel="noopener nofollow">{escape(r["organisation"])}</a>' if web else escape(r["organisation"])
        call = ""
        if show_call:
            c = (calls_by_id or {}).get(r["call"].upper())
            call = (f'<p style="margin-top:4px;font-size:14px">Call: <a href="/call/{slugify(c["id"])}/">{escape(c["title"])}</a> <span class="code">{escape(c["id"])}</span></p>' if c
                    else f'<p class="code" style="margin-top:4px">Call: {escape(r["call"])}</p>')
        mail = f'mailto:{CONTACT}?subject={escape("Partner request " + r["id"] + " – " + r["call"])}'
        out.append(f'<div class="box req"><div class="meta">{tag}<span class="code">{escape(r["id"])}</span></div>'
                   f'<h3 style="margin-top:8px">{org}</h3><p><strong>{escape(r["country"])}</strong> · {escape(r["type"])} · Role: {escape(r["role"])}</p>'
                   f'{call}<p style="margin-top:8px;color:var(--ink)">{escape(r["description"])}</p>'
                   f'<a class="go" href="{mail}">Contact via Ullswater →</a></div>')
    return "".join(out)


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


TYPE_LABEL = {"HES": "University", "REC": "Research organisation", "PRC": "Company", "PUB": "Public body", "OTH": "Other"}
MIX_COLOURS = {"Company": "#233567", "Research organisation": "#c9a646", "University": "#3b6fb6", "Public body": "#067647", "Other": "#9aa3b2"}
COUNTRY = {"AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "CH": "Switzerland", "CY": "Cyprus", "CZ": "Czechia", "DE": "Germany", "DK": "Denmark",
           "EE": "Estonia", "EL": "Greece", "ES": "Spain", "FI": "Finland", "FR": "France", "HR": "Croatia", "HU": "Hungary", "IE": "Ireland", "IL": "Israel",
           "IS": "Iceland", "IT": "Italy", "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia", "MT": "Malta", "NL": "Netherlands", "NO": "Norway", "PL": "Poland",
           "PT": "Portugal", "RO": "Romania", "RS": "Serbia", "SE": "Sweden", "SI": "Slovenia", "SK": "Slovakia", "TR": "Türkiye", "UA": "Ukraine", "UK": "United Kingdom"}

# Thematic NCP-network partner search tools (checked Nov 2026)
NCP = {
    "health": ("Health NCP Net", "https://www.healthncp.net/", "Network of Health National Contact Points: partner search, brokerage events and proposal support for Cluster 1 Health and IHI."),
    "cl2": ("NCP network – Cluster 2", "https://horizoneuropencpportal.eu/cluster-2", "Partner search and brokerage for Culture, Creativity and Inclusive Society."),
    "cl3": ("SEREN – Security NCPs", "https://www.seren-project.eu/", "Security research NCP network with partner search for Cluster 3."),
    "digital": ("Ideal-ist partner search", "https://www.ideal-ist.eu/partner-search-home", "The Cluster 4 Digital NCP network's one-stop shop for digital partner searches."),
    "industry": ("NCP4Industry", "https://ncp4industry.eu/", "Industry NCP network: partner search and brokerage for Cluster 4 Industry topics."),
    "space": ("NCP Space network", "https://www.ncp-space.net/", "Space NCP network with partner search for Cluster 4 Space topics."),
    "cl5": ("GREENET Partner Tool", "https://greenet-partner-search-tool.b2match.io/", "Year-round matchmaking platform of the Cluster 5 NCP network (climate, energy, mobility)."),
    "cl6": ("NCP network – Cluster 6", "https://horizoneuropencpportal.eu/cluster-6", "Partner search and brokerage for Food, Bioeconomy, Agriculture and Environment."),
    "widera": ("NCP WIDERA.NET", "https://www.ncpwideranet.eu/", "NCP network for Widening Participation and the European Research Area."),
    "msca": ("EURAXESS Partnering", "https://euraxess.ec.europa.eu/partnering", "Find institutions for MSCA Doctoral Networks, Staff Exchanges and COFUND."),
}


def ncp_key(c):
    i = c["id"].upper()
    if re.search(r"HLTH|-CL1-|IHI|EU4H", i): return "health"
    if "-CL2-" in i: return "cl2"
    if "-CL3-" in i: return "cl3"
    if "-CL4-" in i:
        if "SPACE" in i: return "space"
        if re.search(r"DIGITAL|HUMAN|DATA|EMERGING", i): return "digital"
        return "industry"
    if re.search(r"JU-CHIPS|JU-SNS|EUROHPC|^DIGITAL", i): return "digital"
    if re.search(r"-CL5-|CBE|CETP|2ZERO|CCAM|CLEANH2", i): return "cl5"
    if re.search(r"-CL6-|CIRCBIO", i): return "cl6"
    if "WIDERA" in i: return "widera"
    if "MSCA" in i: return "msca"
    if re.search(r"-MISS-", i):
        if "CANCER" in i: return "health"
        if re.search(r"SOIL|OCEAN", i): return "cl6"
        return "cl5"
    return None


EVENT_PROG = {"health": "cluster-1", "cl2": "cluster-2", "cl3": "cluster-3", "digital": "cluster-4", "industry": "cluster-4", "space": "cluster-4",
              "cl5": "cluster-5", "cl6": "cluster-6", "widera": "widera"}


def load_events():
    try:
        req = urllib.request.Request("https://events.ullswaterinvestments.com/events.json", headers={"User-Agent": "UllswaterCallsBot/1.0"})
        return json.load(urllib.request.urlopen(req, timeout=30)).get("events", [])
    except Exception as e:  # events feed is optional
        print(f"  events feed unavailable: {e}")
        return []


def partners_enabled(c, p):
    """Track-record recommendations only where CORDIS is a meaningful reference."""
    return bool(p) and c["kind"] == "topic" and c["programme"] in {"HORIZON", "EURATOM", "DIGITAL", "EUBA"} and p.get("max_sim", 0) >= 0.10


def cordis(pid):
    return f"https://cordis.europa.eu/project/id/{pid}"


def org_table(orgs):
    rows = []
    for o in orgs:
        name = escape(o["name"].title() if o["name"].isupper() else o["name"])
        name = f'<a href="{escape(o["url"])}" target="_blank" rel="noopener nofollow">{name}</a>' if o.get("url") else name
        ex = ", ".join(f'<a href="{cordis(x["id"])}" target="_blank" rel="noopener">{escape(x["acronym"])}</a>' for x in o["projects"])
        kind = TYPE_LABEL.get(o["type"], o["type"] or "") + (" · SME" if o.get("sme") else "")
        rows.append(f'<tr><td><strong>{name}</strong><br><small>{escape(o.get("city") or "")}</small></td><td>{escape(COUNTRY.get(o["country"], o["country"] or ""))}</td>'
                    f'<td>{escape(kind)}</td><td class="n">{o["n"]}</td><td class="n">{o["coord"]}</td><td>{ex}</td></tr>')
    return ('<div class="scroll"><table class="tbl"><thead><tr><th>Organisation</th><th>Country</th><th>Type</th><th>Similar EU projects</th>'
            '<th>As coordinator</th><th>Examples (CORDIS)</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")


def archetype(a):
    mix = sorted(a["mix"].items(), key=lambda kv: -kv[1])
    bar = "".join(f'<span style="width:{v*100:.0f}%;background:{MIX_COLOURS.get(k, "#999")}"></span>' for k, v in mix)
    leg = "".join(f'<span><i style="background:{MIX_COLOURS.get(k, "#999")}"></i>{escape(k)} {v*100:.0f}%</span>' for k, v in mix)
    return (f'<ul class="kpi"><li><strong>{a["partners"]}</strong>partners (median)</li><li><strong>{a["countries"]}</strong>countries (median)</li>'
            f'<li><strong>{a["sme_share"]*100:.0f}%</strong>of partners are SMEs</li></ul>'
            f'<div class="bar" role="img" aria-label="Organisation type mix">{bar}</div><div class="legend">{leg}</div>'
            f'<p class="note" style="margin-top:8px">Based on the {a["based_on"]} funded projects closest to this call. Use it as a benchmark, not a rule: always check the call conditions for the minimum consortium.</p>')


def render_call(c, p, events, page, nav_html, fmt_date, money, label, slug, MAIN, board=None, directory=None):
    name = label(c["programme"], c["programmeName"])
    st = '<span class="tag open">Open</span>' if c["status"] == "open" else '<span class="tag fc">Forthcoming</span>'
    facts = []
    if c.get("deadline"): facts.append(f"<span>Deadline <b>{fmt_date(c['deadline'])}</b></span>")
    if c.get("opening") and c["status"] == "forthcoming": facts.append(f"<span>Opens <b>{fmt_date(c['opening'])}</b></span>")
    if c.get("budget"): facts.append(f"<span>Budget <b>{money(c['budget'])}</b></span>")
    if c.get("grants"): facts.append(f"<span>Indicative grants <b>{c['grants']}</b></span>")
    if c.get("minEU") and c.get("maxEU"):
        rng = money(c["minEU"]) if c["minEU"] == c["maxEU"] else f"{money(c['minEU'])}–{money(c['maxEU'])}"
        facts.append(f"<span>EU contribution per project <b>{rng}</b></span>")
    elif c.get("maxEU"):
        facts.append(f"<span>EU contribution per project <b>up to €{c['maxEU']/1e6:g}M</b></span>")
    if c.get("deadlineModel"): facts.append(f"<span>{escape(c['deadlineModel'].replace('-', ' ').capitalize())}</span>")
    if c.get("actions"): facts.append(f"<span>{escape(', '.join(c['actions'][:2]))}</span>")
    ident = c["id"] if c["kind"] == "topic" else c.get("call", "")
    path = f"/call/{slug(c['id'])}/"

    head = f"""<main><section class="hero callhead"><div class="wrap"><div class="crumbs"><a href="/">All calls</a> › <a href="/programme/{slug(c['programme'])}/">{escape(name)}</a> › <span class="code">{escape(ident)}</span></div>
<div class="meta">{st}<span class="tag">{escape(name)}</span>{'<span class="tag cas">Cascade funding</span>' if c['kind'] == 'cascade' else ''}</div>
<h1 style="margin-top:10px">{escape(c['title'])}</h1>{f'<p class="lead">{escape(c["summary"])}</p>' if c.get('summary') else ''}
<div class="facts">{''.join(facts)}</div>
<div class="actions"><a class="btn" href="{escape((c.get('extra') or {}).get('official_url') or c['url'])}" target="_blank" rel="noopener">Official call page ↗</a><a class="btn ghost" href="#partners">Find partners ↓</a>{'<a class="btn ghost" href="deadline.ics">📅 Add deadline to calendar</a>' if c.get('deadline') else ''}<a class="btn ghost" href="/review/?call={escape(c['id'])}">🤖 AI pre-check of my idea</a><a class="btn ghost" href="/alerts/?call={escape(ident)}">🔔 Alerts for this call</a></div></div></section>
<div class="wrap" id="partners">"""

    body = []
    reqs = (board or {}).get(c["id"].upper(), [])
    if reqs:
        body.append(f'<section class="sec"><h2>Partner requests for this call ({len(reqs)})</h2><p class="note">Published on the Ullswater partner board after review. Contact goes through Ullswater Investments, which introduces both parties.</p><div class="grid3">{board_cards(reqs)}</div></section>')
    if directory:
        import extra_pages
        body.append(f'<section class="sec"><h2>Organisations in the Ullswater directory that match this call</h2><p class="note">Reviewed profiles of organisations open to EU consortia. Ask us for an introduction.</p><div class="grid3">{"".join(extra_pages.profile_card(x) for x in directory)}</div></section>')
    show = partners_enabled(c, p)
    comp = []
    if c.get("grants"):
        comp.append(f"<li><strong>{c['grants']}</strong>grant{'s' if c['grants'] != 1 else ''} expected (official)</li>")
    if c.get("minEU") and c.get("maxEU"):
        comp.append(f"<li><strong>{money(c['minEU']) if c['minEU'] == c['maxEU'] else money(c['minEU']) + '–' + money(c['maxEU'])}</strong>EU contribution per project</li>")
    elif c.get("maxEU"):
        comp.append(f"<li><strong>up to €{c['maxEU']/1e6:g}M</strong>per project</li>")
    fnd = (p or {}).get("funding") or {}
    if show and fnd.get("median_eu"):
        comp.append(f"<li><strong>{money(fnd['median_eu'])}</strong>median EU grant of the most similar funded projects</li>")
    if show and fnd.get("family_projects"):
        comp.append(f"<li><strong>{fnd['family_projects']}</strong>projects funded in earlier topics of this programme line</li>")
    if comp:
        tip = ""
        if c.get("grants") and c["grants"] <= 2:
            tip = "<p class=\"note\">Very few grants: expect strong competition. Only proposals well above threshold are funded, so a clearly differentiated idea and a complete consortium are essential.</p>"
        body.append(f'<section class="sec"><h2>Funding and competition</h2><ul class="kpi">{"".join(comp)}</ul>{tip}<p class="note">Success rates vary widely between topics (often from below 5% to above 30%). Ask us for the success-rate history of this topic before you commit to a proposal.</p></section>')
    if show:
        body.append(f"""<section class="sec"><h2>Organisations with a track record in this topic</h2>
<p class="note">Organisations that took part in the EU-funded projects most similar to this call (Horizon Europe and Horizon 2020), ranked by how close those projects are to the call, how recent they are and whether the organisation coordinated them. Being listed does not mean an organisation is looking for partners: use the list to target your outreach.</p>
{org_table(p['orgs'][:15])}</section>""")
        if p.get("orgs_es"):
            body.append(f"""<section class="sec"><h2>Spanish organisations with experience in this field</h2>
<p class="note">The Spanish organisations that appear most often in the closest funded projects.</p>{org_table(p['orgs_es'][:8])}</section>""")
        body.append(f'<section class="sec"><h2>What a typical winning consortium looks like</h2>{archetype(p["archetype"])}</section>')
        sim = "".join(f'<li><a href="{cordis(x["id"])}" target="_blank" rel="noopener"><strong>{escape(x["acronym"])}</strong></a> – {escape(x["title"].capitalize() if x["title"].isupper() else x["title"])} <small class="code">({escape(x["fp"])} · {x["year"]} · {escape(x["topic"] or "")})</small></li>' for x in p["similar"])
        body.append(f'<section class="sec"><h2>Most similar funded projects</h2><p class="note">Read their CORDIS pages to see the full consortium, results and deliverables.</p><ul>{sim}</ul></section>')

    x = c.get("extra") or {}
    if x.get("conditions"):
        li = "".join(f"<li>{escape(t)}</li>" for t in x["conditions"])
        when = f' Deadline: <strong>{escape(x["deadline_time"])}</strong>.' if x.get("deadline_time") else ""
        body.append(f'<section class="sec"><h2>Key conditions</h2><ul>{li}</ul><p class="note">Summary by Ullswater Investments, checked on {fmt_date(x.get("source_checked", ""))} against the <a href="{escape(x.get("official_url", c["url"]))}" target="_blank" rel="noopener">official call page</a>.{when} The call text always prevails.</p></section>')
    today_ = date.today().isoformat()
    linked = any(c["id"] in (e.get("calls") or []) for e in events)
    sess = [] if linked else [s_ for s_ in x.get("sessions", []) if s_[0] >= today_]
    if sess:
        li = "".join(f'<li><strong>{fmt_date(d_)}</strong> · {escape(t_)} <small>({escape(h_)}, online)</small> – <a href="{escape(u_)}" target="_blank" rel="noopener">register ↗</a></li>' for d_, t_, h_, u_ in sess)
        body.append(f'<section class="sec"><h2>Official info sessions</h2><ul>{li}</ul></section>')
    if x.get("resources"):
        rb = "".join(f'<div class="box"><h3>{escape(t)}</h3><p>{escape(d)}</p><a class="go" href="{escape(u)}" target="_blank" rel="noopener">{escape(g)}</a></div>' for t, u, d, g in x["resources"])
        body.append(f'<section class="sec"><h2>Official resources for this call</h2><div class="grid3">{rb}</div></section>')

    k = ncp_key(c)
    boxes = [("Partner search on this topic", c["url"], "On the official topic page, open “Partner search announcements” to see organisations that have declared interest in this exact topic, or publish your own (EU Login required).", "Open the topic ↗"),
             ("EU Funding &amp; Tenders Partner Search", "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/how-to-participate/partner-search",
              "Search all organisations registered in the portal by keyword, programme, country and organisation type.", "Search organisations ↗"),
             ("Enterprise Europe Network", "https://een.ec.europa.eu/partnering-opportunities",
              "Europe's largest database of business, technology and R&amp;D cooperation requests. Filter by “Research and development request”.", "Browse requests ↗")]
    if k:
        n = NCP[k]
        boxes.insert(1, (escape(n[0]), n[1], escape(n[2]), "Open ↗"))
    live = "".join(f'<div class="box"><h3>{t}</h3><p>{d}</p><a class="go" href="{escape(u)}" target="_blank" rel="noopener">{g}</a></div>' for t, u, d, g in boxes)
    body.append(f'<section class="sec"><h2>Live partner requests</h2><p class="note">Organisations actively looking for partners publish their requests on these official platforms.</p><div class="grid3">{live}</div></section>')

    ev_key = EVENT_PROG.get(k)
    today = date.today().isoformat()
    upcoming = [e for e in events if (e.get("end") or e.get("start") or "") >= today]
    own = [e for e in upcoming if c["id"] in (e.get("calls") or [])]  # events linked to this exact call
    if own:
        li = "".join(f'<li><strong>{fmt_date(e["start"])}</strong> · <a href="{escape(e["url"])}">{escape(e["title"])}</a> <small>({escape(e.get("location") or "")})</small></li>' for e in own)
        body.append(f'<section class="sec"><h2>Events about this call</h2><ul>{li}</ul></section>')
    evs = [e for e in upcoming if e not in own and (e.get("programme") == ev_key or (c["programme"] == "HORIZON" and e.get("programme") == "horizon-europe"))][:5]
    if evs:
        li = "".join(f'<li><strong>{fmt_date(e["start"])}</strong> · <a href="{escape(e["url"])}">{escape(e["title"])}</a> <small>({escape(e.get("location") or "")})</small></li>' for e in evs)
        body.append(f'<section class="sec"><h2>Upcoming info days and brokerage events</h2><p class="note">Brokerage events are where most consortia are built.</p><ul>{li}</ul><p><a href="https://events.ullswaterinvestments.com/">All EU funding events →</a></p></section>')

    body.append(f"""<div class="cta"><div><strong>Building a consortium for this call?</strong><p>Publish what you are looking for or what you can offer on the Ullswater partner board. We review each request, publish it on this page and introduce you to suitable partners.</p></div>
<a class="btn" href="{escape(form_link(ident if c['kind'] == 'topic' else c['id']))}" target="_blank" rel="noopener">Post a partner request</a></div>""")
    if show:
        body.append('<p class="disc">Track-record data: CORDIS open data (European Commission), organisation level only, refreshed weekly. Rankings are calculated automatically by Ullswater Investments from text similarity between the call and funded projects; they are indicative.</p>')
    body.append("</div></main>")

    title = f"{c['title']} ({ident}): deadline, budget and potential partners | Ullswater Investments"
    desc = f"{name} call {ident}" + (f", deadline {fmt_date(c['deadline'])}" if c.get("deadline") else "") + ". Organisations with a track record, typical consortium and where to find partners."
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": c["title"], "url": "https://calls.ullswaterinvestments.com" + path,
          "about": {"@type": "Thing", "name": f"{ident} – {c['title']}", "url": c["url"]},
          "publisher": {"@type": "Organization", "name": "Ullswater Investments S.L.", "url": MAIN}}
    ics = None
    if c.get("deadline"):
        d = c["deadline"].replace("-", "")
        ics = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Ullswater Investments//EU Funding Calls//EN\r\nBEGIN:VEVENT\r\n"
               f"UID:{slug(c['id'])}@calls.ullswaterinvestments.com\r\nDTSTAMP:{date.today().strftime('%Y%m%d')}T000000Z\r\n"
               f"DTSTART;VALUE=DATE:{d}\r\nSUMMARY:Deadline: {ident} – {c['title'][:120].replace(',', ' ')}\r\n"
               f"DESCRIPTION:EU call deadline (check the exact time on the official page). Details and partners: https://calls.ullswaterinvestments.com{path}\r\n"
               f"URL:{c['url']}\r\nBEGIN:VALARM\r\nTRIGGER:-P14D\r\nACTION:DISPLAY\r\nDESCRIPTION:Deadline in 14 days\r\nEND:VALARM\r\n"
               "BEGIN:VALARM\r\nTRIGGER:-P3D\r\nACTION:DISPLAY\r\nDESCRIPTION:Deadline in 3 days\r\nEND:VALARM\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
    return path, ics, page(title[:150], desc[:300], path, nav_html + head + "".join(body), ld)
