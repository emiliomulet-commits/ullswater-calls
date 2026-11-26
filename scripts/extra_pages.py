"""Alerts, organisation directory and Spain (BDNS) pages."""
import csv
import io
import json
import re
import time
import urllib.request
from html import escape

import ficha_widget
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
    purposes = sorted({c["purpose"] for c in calls})
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
        items.append(f'<article class="call" data-region="{escape(c["region"])}" data-purpose="{escape(c["purpose"])}" data-open="{int(c["open"])}"><div class="date{"" if c.get("end") else " tbc"}"><small>Deadline</small>'
                     + (f'<b>{c["end"][8:10].lstrip("0")}</b><i>{fmt_date(c["end"])[-8:]}</i>' if c.get("end") else "<b>TBC</b>") + '</div><div>'
                     f'<div class="meta">{st}<span class="tag">{escape(c["level"])}</span><span>{escape(c["region"])}</span><span class="code">BDNS {escape(c["id"])}</span></div>'
                     f'<h3><a href="/spain/{escape(c["id"])}/">{escape(c["title"][:220])}</a></h3>'
                     f'<p>{escape(c["body"])} · {escape(c["purpose"])}{" · " + escape(", ".join(c["beneficiaries"])) if c.get("beneficiaries") else ""}</p>'
                     f'<div class="facts">{"".join(f"<span>{d}</span>" for d in dates)}</div>'
                     f'<div class="links"><a class="more" href="{escape(c["bdns"])}" target="_blank" rel="noopener">Official record (BDNS) ↗</a>{ficha_widget.button(c["id"], c["title"], "es", "more ficha")}</div></div></article>')
    opts = "".join(f"<option>{escape(r)}</option>" for r in regions)
    popts = "".join(f"<option>{escape(r)}</option>" for r in purposes)
    return f"""<main><section class="hero"><div class="wrap"><div class="crumbs"><a href="/">All calls</a> › Spain</div><p class="kicker">Spain · national and regional calls · updated {fmt_date(data.get('updated'))}</p>
<h1>Spanish State and regional grants for companies</h1><p class="lead">Competitive calls from the State and the regions (R&amp;D&amp;I, industry &amp; energy, business and SME competitiveness, trade and tourism, agri-food and employment) that are open or about to open, for companies and organisations. Each one has a downloadable PDF factsheet in Spanish. Combine them with EU funding to build your funding strategy.</p>
<ul class="stats"><li><strong>{len(calls)}</strong>open or upcoming calls</li><li><strong>{sum(1 for c in calls if c['level'] == 'State')}</strong>State calls</li><li><strong>{len(regions)}</strong>regions</li></ul>
<div class="actions"><a class="btn" href="https://www.ullswaterinvestments.com/es/ayudas/" hreflang="es">All open grants in Spain, in Spanish →</a><a class="btn ghost" href="https://www.ullswaterinvestments.com/eu-fund-matching">Get a funding strategy (EU + Spain)</a><a class="btn ghost" href="/alerts/?q=spain">🔔 Alerts</a></div>
<p style="margin:14px 0 0;max-width:80ch">This page lists the R&amp;D, industry and competitiveness calls in English. <a href="https://www.ullswaterinvestments.com/es/ayudas/" hreflang="es" style="color:inherit;font-weight:700">Ayudas en España</a> (in Spanish) covers every State and regional grant for companies, with a search by region, a calendar of deadlines and the CDTI, ENISA and ICO programmes open all year.</p></div></section>
<div class="filters" role="search"><div class="wrap" style="grid-template-columns:2fr 1fr 1fr 1fr">
<label class="q">Search<input id="es-q" type="search" placeholder="e.g. hidrógeno, digitalización, I+D"></label>
<label>Region<select id="es-r"><option value="">All</option>{opts}</select></label>
<label>Purpose<select id="es-p"><option value="">All</option>{popts}</select></label>
<label>Status<select id="es-s"><option value="">Open + upcoming</option><option value="1">Open now</option></select></label></div></div>
<div class="wrap"><div class="resbar"><span><strong id="es-n">{len(calls)}</strong> calls</span></div>{"".join(items) or '<div class="empty">No calls right now.</div>'}
<p class="disc">Source: Sistema Nacional de Publicidad de Subvenciones y Ayudas Públicas (BDNS, IGAE), public API. Data are dynamic and may be corrected by the issuing bodies: always check the official call. Titles are shown in the original language.</p></div></main>
<script>(function(){{var q=document.getElementById('es-q'),r=document.getElementById('es-r'),pu=document.getElementById('es-p'),s=document.getElementById('es-s'),n=document.getElementById('es-n'),a=[].slice.call(document.querySelectorAll('article.call'));
function f(){{var t=q.value.toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g,''),k=0;a.forEach(function(e){{var ok=(!r.value||e.dataset.region===r.value)&&(!pu.value||e.dataset.purpose===pu.value)&&(!s.value||e.dataset.open==='1')&&(!t||e.textContent.toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').indexOf(t)>-1);e.hidden=!ok;if(ok)k++}});n.textContent=k}}
[q,r,pu,s].forEach(function(e){{e.addEventListener('input',f);e.addEventListener('change',f)}})}})();</script>"""


