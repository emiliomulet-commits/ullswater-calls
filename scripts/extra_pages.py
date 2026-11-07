"""Alerts, organisation directory and Spain (BDNS) pages."""
import csv
import io
import json
import time
import urllib.request
from html import escape
from pathlib import Path

ALERTS_FORM = "https://docs.google.com/forms/d/e/1FAIpQLSfEe0ax4pkpY66jkgBnJY1SorVZBTWxsw7aibbUWG6GjGv4QA/viewform"
ALERTS_KW, ALERTS_CALL = "entry.1224081727", "entry.410356859"
DIR_FORM = "https://docs.google.com/forms/d/e/1FAIpQLSdhVyyTZ--08A5sST21GeMZCUy-uopw_7cwHMcIn_RxgnDOSQ/viewform"
DIR_CSV = ("https://docs.google.com/spreadsheets/d/e/2PACX-1vRRLgUFPUN6QApInjWwsIeMF1yO8xz43PscSfErKHsL9dtjGmF8zF_F41UOB1KUoE_uAohxvEL1IXAP"
           "/pub?gid=0&single=true&output=csv")
ROOT = Path(__file__).resolve().parent.parent


# ---------------- Alerts ----------------
def alerts_html():
    return f"""<main><section class="hero"><div class="wrap"><div class="crumbs"><a href="/">All calls</a> › Alerts</div><p class="kicker">Free weekly alerts</p>
<h1>EU funding alerts in your inbox</h1><p class="lead">Every Monday: new EU calls matching your keywords and programmes, deadlines coming up in the next three weeks, new partner requests for the calls you follow and, if you want, Spanish national and regional calls.</p>
<div class="actions"><a class="btn" id="al-go" href="{ALERTS_FORM}" target="_blank" rel="noopener">Subscribe to alerts</a></div>
<p class="note" id="al-pre" hidden style="margin-top:12px"></p></div></section>
<div class="wrap"><section class="sec"><div class="grid3">
<div class="box"><h3>1. Choose your interests</h3><p>Keywords (for example “hydrogen, digital twins”), programmes and, optionally, the calls you want to follow.</p></div>
<div class="box"><h3>2. Confirm your email</h3><p>We send you a confirmation link (double opt-in). Nothing is sent until you confirm.</p></div>
<div class="box"><h3>3. Receive one email a week</h3><p>Only when there is something relevant. Every alert includes a one-click unsubscribe link.</p></div>
</div><p class="disc">Your email and preferences are stored privately by Ullswater Investments S.L. only to send these alerts. They are never published or shared.</p></section></div></main>
<script>(function(){{var u=new URLSearchParams(location.search),q=u.get('q')||'',c=u.get('call')||'';if(!q&&!c)return;
var href='{ALERTS_FORM}?usp=pp_url'+(q?'&{ALERTS_KW}='+encodeURIComponent(q.split(/\\s+/).join(', ')):'')+(c?'&{ALERTS_CALL}='+encodeURIComponent(c):'');
document.getElementById('al-go').href=href;var p=document.getElementById('al-pre');p.hidden=false;p.textContent='Pre-filled'+(c?' with call '+c:'')+(q?' with keywords: '+q:'')+'. You can change them in the form.'}})();</script>"""


# ---------------- Directory ----------------
def load_directory():
    try:
        req = urllib.request.Request(f"{DIR_CSV}&t={int(time.time())}", headers={"User-Agent": "UllswaterCallsBot/1.0"})
        rows = list(csv.DictReader(io.StringIO(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))))
        return [{k: (v or "").strip() for k, v in r.items()} for r in rows if r.get("id") and r.get("organisation")]
    except Exception as e:
        print(f"  directory unavailable: {e}")
        return []


