"""Per-call pages with the "Find partners" section (imported by build_site.py)."""
import json
import re
import urllib.request
from datetime import date
from html import escape

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


def render_call(c, p, events, page, nav_html, fmt_date, money, label, slug, MAIN):
    name = label(c["programme"], c["programmeName"])
    st = '<span class="tag open">Open</span>' if c["status"] == "open" else '<span class="tag fc">Forthcoming</span>'
    facts = []
    if c.get("deadline"): facts.append(f"<span>Deadline <b>{fmt_date(c['deadline'])}</b></span>")
    if c.get("opening") and c["status"] == "forthcoming": facts.append(f"<span>Opens <b>{fmt_date(c['opening'])}</b></span>")
    if c.get("budget"): facts.append(f"<span>Budget <b>{money(c['budget'])}</b></span>")
    if c.get("deadlineModel"): facts.append(f"<span>{escape(c['deadlineModel'].replace('-', ' ').capitalize())}</span>")
    if c.get("actions"): facts.append(f"<span>{escape(', '.join(c['actions'][:2]))}</span>")
    ident = c["id"] if c["kind"] == "topic" else c.get("call", "")
    path = f"/call/{slug(c['id'])}/"

    head = f"""<main><section class="hero callhead"><div class="wrap"><div class="crumbs"><a href="/">All calls</a> › <a href="/programme/{slug(c['programme'])}/">{escape(name)}</a> › <span class="code">{escape(ident)}</span></div>
<div class="meta">{st}<span class="tag">{escape(name)}</span>{'<span class="tag cas">Cascade funding</span>' if c['kind'] == 'cascade' else ''}</div>
<h1 style="margin-top:10px">{escape(c['title'])}</h1>{f'<p class="lead">{escape(c["summary"])}</p>' if c.get('summary') else ''}
<div class="facts">{''.join(facts)}</div>
<div class="actions"><a class="btn" href="{escape(c['url'])}" target="_blank" rel="noopener">Official call page ↗</a><a class="btn ghost" href="#partners">Find partners ↓</a></div></div></section>
<div class="wrap" id="partners">"""

    body = []
    show = partners_enabled(c, p)
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
    evs = [e for e in events if (e.get("end") or e.get("start") or "") >= today and (e.get("programme") == ev_key or (c["programme"] == "HORIZON" and e.get("programme") == "horizon-europe"))][:5]
    if evs:
        li = "".join(f'<li><strong>{fmt_date(e["start"])}</strong> · <a href="{escape(e["url"])}">{escape(e["title"])}</a> <small>({escape(e.get("location") or "")})</small></li>' for e in evs)
        body.append(f'<section class="sec"><h2>Upcoming info days and brokerage events</h2><p class="note">Brokerage events are where most consortia are built.</p><ul>{li}</ul><p><a href="https://events.ullswaterinvestments.com/">All EU funding events →</a></p></section>')

    subj = f"Partner search – {ident}"
    bodytxt = f"Call: {c['title']} ({ident})%0D%0A%0D%0AWe are looking for / we offer:%0D%0A%0D%0AOrganisation and country:%0D%0A"
    body.append(f"""<div class="cta"><div><strong>Building a consortium for this call?</strong><p>Tell us what you are looking for or what you can offer. Ullswater Investments checks the fit, introduces you to suitable partners and can help you shape the proposal.</p></div>
<a class="btn" href="mailto:emilio.mulet@ullswaterinvestments.com?subject={escape(subj)}&amp;body={bodytxt}">Post a partner request</a></div>""")
    if show:
        body.append('<p class="disc">Track-record data: CORDIS open data (European Commission), organisation level only, refreshed weekly. Rankings are calculated automatically by Ullswater Investments from text similarity between the call and funded projects; they are indicative.</p>')
    body.append("</div></main>")

    title = f"{c['title']} ({ident}): deadline, budget and potential partners | Ullswater Investments"
    desc = f"{name} call {ident}" + (f", deadline {fmt_date(c['deadline'])}" if c.get("deadline") else "") + ". Organisations with a track record, typical consortium and where to find partners."
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": c["title"], "url": "https://calls.ullswaterinvestments.com" + path,
          "about": {"@type": "Thing", "name": f"{ident} – {c['title']}", "url": c["url"]},
          "publisher": {"@type": "Organization", "name": "Ullswater Investments S.L.", "url": MAIN}}
    return path, page(title[:150], desc[:300], path, nav_html + head + "".join(body), ld)