AYUDAS = "https://www.ullswaterinvestments.com/es/ayudas/"
_AYUDAS_IDS = None


def ayudas_ids():
    """BDNS codes that have their own page in www /es/ayudas/ (open grants), so a call page can link to it. Empty if unreachable."""
    global _AYUDAS_IDS
    if _AYUDAS_IDS is None:
        import json as _json
        import urllib.request
        try:
            req = urllib.request.Request(AYUDAS + "ayudas.json", headers={"User-Agent": "ullswater-calls-build"})
            with urllib.request.urlopen(req, timeout=30) as r:
                _AYUDAS_IDS = {str(c["id"]) for c in _json.load(r).get("calls", [])}
        except Exception as ex:  # noqa: BLE001
            print("  ayudas.json not reachable, no links to individual www grant pages:", ex)
            _AYUDAS_IDS = set()
    return _AYUDAS_IDS


def spain_call_html(c, x, money, fmt_date):
    """Page of one Spanish call (/spain/<BDNS id>/), in Spanish: the content extracted from the official text
    (visible to everyone and to search engines), pages 1-2 of the PDF factsheet and the email-verified download."""
    e = escape
    X = (x or {}).get("data") or {}
    q, pl = X.get("cuantia") or {}, X.get("plazos") or {}
    link = c.get("url") or c["bdns"]
    end = pl.get("solicitud_fin") or c.get("end")
    start = pl.get("solicitud_inicio") or c.get("start")
    budget = q.get("presupuesto_total") or c.get("budget")

    def eur(v):
        if not v:
            return ""
        return f"{v / 1e6:,.1f}".rstrip("0").rstrip(".").replace(".", ",") + " M€" if v >= 1e6 else f"{v:,.0f} €".replace(",", ".")

    def fd(iso):
        return fmt_date(iso) if iso and re.match(r"\d{4}-\d\d-\d\d$", str(iso)) else e(iso or "")

    def ul(items):
        return "<ul>" + "".join(f"<li>{e(i)}</li>" for i in items if i) + "</ul>"

    st = '<span class="tag open">Abierta</span>' if c.get("open") else '<span class="tag fc">Próximamente</span>'
    facts = []
    if end: facts.append(f"<span>Fin de solicitudes <b>{fd(end)}</b>{' · ' + e(pl['hora_fin']) if pl.get('hora_fin') else ''}</span>")
    if start and not c.get("open"): facts.append(f"<span>Apertura <b>{fd(start)}</b></span>")
    if budget: facts.append(f"<span>Presupuesto <b>{eur(budget)}</b></span>")
    if q.get("importe_maximo"): facts.append(f"<span>Ayuda máxima <b>{eur(q['importe_maximo'])}</b></span>")
    ints = [i for i in q.get("intensidad") or [] if isinstance(i.get("porcentaje"), (int, float)) and 0 < i["porcentaje"] <= 100]
    if ints:
        lo, hi = min(i["porcentaje"] for i in ints), max(i["porcentaje"] for i in ints)
        facts.append(f"<span>Intensidad <b>{lo:g}{'' if lo == hi else f'–{hi:g}'} %</b></span>")
    lead = X.get("resumen") or f"{c.get('body', '')} · {'convocatoria estatal' if c.get('level') == 'State' else 'convocatoria autonómica · ' + c.get('region', '')}."

    secs = []
    if X.get("objeto"):
        secs.append(f"<h2>Objeto de la ayuda</h2><p>{e(X['objeto'])}</p>")
    if X.get("beneficiarios"):
        secs.append("<h2>Quién puede solicitarla</h2>" + ul(X["beneficiarios"]))
    elif c.get("beneficiaries"):
        secs.append("<h2>Beneficiarios</h2>" + ul(c["beneficiaries"]))
    if X.get("actuaciones"):
        secs.append("<h2>Qué se financia</h2>" + ul(X["actuaciones"][:8]))
    if X.get("gastos"):
        secs.append("<h2>Gastos subvencionables</h2>" + ul([g.get("partida", "") + (f": {g['condiciones']}" if g.get("condiciones") else "") for g in X["gastos"][:8]]))
    rows = []
    if budget: rows.append(("Presupuesto total", eur(budget)))
    if q.get("importe_maximo"): rows.append(("Ayuda máxima", eur(q["importe_maximo"])))
    if q.get("importe_minimo"): rows.append(("Ayuda mínima", eur(q["importe_minimo"])))
    if q.get("inversion_minima"): rows.append(("Proyecto o inversión mínima", eur(q["inversion_minima"])))
    for i in ints[:4]: rows.append((f"Intensidad · {e(i.get('categoria', ''))}", f"{i['porcentaje']:g} %"))
    if start: rows.append(("Inicio de solicitudes", fd(start)))
    if end: rows.append(("Fin de solicitudes", fd(end)))
    if pl.get("ejecucion"): rows.append(("Ejecución", e(pl["ejecucion"])))
    if X.get("procedimiento"): rows.append(("Procedimiento", e(X["procedimiento"])))
    if rows:
        secs.append("<h2>Cuantía y plazos</h2><table class=\"kv\">" + "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows) + "</table>")
    if X.get("atencion"):
        secs.append("<h2>Puntos de atención</h2>" + ul(X["atencion"][:5]))
    www = (f'<a class="btn ghost" href="{AYUDAS}convocatoria/{e(c["id"])}/">Ficha completa y asistente de IA en Ayudas en España →</a> '
           if str(c["id"]) in ayudas_ids() else "")
    secs.append(f'<p style="margin-top:18px">{www}<a href="{AYUDAS}">Todas las ayudas abiertas para empresas en España</a></p>')
    src = (f'Contenido extraído por Ullswater Investments del texto oficial ({e(x.get("docName") or "convocatoria")}) publicado en la BDNS. '
           if X else "") + "Compruebe siempre los requisitos y plazos en la convocatoria oficial antes de presentar la solicitud."

    return f"""<main lang="es"><section class="hero"><div class="wrap"><div class="crumbs"><a href="/">All calls</a> › <a href="/spain/">Spain</a> › BDNS {e(c['id'])}</div>
<p class="kicker">{e(c.get('body', ''))} · {e('Estatal' if c.get('level') == 'State' else c.get('region', ''))}</p>
<div class="meta">{st}<span class="tag">{e(c.get('purpose', ''))}</span><span class="code">BDNS {e(c['id'])}</span></div>
<h1 style="margin-top:10px">{e(c['title'])}</h1><p class="lead">{e(lead)}</p>
<div class="facts">{''.join(facts)}</div>
<div class="actions"><a class="btn" href="{e(link)}" target="_blank" rel="noopener">Convocatoria oficial ↗</a><a class="btn gold" href="https://www.ullswaterinvestments.com/eu-fund-matching" target="_blank" rel="noopener">Solicitarla con nuestro apoyo</a>{ficha_widget.button(c['id'], c['title'], 'es')}<a class="btn ghost" href="{e(c['bdns'])}" target="_blank" rel="noopener">Registro BDNS ↗</a></div></div></section>
<div class="wrap">{ficha_widget.preview(c['id'], c['title'], 'es')}
<section class="sec es-call">{''.join(secs)}</section>
<p class="disc">{src}</p></div></main>
<style>.es-call ul{{margin:0 0 18px;padding-left:20px;max-width:860px}}.es-call li{{margin:4px 0}}.es-call p{{max-width:860px}}.es-call h2{{font-size:20px;margin:22px 0 8px}}
.kv{{border-collapse:collapse;margin:0 0 18px;max-width:860px;width:100%}}.kv th,.kv td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);font-size:14px;vertical-align:top}}.kv th{{color:var(--muted);font-weight:600;width:38%}}</style>"""