def match_directory(profiles, calls):
    """For each profile: best matching calls; for each call: best matching profiles (TF-IDF cosine)."""
    if not profiles:
        return {}, {}
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    texts = json.loads((ROOT / "data" / "topic_text.json").read_text(encoding="utf-8")) if (ROOT / "data" / "topic_text.json").exists() else {}
    docs = [texts.get(c["id"]) or c["title"] for c in calls]
    pdocs = [f'{p["expertise"]} {p["keywords"]} {p["keywords"]}' for p in profiles]
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True, max_df=0.5).fit(docs + pdocs)
    S = linear_kernel(vec.transform(pdocs), vec.transform(docs))
    by_profile, by_call = {}, {}
    for i, p in enumerate(profiles):
        top = [j for j in S[i].argsort()[::-1][:5] if S[i, j] > 0.05]
        by_profile[p["id"]] = [calls[j] for j in top]
        for j in top[:3]:
            by_call.setdefault(calls[j]["id"], []).append((float(S[i, j]), p))
    return by_profile, {k: [p for _, p in sorted(v, key=lambda t: -t[0])][:3] for k, v in by_call.items()}


def profile_card(p, matches=None, slugify=None):
    web = p.get("website") or ""
    if web and not web.startswith("http"):
        web = "https://" + web
    name = f'<a href="{escape(web)}" target="_blank" rel="noopener nofollow">{escape(p["organisation"])}</a>' if web else escape(p["organisation"])
    kws = "".join(f"<span>{escape(k.strip())}</span>" for k in p.get("keywords", "").split(",") if k.strip())
    m = ""
    if matches:
        m = '<p style="margin-top:8px;font-size:14px"><strong>Matching open calls:</strong> ' + ", ".join(
            f'<a href="/call/{slugify(c["id"])}/">{escape(c["id"])}</a>' for c in matches[:3]) + "</p>"
    mail = f'mailto:eufunding@ullswaterinvestments.com?subject={escape("Directory introduction " + p["id"] + " – " + p["organisation"])}'
    return (f'<div class="box"><div class="meta"><span class="tag">{escape(p["type"])}</span><span class="code">{escape(p["id"])}</span></div>'
            f'<h3 style="margin-top:8px">{name}</h3><p><strong>{escape(p["country"])}</strong> · Preferred role: {escape(p["role"])}</p>'
            f'<p style="margin-top:8px;color:var(--ink)">{escape(p["expertise"])}</p><div class="tags" style="margin-top:8px">{kws}</div>{m}'
            f'<a class="go" href="{mail}">Request an introduction →</a></div>')


def directory_html(profiles, by_profile, slugify):
    cards = "".join(profile_card(p, by_profile.get(p["id"]), slugify) for p in profiles)
    body = f'<div class="grid3">{cards}</div>' if cards else '<div class="empty">The directory is opening now. Add your organisation to be matched with new calls and consortia.</div>'
    return f"""<main><section class="hero"><div class="wrap"><div class="crumbs"><a href="/">All calls</a> › Directory</div><p class="kicker">Organisation directory</p>
<h1>Directory of organisations open to EU consortia</h1><p class="lead">Universities, research centres, companies and public bodies that want to join or lead EU projects. Each profile is reviewed by Ullswater Investments and automatically matched with open calls. Introductions go through us.</p>
<div class="actions"><a class="btn" href="{DIR_FORM}" target="_blank" rel="noopener">Add your organisation</a><a class="btn ghost" href="/partners/">Partner board</a></div></div></section>
<div class="wrap"><section class="sec">{body}</section></div></main>"""


# ---------------- Spain (BDNS) ----------------
def spain_html(data, money, fmt_date):
    calls = data.get("calls", [])
    regions = sorted({c["region"] for c in calls})
    items = []
    for c in calls:
        st = '<span class="tag open">Open</span>' if c["open"] else '<span class="tag fc">Upcoming</span>'
        dates = []
        if c.get("start") and not c["open"]: dates.append(f"Opens <b>{fmt_date(c['start'])}</b>")
        if c.get("end"): dates.append(f"Deadline <b>{fmt_date(c['end'])}</b>")
        if c.get("budget"): dates.append(f"Budget <b>{money(c['budget'])}</b>")
        if c.get("mrr"): dates.append("Recovery plan (MRR)")
        if c.get("funds"): dates.append(escape(", ".join(f.title() for f in c["funds"])))
        link = c.get("url") or c["bdns"]
        items.append(f'<article class="call" data-region="{escape(c["region"])}" data-open="{int(c["open"])}"><div class="date{"" if c.get("end") else " tbc"}"><small>Deadline</small>'
                     + (f'<b>{c["end"][8:10].lstrip("0")}</b><i>{fmt_date(c["end"])[-8:]}</i>' if c.get("end") else "<b>TBC</b>") + '</div><div>'
                     f'<div class="meta">{st}<span class="tag">{escape(c["level"])}</span><span>{escape(c["region"])}</span><span class="code">BDNS {escape(c["id"])}</span></div>'
                     f'<h3><a href="{escape(link)}" target="_blank" rel="noopener">{escape(c["title"][:220])}</a></h3>'
                     f'<p>{escape(c["body"])} · {escape(c["purpose"])}{" · " + escape(", ".join(c["beneficiaries"])) if c.get("beneficiaries") else ""}</p>'
                     f'<div class="facts">{"".join(f"<span>{d}</span>" for d in dates)}</div>'
                     f'<div class="links"><a class="more" href="{escape(c["bdns"])}" target="_blank" rel="noopener">Official record (BDNS) ↗</a></div></div></article>')
    opts = "".join(f"<option>{escape(r)}</option>" for r in regions)
    return f"""<main><section class="hero"><div class="wrap"><div class="crumbs"><a href="/">All calls</a> › Spain</div><p class="kicker">Spain · national and regional calls · updated {fmt_date(data.get('updated'))}</p>
<h1>Spanish R&amp;D, innovation and industry calls</h1><p class="lead">Competitive calls from the State and the regions (R&amp;D&amp;I and industry &amp; energy) that are open or about to open, for companies and organisations. Combine them with EU funding to build your funding strategy.</p>
<ul class="stats"><li><strong>{len(calls)}</strong>open or upcoming calls</li><li><strong>{sum(1 for c in calls if c['level'] == 'State')}</strong>State calls</li><li><strong>{len(regions)}</strong>regions</li></ul>
<div class="actions"><a class="btn" href="https://www.ullswaterinvestments.com/eu-fund-matching">Get a funding strategy (EU + Spain)</a><a class="btn ghost" href="/alerts/?q=spain">🔔 Alerts</a></div></div></section>
<div class="filters" role="search"><div class="wrap" style="grid-template-columns:2fr 1fr 1fr">
<label class="q">Search<input id="es-q" type="search" placeholder="e.g. hidrógeno, digitalización, I+D"></label>
<label>Region<select id="es-r"><option value="">All</option>{opts}</select></label>
<label>Status<select id="es-s"><option value="">Open + upcoming</option><option value="1">Open now</option></select></label></div></div>
<div class="wrap"><div class="resbar"><span><strong id="es-n">{len(calls)}</strong> calls</span></div>{"".join(items) or '<div class="empty">No calls right now.</div>'}
<p class="disc">Source: Sistema Nacional de Publicidad de Subvenciones y Ayudas Públicas (BDNS, IGAE), public API. Data are dynamic and may be corrected by the issuing bodies: always check the official call. Titles are shown in the original language.</p></div></main>
<script>(function(){{var q=document.getElementById('es-q'),r=document.getElementById('es-r'),s=document.getElementById('es-s'),n=document.getElementById('es-n'),a=[].slice.call(document.querySelectorAll('article.call'));
function f(){{var t=q.value.toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g,''),k=0;a.forEach(function(e){{var ok=(!r.value||e.dataset.region===r.value)&&(!s.value||e.dataset.open==='1')&&(!t||e.textContent.toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').indexOf(t)>-1);e.hidden=!ok;if(ok)k++}});n.textContent=k}}
[q,r,s].forEach(function(e){{e.addEventListener('input',f);e.addEventListener('change',f)}})}})();</script>"""
