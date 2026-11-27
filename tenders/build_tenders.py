#!/usr/bin/env python3
"""Build tenders.ullswaterinvestments.com (EN + ES) from site-tenders/data/ (see fetch_tenders.py).

Same look as calls.ullswaterinvestments.com (CSS and header/footer of scripts/build_site.py).
Pages:
  /  and /es/                       Tender Finder: EU institutions + one TED country at a time, filters in the browser
  /tender/<id>/, /es/licitacion/<id>/  one page per EU-institution tender (schema.org Offer-like data, apply-with-support box)
  /country/<cc>/, /es/pais/<cc>/    one page per country: the tenders closing first (static, indexable) + link to the finder
  /closing-soon/, /es/cierran-pronto/  every tender (EU + TED) with a deadline within 15 days, statically listed (capped)
  sitemap.xml, robots.txt, llms.txt, 404.html
"""
import json
import shutil
import sys
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(HERE))
import build_site as B  # noqa: E402  (CSS, ORG_REF, OG_IMAGE)
import call_pages  # noqa: E402  (support form)
from labels import COUNTRIES, CPV, NATURE, country, country_slug, cpv_label  # noqa: E402

SITE = ROOT / "site-tenders"
DATA = SITE / "data"
BASE = "https://tenders.ullswaterinvestments.com"
MAIN = "https://www.ullswaterinvestments.com"
CALLS = "https://calls.ullswaterinvestments.com"
CHAT = '<script src="https://ullswater-ai.emilio-mulet-b52.workers.dev/widget.js" defer data-site="tenders"></script>'
STATIC_CAP = 300  # tenders listed statically on a country page; the finder shows the rest
MON = {"en": B.MONTHS, "es": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]}

T = {
    "en": dict(
        brand="EU Tenders", home="/", tender="/tender/", ctry="/country/", soon="/closing-soon/",
        kicker="EU public tenders · updated {d}", h1="Open public tenders in Europe",
        lead="Every open call for tenders of the EU institutions and agencies, plus the national, regional and local tenders of every EU country published in TED. Search by country, sector (CPV), contract type and deadline. Updated every day.",
        s_total="open tenders", s_eu="EU-institution tenders", s_ctry="countries", s_soon="closing in 30 days",
        cta1="Get help with a tender", cta2="Closing in the next 15 days",
        f_src="Where", f_q="Search", f_qph="Keyword, buyer, CPV code, e.g. software, cleaning, 72000000…", f_nat="Contract", f_all_nat="All contracts",
        f_cpv="Sector (CPV)", f_all_cpv="All sectors", f_dl="Deadline", f_any="Any deadline", f_d=["Within 7 days", "Within 15 days", "Within 30 days", "Within 60 days"],
        f_val="Value", f_any_val="Any value", count="tenders match your filters", reset="Reset filters", more="Show more",
        loading="Loading tenders…", empty="No tenders match these filters. Try a broader keyword or another country.",
        deadline="Deadline", opens="Opens", tbc="TBC", open="Open", fc="Forthcoming", value="Estimated value", lots="lots",
        details="Details →", portal="Official notice ↗", help="Apply with our support", buyer="Buyer", ref="Reference", proc="Procedure",
        cpvl="CPV", published="Published", planned="Planned launch", nature="Contract type", source="Source", summary="Description",
        b_eu="EU Funding & Tenders Portal", b_ted="TED – Tenders Electronic Daily",
        crumbs_home="All tenders", why_h="How Ullswater helps you win public contracts",
        why=["<b>Bid / no-bid in 48 h.</b> We read the tender documents and tell you if it is worth bidding, what you need and the risks.",
             "<b>Offer writing.</b> Technical proposal, award-criteria strategy, price structure and the administrative file (ESPD, declarations).",
             "<b>Consortia and subcontracting.</b> We find partners to meet the selection criteria and set up joint bids."],
        ask_ph="Ask the AI about public tenders, e.g. IT tenders in Spain closing this month…", ask_btn="Ask the AI",
        ask_q=["IT services tenders of the EU institutions", "Public tenders in Spain closing this month", "Consulting tenders in France and Belgium", "How do I bid for an EU tender?"],
        book="Book a meeting", about_h="About this list",
        about="Data from the public search services of the European Commission's Funding &amp; Tenders Portal (tenders of the EU institutions and agencies) and of TED, the Publications Office's journal of public procurement in Europe (national tenders above the EU thresholds). Only competition notices whose deadline is still ahead are shown; tenders whose deadline has passed are removed every day. Always read the official notice and tender documents before bidding.",
        ctry_h1="Public tenders in {c}", ctry_lead="{n} open public tenders from buyers in {c}, published in TED. The ones closing first are listed below; use the finder for every filter.",
        eu_h1="Tenders of the EU institutions and agencies", eu_lead="{n} open and forthcoming calls for tenders of the European Commission, the EU agencies and the other EU bodies, from the EU Funding &amp; Tenders Portal.",
        open_finder="Open in the Tender Finder →", soon_h1="Public tenders closing in the next 15 days",
        soon_lead="{n} open tenders in Europe have a deadline within 15 days.", countries_h="Tenders by country",
        calls_link="Looking for EU grants instead? See the open EU funding calls →", lang_sw='<a href="/es/" hreflang="es">ES</a>',
        nf="Page not found", nf_p="This tender may have closed. Go to the Tender Finder:",
    ),
    "es": dict(
        brand="Licitaciones UE", home="/es/", tender="/es/licitacion/", ctry="/es/pais/", soon="/es/cierran-pronto/",
        kicker="Licitaciones públicas europeas · actualizado {d}", h1="Licitaciones públicas abiertas en Europa",
        lead="Todas las licitaciones abiertas de las instituciones y agencias de la UE y las licitaciones nacionales, regionales y locales de todos los países de la UE publicadas en TED. Busca por país, sector (CPV), tipo de contrato y plazo. Se actualiza cada día.",
        s_total="licitaciones abiertas", s_eu="licitaciones de instituciones UE", s_ctry="países", s_soon="cierran en 30 días",
        cta1="Quiero ayuda con una licitación", cta2="Cierran en los próximos 15 días",
        f_src="Dónde", f_q="Buscar", f_qph="Palabra clave, organismo, código CPV, p. ej. software, limpieza, 72000000…", f_nat="Contrato", f_all_nat="Todos los contratos",
        f_cpv="Sector (CPV)", f_all_cpv="Todos los sectores", f_dl="Plazo", f_any="Cualquier plazo", f_d=["En 7 días", "En 15 días", "En 30 días", "En 60 días"],
        f_val="Importe", f_any_val="Cualquier importe", count="licitaciones con estos filtros", reset="Quitar filtros", more="Ver más",
        loading="Cargando licitaciones…", empty="Ninguna licitación con estos filtros. Prueba otra palabra u otro país.",
        deadline="Plazo", opens="Se abre", tbc="Por confirmar", open="Abierta", fc="Próxima", value="Valor estimado", lots="lotes",
        details="Ver ficha →", portal="Anuncio oficial ↗", help="Preséntate con nuestro apoyo", buyer="Órgano de contratación", ref="Referencia", proc="Procedimiento",
        cpvl="CPV", published="Publicada", planned="Lanzamiento previsto", nature="Tipo de contrato", source="Fuente", summary="Descripción",
        b_eu="Portal Funding & Tenders de la UE", b_ted="TED – Diario de licitaciones de la UE",
        crumbs_home="Todas las licitaciones", why_h="Cómo te ayuda Ullswater a ganar contratos públicos",
        why=["<b>Decisión de presentarse en 48 h.</b> Leemos los pliegos y te decimos si merece la pena, qué necesitas y qué riesgos hay.",
             "<b>Redacción de la oferta.</b> Memoria técnica, estrategia ante los criterios de adjudicación, estructura de precios y sobre administrativo (DEUC, declaraciones).",
             "<b>UTE y subcontratación.</b> Buscamos socios para cumplir la solvencia y montamos ofertas conjuntas."],
        ask_ph="Pregunta a la IA por licitaciones, p. ej. licitaciones TI en España que cierran este mes…", ask_btn="Preguntar a la IA",
        ask_q=["Licitaciones de servicios TI de las instituciones de la UE", "Licitaciones públicas en España que cierran este mes", "Licitaciones de consultoría en Francia y Bélgica", "¿Cómo me presento a una licitación de la UE?"],
        book="Reservar una reunión", about_h="Sobre este listado",
        about="Datos de los servicios públicos de búsqueda del Portal Funding &amp; Tenders de la Comisión Europea (licitaciones de las instituciones y agencias de la UE) y de TED, el diario de contratación pública europea de la Oficina de Publicaciones (licitaciones nacionales por encima de los umbrales UE). Solo se muestran anuncios de licitación con plazo abierto; los vencidos se retiran cada día. Lee siempre el anuncio oficial y los pliegos antes de presentarte.",
        ctry_h1="Licitaciones públicas en {c}", ctry_lead="{n} licitaciones públicas abiertas de organismos de {c}, publicadas en TED. Abajo, las que cierran antes; usa el buscador para filtrar.",
        eu_h1="Licitaciones de las instituciones y agencias de la UE", eu_lead="{n} licitaciones abiertas y próximas de la Comisión Europea, las agencias y los demás organismos de la UE, del Portal Funding &amp; Tenders.",
        open_finder="Abrir en el buscador →", soon_h1="Licitaciones públicas que cierran en los próximos 15 días",
        soon_lead="{n} licitaciones abiertas en Europa tienen plazo en los próximos 15 días.", countries_h="Licitaciones por país",
        calls_link="¿Buscas subvenciones de la UE? Mira las convocatorias abiertas →", lang_sw='<a href="/" hreflang="en">EN</a>',
        nf="Página no encontrada", nf_p="Puede que esta licitación haya cerrado. Ve al buscador:",
    ),
}

EXTRA_CSS = """.vh{position:absolute!important;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.ask{max-width:860px;margin:26px 0 0;display:flex;align-items:center;gap:12px;background:#fff;border-radius:40px;height:64px;padding:0 10px 0 24px;box-shadow:0 8px 28px rgba(35,53,103,.14);border:1px solid var(--line)}
.ask input{flex:1;border:0;outline:0;font:inherit;font-size:17px;color:#1f2937;background:transparent;min-width:0}.ask input::placeholder{color:#6b7280}
.ask button{flex:none;width:46px;height:46px;border-radius:50%;border:0;background:#c9a646;color:#233567;font-size:22px;font-weight:700;cursor:pointer}.ask button:hover{background:#233567;color:#fff}.ask:focus-within{box-shadow:0 0 0 3px #c9a646}
.achips{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0 6px;max-width:960px}.achip{font:inherit;font-size:14px;color:var(--navy);background:#fff;border:1px solid var(--line);border-radius:8px;padding:8px 14px;cursor:pointer}.achip:hover,.achip:focus-visible{border-color:#c9a646;background:#fffaf0}
@media(max-width:640px){.ask{height:56px;padding:0 6px 0 16px}.ask input{font-size:15px}.ask button{width:42px;height:42px}}
.src{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;border-radius:4px;padding:3px 8px;background:#eef1f8;color:var(--navy)}
.filters .wrap{grid-template-columns:1.3fr 2fr repeat(4,1fr)}@media(max-width:1000px){.filters .wrap{grid-template-columns:1fr 1fr}.filters .q{grid-column:1/-1}}
.why{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:8px 0 0;padding:0;list-style:none}.why li{border:1px solid var(--line);border-radius:10px;padding:16px;background:#fff;font-size:15px;color:var(--muted)}.why b{display:block;color:var(--navy);margin-bottom:4px}
@media(max-width:860px){.why{grid-template-columns:1fr}}.dl{display:grid;grid-template-columns:200px 1fr;gap:8px 18px;margin:18px 0;font-size:15px}.dl dt{font-weight:700;color:var(--navy)}.dl dd{margin:0;color:var(--ink)}
@media(max-width:640px){.dl{grid-template-columns:1fr}.dl dt{margin-top:6px}}.lang{margin-left:16px;font-weight:700}.loadmore{display:block;margin:10px auto 0}.loadmore[hidden]{display:none}"""


def fdate(iso, lang):
    d = date.fromisoformat(iso)
    return f"{d.day} {MON[lang][d.month - 1]} {d.year}"


def money(v, cur="EUR"):
    if not v:
        return ""
    sym = "€" if (cur or "EUR") == "EUR" else (cur + " ")
    if v >= 1_000_000:
        return f"{sym}{v / 1_000_000:.1f}M".replace(".0M", "M")
    if v >= 1000:
        return f"{sym}{round(v / 1000):,}k"
    return f"{sym}{v:,}"


def network(lang):
    t = B.TAXONOMY["network"]
    links = []
    for name, url in t:
        if name == "EU calls":
            links.append(f'<a href="{url}">{"EU calls" if lang == "en" else "Convocatorias UE"}</a>')
            links.append(f'<a href="{T[lang]["home"]}" aria-current=page>{"EU tenders" if lang == "en" else "Licitaciones UE"}</a>')
        else:
            if lang == "es" and url.startswith(MAIN):
                url = url.replace(MAIN + "/", MAIN + "/es/")
            if lang == "es":
                name = {"News": "Noticias", "Events": "Eventos", "Projects": "Proyectos", "About": "Nosotros", "Home": "Inicio"}.get(name, name)
            links.append(f'<a href="{url}">{escape(name)}</a>')
    return "".join(links)


def page(lang, title, desc, path, body, alt=None, jsonld=None):
    """alt = path of the twin page in the other language (hreflang)."""
    t = T[lang]
    canon = BASE + path
    lds = [{"@context": "https://schema.org", "@type": "WebPage", "name": title.split(" | ")[0], "url": canon, "description": desc,
            "inLanguage": lang, "publisher": B.ORG_REF,
            "isPartOf": {"@type": "WebSite", "@id": BASE + "/#website", "name": "EU Tenders · Ullswater Investments", "url": BASE + "/"}}]
    if jsonld:
        lds += jsonld if isinstance(jsonld, list) else [jsonld]
    hre = ""
    if alt:
        en, es = (path, alt) if lang == "en" else (alt, path)
        hre = (f'<link rel="alternate" hreflang="en" href="{BASE}{en}"><link rel="alternate" hreflang="es" href="{BASE}{es}">'
               f'<link rel="alternate" hreflang="x-default" href="{BASE}{en}">')
    sw = (f'<a class="lang" href="{alt}" hreflang="{"es" if lang == "en" else "en"}">{"ES" if lang == "en" else "EN"}</a>') if alt else ""
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><meta name="description" content="{escape(desc)}"><link rel="canonical" href="{canon}">{hre}
<meta property="og:type" content="website"><meta property="og:title" content="{escape(title)}"><meta property="og:description" content="{escape(desc)}"><meta property="og:url" content="{canon}"><meta property="og:site_name" content="Ullswater Investments · EU Funding Advisors">
<meta property="og:image" content="{B.OG_IMAGE}"><meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='12' fill='%23233567'/%3E%3Ctext x='32' y='44' font-family='Arial' font-weight='700' font-size='34' text-anchor='middle' fill='%23c9a646'%3EU%3C/text%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{B.CSS}{EXTRA_CSS}</style><script type="application/ld+json">{json.dumps(lds, ensure_ascii=False)}</script></head><body>
<header class="site"><div class="wrap"><a class="brand" href="{t['home']}">Ullswater Investments <span>· {t['brand']}</span></a>
<nav class="top-links" aria-label="Ullswater Investments sites">{network(lang)}{sw}</nav></div></header>
{body}
<footer class="site"><div class="wrap"><div><strong>Ullswater Investments · EU Funding Advisors</strong><br>Madrid: Calle Ramírez de Arellano 17, 28043 Madrid · Brussels: Square de Meeûs 37, 1000 Brussels</div>
<div>{"Data" if lang == "en" else "Datos"}: <a href="https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-tenders" target="_blank" rel="noopener">EU Funding &amp; Tenders Portal</a> · <a href="https://ted.europa.eu/" target="_blank" rel="noopener">TED</a> (© European Union), {"refreshed daily" if lang == "en" else "actualizado cada día"}.</div>
<div><a href="{MAIN}{'/es/' if lang == 'es' else '/'}">ullswaterinvestments.com</a> · <a href="{CALLS}/">calls.</a> · <a href="https://www.linkedin.com/company/ullswater-investments" target="_blank" rel="noopener me">LinkedIn</a> · © {date.today().year}</div></div></footer>
<script src="/assets/tenders.js" defer></script>{CHAT}</body></html>"""


def ask_bar(lang):
    """AI question bar of the home hero: opens the network assistant (widget.js, UAA.ask) with the question, like the www home."""
    t = T[lang]
    chips = "".join(f'<button type="button" class="achip" data-q="{escape(q)}">{escape(q)}</button>' for q in t["ask_q"])
    return (f'<form class="ask" id="ai-ask" role="search" action="{MAIN}{"/es/" if lang == "es" else "/"}"><label class="vh" for="ai-q">{t["ask_btn"]}</label>'
            f'<input id="ai-q" name="q" type="text" autocomplete="off" maxlength="500" placeholder="{escape(t["ask_ph"])}">'
            f'<button type="submit" aria-label="{t["ask_btn"]}">↑</button></form><div class="achips">{chips}</div>'
            "<script>(function(){function go(q,o){if(window.UAA&&window.UAA.ask){window.UAA.ask(q,o);return true}window.UAA_Q=window.UAA_Q||[];if(window.UAA_Q.push){window.UAA_Q.push([q,o]);return true}return false}"
            "var f=document.getElementById('ai-ask');f.addEventListener('submit',function(e){var i=document.getElementById('ai-q'),q=(i.value||'').trim();e.preventDefault();if(!q){i.focus();return}if(go(q,{wide:1}))i.value=''});"
            "document.querySelectorAll('.achip').forEach(function(b){b.addEventListener('click',function(){go(b.getAttribute('data-q'),{wide:1})})})})();</script>")


def help_url(ref, path):
    return call_pages.support_link(f"Tender: {ref}", BASE + path)


def why_box(lang):
    t = T[lang]
    return (f'<section class="sec"><h2>{t["why_h"]}</h2><ul class="why">' + "".join(f"<li>{x}</li>" for x in t["why"]) + "</ul>"
            f'<div class="cta"><div><strong>{"Tender Readiness" if lang == "en" else "Tender Readiness: preparación de ofertas"}</strong><p>{"Bid/no-bid, offer writing and consortium building for EU and national tenders." if lang == "en" else "Decisión, redacción de la oferta y UTE para licitaciones europeas y nacionales."}</p></div>'
            f'<a class="btn" href="{call_pages.support_link("Tender Readiness", BASE + t["home"])}" target="_blank" rel="noopener">{t["cta1"]}</a></div></section>')


def card(x, lang):
    """Static card (same markup as the one tenders.js renders)."""
    t = T[lang]
    if x.get("deadline"):
        d = date.fromisoformat(x["deadline"])
        dbox = f'<div class="date{" soon" if (d - date.today()).days <= 7 else ""}"><small>{t["deadline"]}</small><b>{d.day}</b><i>{MON[lang][d.month - 1]} {d.year}</i></div>'
    else:
        dbox = f'<div class="date tbc"><small>{t["deadline"]}</small><b>{t["tbc"]}</b></div>'
    title = (x.get("title_es") if lang == "es" else None) or x["title"]
    cp = x["cpv"][0] if isinstance(x.get("cpv"), list) and x["cpv"] else x.get("cpv") or ""
    facts = []
    if x.get("value"):
        facts.append(f'<span>{t["value"]} <b>{money(x["value"], x.get("currency"))}</b></span>')
    if x.get("nature"):
        facts.append(f'<span>{NATURE[x["nature"]][1 if lang == "es" else 0]}</span>')
    if cp and cpv_label(cp, lang):
        facts.append(f'<span>{escape(cpv_label(cp, lang))}</span>')
    if x["src"] == "eu":
        href = f'{t["tender"]}{x["id"]}/'
        links = f'<a class="more" href="{href}">{t["details"]}</a><a class="more ext" href="{escape(x["url"])}" target="_blank" rel="noopener">{t["portal"]}</a>'
    else:
        href = x["url"]
        links = (f'<a class="more" href="{escape(x["url"])}" target="_blank" rel="noopener">{t["portal"]}</a>'
                 f'<a class="more ext" href="{escape(help_url(x["id"], t["home"]))}" target="_blank" rel="noopener">{t["help"]}</a>')
    st = f'<span class="tag {"open" if x["status"] == "open" else "fc"}">{t["open"] if x["status"] == "open" else t["fc"]}</span>'
    where = country(x["country"], lang) + (f' · {escape(x["city"])}' if x.get("city") else "")
    return (f'<article class="call">{dbox}<div><div class="meta">{st}<span class="src">{escape(where)}</span><span class="code">{escape(x.get("ref") or x["id"])}</span></div>'
            f'<h3><a href="{escape(href)}"{"" if x["src"] == "eu" else " target=_blank rel=noopener"}>{escape(title)}</a></h3>'
            f'<p><b>{escape(x.get("buyer") or "")}</b>{(" — " + escape(x["summary"][:240])) if x.get("summary") else ""}</p>'
            + (f'<div class="facts">{"".join(facts)}</div>' if facts else "") + f'<div class="links">{links}</div></div></article>')


def finder(lang, stats, src="EU"):
    t = T[lang]
    opts = f'<option value="EU"{" selected" if src == "EU" else ""}>{escape(country("EU", lang))} ({stats["eu"]})</option>'
    for cc, n in sorted(stats["countries"].items(), key=lambda kv: country(kv[0], lang)):
        if cc in COUNTRIES:
            opts += f'<option value="{cc}"{" selected" if src == cc else ""}>{escape(country(cc, lang))} ({n})</option>'
    nat = "".join(f'<option value="{k}">{v[1 if lang == "es" else 0]}</option>' for k, v in NATURE.items())
    cpv = "".join(f'<option value="{k}">{k} · {escape(v[1 if lang == "es" else 0])}</option>' for k, v in CPV.items())
    dls = "".join(f'<option value="{d}">{lab}</option>' for d, lab in zip((7, 15, 30, 60), t["f_d"]))
    vals = "".join(f'<option value="{v}">≥ {money(v)}</option>' for v in (100_000, 500_000, 1_000_000, 5_000_000))
    return f"""<div class="filters" id="filters" role="search"><div class="wrap">
<label>{t['f_src']}<select id="f-src" data-default="{src}">{opts}</select></label>
<label class="q">{t['f_q']}<input id="f-q" type="search" placeholder="{escape(t['f_qph'])}" autocomplete="off"></label>
<label>{t['f_nat']}<select id="f-nat"><option value="">{t['f_all_nat']}</option>{nat}</select></label>
<label>{t['f_cpv']}<select id="f-cpv"><option value="">{t['f_all_cpv']}</option>{cpv}</select></label>
<label>{t['f_dl']}<select id="f-dl"><option value="">{t['f_any']}</option>{dls}</select></label>
<label>{t['f_val']}<select id="f-val"><option value="">{t['f_any_val']}</option>{vals}</select></label>
</div></div>
<div class="wrap" id="finder" data-lang="{lang}"><div class="resbar"><span><strong id="count">…</strong> {t['count']}</span><button class="linkbtn" id="reset" type="button">{t['reset']}</button></div>
<div id="list"><p class="empty">{t['loading']}</p></div><button class="btn ghost loadmore" id="more" type="button" hidden>{t['more']}</button>
<div class="empty" id="empty" hidden>{t['empty']}</div></div>"""


def i18n_js():
    keep = ("deadline", "tbc", "open", "fc", "value", "details", "portal", "help", "tender", "home")
    lab = {lang: {k: T[lang][k] for k in keep} for lang in T}
    for lang in T:
        lab[lang]["mon"] = MON[lang]
        lab[lang]["nat"] = {k: v[1 if lang == "es" else 0] for k, v in NATURE.items()}
        lab[lang]["cpv"] = {k: v[1 if lang == "es" else 0] for k, v in CPV.items()}
        lab[lang]["ctry"] = {k: (v[1] if lang == "es" else v[0]) for k, v in COUNTRIES.items()}
    return json.dumps(lab, ensure_ascii=False)


JS = r"""(function(){
var box=document.getElementById('finder');if(!box)return;
var L=box.getAttribute('data-lang')||'en',T=__I18N__[L],$=function(i){return document.getElementById(i)};
var src=$('f-src'),q=$('f-q'),nat=$('f-nat'),cpv=$('f-cpv'),dl=$('f-dl'),val=$('f-val'),list=$('list'),count=$('count'),more=$('more'),empty=$('empty');
var SUPPORT=__SUPPORT__,data=[],shown=0,rows=[],cache={};
var today=new Date();today.setHours(0,0,0,0);
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function norm(s){return (s||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'')}
function money(v,c){if(!v)return'';var s=(c&&c!=='EUR')?c+' ':'€';return v>=1e6?s+(v/1e6).toFixed(1).replace('.0','')+'M':v>=1e3?s+Math.round(v/1e3).toLocaleString('en')+'k':s+v}
function days(iso){return iso?Math.round((new Date(iso+'T00:00:00')-today)/864e5):null}
function card(x){var d=x.deadline?new Date(x.deadline+'T00:00:00'):null,n=days(x.deadline);
 var db=d?'<div class="date'+(n<=7?' soon':'')+'"><small>'+T.deadline+'</small><b>'+d.getDate()+'</b><i>'+T.mon[d.getMonth()]+' '+d.getFullYear()+'</i></div>':'<div class="date tbc"><small>'+T.deadline+'</small><b>'+T.tbc+'</b></div>';
 var c=Array.isArray(x.cpv)?x.cpv[0]:x.cpv,f=[];if(x.value)f.push('<span>'+T.value+' <b>'+money(x.value,x.currency)+'</b></span>');if(x.nature&&T.nat[x.nature])f.push('<span>'+T.nat[x.nature]+'</span>');
 if(c&&T.cpv[String(c).slice(0,2)])f.push('<span>'+esc(T.cpv[String(c).slice(0,2)])+'</span>');
 var title=(L==='es'&&x.title_es)||x.title,eu=x.src==='eu',href=eu?T.tender+x.id+'/':x.url,ext=eu?'':' target="_blank" rel="noopener"';
 var links=eu?'<a class="more" href="'+href+'">'+T.details+'</a><a class="more ext" href="'+esc(x.url)+'" target="_blank" rel="noopener">'+T.portal+'</a>'
  :'<a class="more" href="'+esc(x.url)+'" target="_blank" rel="noopener">'+T.portal+'</a><a class="more ext" href="'+esc(SUPPORT.replace('CALL',encodeURIComponent('Tender: '+x.id)).replace('PAGE',encodeURIComponent(location.href)))+'" target="_blank" rel="noopener">'+T.help+'</a>';
 var where=(T.ctry[x.country]||x.country)+(x.city?' · '+x.city:'');
 return '<article class="call">'+db+'<div><div class="meta"><span class="tag '+(x.status==='open'?'open">'+T.open:'fc">'+T.fc)+'</span><span class="src">'+esc(where)+'</span><span class="code">'+esc(x.ref||x.id)+'</span></div>'
  +'<h3><a href="'+esc(href)+'"'+ext+'>'+esc(title)+'</a></h3><p><b>'+esc(x.buyer)+'</b>'+(x.summary?' — '+esc(x.summary.slice(0,240)):'')+'</p>'
  +(f.length?'<div class="facts">'+f.join('')+'</div>':'')+'<div class="links">'+links+'</div></div></article>';}
function render(reset){if(reset){shown=0;list.innerHTML='';}var html='';for(var i=shown;i<Math.min(rows.length,shown+50);i++)html+=card(rows[i]);list.insertAdjacentHTML('beforeend',html);shown=Math.min(rows.length,shown+50);more.hidden=shown>=rows.length;}
function apply(){var w=norm(q.value).split(/\s+/).filter(Boolean),n=nat.value,c=cpv.value,d=dl.value,v=+val.value||0;
 rows=data.filter(function(x){if(n&&x.nature!==n)return false;var cp=[].concat(x.cpv||[]);if(c&&!cp.some(function(k){return String(k).slice(0,2)===c}))return false;
  if(d){var k=days(x.deadline);if(k===null||k<0||k>+d)return false}if(v&&!(x.value>=v))return false;
  if(w.length){var h=x._h||(x._h=norm([x.title,x.title_es,x.buyer,x.city,x.summary,x.ref,x.id,cp.join(' ')].join(' ')));if(!w.every(function(t){return h.indexOf(t)>-1}))return false}return true;});
 count.textContent=rows.length.toLocaleString(L);empty.hidden=rows.length>0;render(true);
 var u=new URLSearchParams();if(src.value!==(src.getAttribute('data-default')||'EU'))u.set('country',src.value);if(q.value)u.set('q',q.value);if(n)u.set('contract',n);if(c)u.set('cpv',c);if(d)u.set('closing',d);if(v)u.set('value',v);
 history.replaceState(null,'',u.toString()?'?'+u:location.pathname);}
function load(){var s=src.value,url=s==='EU'?'/data/eu.json':'/data/ted/'+s+'.json';
 if(cache[s]){data=cache[s];apply();return}count.textContent='…';list.innerHTML='<p class="empty">…</p>';
 fetch(url).then(function(r){return r.json()}).then(function(j){cache[s]=data=j;apply()}).catch(function(){data=[];apply()});}
var u=new URLSearchParams(location.search);if(u.get('country'))src.value=u.get('country');else if(src.getAttribute('data-default'))src.value=src.getAttribute('data-default');if(u.get('q'))q.value=u.get('q');if(u.get('contract'))nat.value=u.get('contract');if(u.get('cpv'))cpv.value=u.get('cpv');if(u.get('closing'))dl.value=u.get('closing');if(u.get('value'))val.value=u.get('value');
src.addEventListener('change',load);q.addEventListener('input',apply);[nat,cpv,dl,val].forEach(function(e){e.addEventListener('change',apply)});
more.addEventListener('click',function(){render(false)});
$('reset').addEventListener('click',function(){q.value='';nat.value='';cpv.value='';dl.value='';val.value='';apply()});
load();})();"""


def tender_page(x, lang):
    t = T[lang]
    path, alt = f'{t["tender"]}{x["id"]}/', f'{T["es" if lang == "en" else "en"]["tender"]}{x["id"]}/'
    rows = [(t["buyer"], escape(x.get("buyer") or "")), (t["ref"], f'<span class="code">{escape(x.get("ref") or x["id"])}</span>')]
    st = t["open"] if x["status"] == "open" else t["fc"]
    rows.append(("Status" if lang == "en" else "Estado", st))
    if x.get("deadline"):
        rows.append((t["deadline"], f'<b>{fdate(x["deadline"], lang)}</b>'))
    if x.get("planned"):
        rows.append((t["planned"], fdate(x["planned"], lang)))
    if x.get("published"):
        rows.append((t["published"], fdate(x["published"], lang)))
    if x.get("nature"):
        rows.append((t["nature"], NATURE[x["nature"]][1 if lang == "es" else 0]))
    if x.get("procedure"):
        rows.append((t["proc"], escape(x["procedure"])))
    if x.get("cpv"):
        rows.append((t["cpvl"], f'{escape(x["cpv"])} · {escape(cpv_label(x["cpv"], lang))}'))
    if x.get("value"):
        rows.append((t["value"], money(x["value"], x.get("currency"))))
    if x.get("lots"):
        rows.append((t["lots"].capitalize(), str(x["lots"])))
    rows.append((t["source"], f'<a href="{escape(x["url"])}" target="_blank" rel="noopener">{t["b_eu"]} ↗</a>'))
    dl = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)
    hu = help_url(x.get("ref") or x["id"], path)
    body = f"""<main><section class="hero"><div class="wrap"><div class="crumbs"><a href="{t['home']}">{t['crumbs_home']}</a> › <a href="{t['ctry']}eu/">{escape(country('EU', lang))}</a></div>
<p class="kicker">{escape(x.get('buyer') or '')}</p><h1>{escape(x['title'])}</h1>
<div class="actions"><a class="btn" href="{escape(hu)}" target="_blank" rel="noopener">{t['help']}</a><a class="btn ghost" href="{escape(x['url'])}" target="_blank" rel="noopener">{t['portal']}</a></div></div></section>
<div class="wrap"><dl class="dl">{dl}</dl>{f'<section class="sec"><h2>{t["summary"]}</h2><p>{escape(x["summary"])}</p></section>' if x.get('summary') else ''}
{why_box(lang)}<p class="disc">{t['about']}</p></div></main>"""
    desc = f'{x["title"][:120]} – {x.get("buyer") or ""}. ' + (f'{t["deadline"]}: {fdate(x["deadline"], lang)}.' if x.get("deadline") else "")
    ld = {"@context": "https://schema.org", "@type": "Demand", "name": x["title"], "description": x.get("summary") or x["title"], "url": BASE + path,
          "seeks": {"@type": "Service", "name": x["title"]}, "areaServed": "EU",
          "availabilityEnds": x.get("deadline"), "eligibleRegion": "EU", "sameAs": x["url"],
          "offeredBy": {"@type": "GovernmentOrganization", "name": x.get("buyer") or "European Union"}}
    if x.get("value"):
        ld["priceSpecification"] = {"@type": "PriceSpecification", "price": x["value"], "priceCurrency": x.get("currency") or "EUR"}
    return path, alt, page(lang, f'{x["title"][:90]} | {t["brand"]} · Ullswater', desc, path, body, alt, ld)


def list_page(lang, recs, h1, lead, path, alt, upd_s, src="EU", extra=""):
    t = T[lang]
    shown = recs[:STATIC_CAP]
    body = (f'<main><section class="hero"><div class="wrap"><div class="crumbs"><a href="{t["home"]}">{t["crumbs_home"]}</a> › {escape(h1)}</div>'
            f'<p class="kicker">{t["kicker"].format(d=upd_s)}</p><h1>{escape(h1)}</h1><p class="lead">{lead}</p>'
            f'<div class="actions"><a class="btn" href="{t["home"]}?country={src}">{t["open_finder"]}</a></div></div></section>'
            f'<div class="wrap"><div class="resbar"><span><strong>{len(recs):,}</strong> {t["count"]}</span></div>'
            + "".join(card(x, lang) for x in shown)
            + (f'<p><a class="btn ghost" href="{t["home"]}?country={src}">{t["open_finder"]}</a></p>' if len(recs) > len(shown) else "")
            + extra + why_box(lang) + "</div></main>")
    return page(lang, f"{h1} ({len(recs):,}) | {t['brand']} · Ullswater", re_text(lead), path, body, alt)


def re_text(s):
    import re
    return re.sub(r"<[^>]+>|&amp;", lambda m: "&" if m.group(0) == "&amp;" else "", s)


def main():
    stats = json.loads((DATA / "stats.json").read_text(encoding="utf-8"))
    eu = json.loads((DATA / "eu.json").read_text(encoding="utf-8"))
    upd = datetime.fromisoformat(stats["updated"]).date()
    for old in ("tender", "country", "closing-soon", "es", "assets"):
        shutil.rmtree(SITE / old, ignore_errors=True)
    (SITE / "assets").mkdir(parents=True, exist_ok=True)
    (SITE / "assets" / "tenders.js").write_text(JS.replace("__I18N__", i18n_js()).replace("__SUPPORT__", json.dumps(call_pages.SUPPORT_FORM)), encoding="utf-8")
    urls = []

    def write(path, html):
        f = SITE / path.lstrip("/") / "index.html" if path.endswith("/") else SITE / path.lstrip("/")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(html, encoding="utf-8")
        urls.append(path)

    soon15 = (upd + timedelta(days=15)).isoformat()
    soon30 = (upd + timedelta(days=30)).isoformat()
    ted_soon = []
    countries = {}
    for cc in stats["countries"]:
        f = DATA / "ted" / f"{cc}.json"
        if f.exists() and cc in COUNTRIES:
            recs = json.loads(f.read_text(encoding="utf-8"))
            countries[cc] = recs
            ted_soon += [x for x in recs if x["deadline"] <= soon15]
    ted_soon.sort(key=lambda x: x["deadline"])
    eu_soon = [x for x in eu if x.get("deadline") and x["deadline"] <= soon15]

    for lang in ("en", "es"):
        t = T[lang]
        upd_s = fdate(upd.isoformat(), lang)
        ctiles = "".join(f'<a class="tile" href="{t["ctry"]}{country_slug(cc)}/"><b>{escape(country(cc, lang))}</b><span>{len(v):,} {t["s_total"]}</span></a>'
                         for cc, v in sorted(countries.items(), key=lambda kv: -len(kv[1])))
        ctiles = f'<a class="tile" href="{t["ctry"]}eu/"><b>{escape(country("EU", lang))}</b><span>{len(eu):,} {t["s_total"]}</span></a>' + ctiles
        hero = f"""<main><section class="hero"><div class="wrap"><p class="kicker">{t['kicker'].format(d=upd_s)}</p><h1>{t['h1']}</h1><p class="lead">{t['lead']}</p>
{ask_bar(lang)}
<ul class="stats"><li><a href="#filters"><strong>{stats['total']:,}</strong>{t['s_total']}</a></li><li><a href="{t['ctry']}eu/"><strong>{stats['eu']:,}</strong>{t['s_eu']}</a></li><li><a href="#countries"><strong>{len(countries)}</strong>{t['s_ctry']}</a></li><li><a href="{t['soon']}"><strong>{stats['closingIn30Days']:,}</strong>{t['s_soon']}</a></li></ul>
<div class="actions"><a class="btn" href="{escape(call_pages.support_link('Tender Readiness', BASE + t['home']))}" target="_blank" rel="noopener">{t['cta1']}</a><a class="btn ghost" href="{t['soon']}">{t['cta2']}</a></div></div></section>"""
        tail = (f'<div class="wrap"><section class="sec" id="countries"><h2>{t["countries_h"]}</h2><div class="tiles">{ctiles}</div></section>'
                f'{why_box(lang)}<p><a href="{CALLS}/">{t["calls_link"]}</a></p><section class="about"><h2>{t["about_h"]}</h2><p>{t["about"]}</p></section></div></main>')
        title = (f"Open public tenders in Europe: {stats['total']:,} EU and national tenders | Ullswater Investments" if lang == "en"
                 else f"Licitaciones públicas abiertas en Europa: {stats['total']:,} licitaciones UE y nacionales | Ullswater Investments")
        desc = re_text(t["lead"])[:300]
        ld = {"@context": "https://schema.org", "@type": "Dataset", "name": t["h1"], "description": desc, "url": BASE + t["home"],
              "creator": B.ORG_REF, "license": "https://eur-lex.europa.eu/eli/dec/2011/833/oj", "dateModified": stats["updated"],
              "isBasedOn": ["https://ec.europa.eu/info/funding-tenders/opportunities/portal/", "https://ted.europa.eu/"],
              "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": BASE + "/data/eu.json"}]}
        write(t["home"], page(lang, title, desc, t["home"], hero + finder(lang, stats, "ESP" if lang == "es" and "ESP" in countries else "EU") + tail, T["es" if lang == "en" else "en"]["home"], ld))

        # EU institutions page + country pages
        other = T["es" if lang == "en" else "en"]
        write(f'{t["ctry"]}eu/', list_page(lang, eu, t["eu_h1"], t["eu_lead"].format(n=f"{len(eu):,}"), f'{t["ctry"]}eu/', f'{other["ctry"]}eu/', upd_s, "EU"))
        for cc, recs in countries.items():
            c = country(cc, lang)
            write(f'{t["ctry"]}{country_slug(cc)}/', list_page(lang, recs, t["ctry_h1"].format(c=c), t["ctry_lead"].format(n=f"{len(recs):,}", c=c),
                                                         f'{t["ctry"]}{country_slug(cc)}/', f'{other["ctry"]}{country_slug(cc)}/', upd_s, cc))
        soon = sorted(eu_soon + ted_soon, key=lambda x: x["deadline"])
        write(t["soon"], list_page(lang, soon, t["soon_h1"], t["soon_lead"].format(n=f"{len(soon):,}"), t["soon"], other["soon"], upd_s, "EU"))
        for x in eu:
            path, alt, html = tender_page(x, lang)
            write(path, html)
        nf = page(lang, t["nf"], t["nf"], "/404.html", f'<main><section class="hero"><div class="wrap"><h1>{t["nf"]}</h1><p class="lead">{t["nf_p"]} <a href="{t["home"]}">{t["home"]}</a></p></div></section></main>')
        if lang == "en":
            (SITE / "404.html").write_text(nf, encoding="utf-8")

    today = date.today().isoformat()
    sm = "".join(f"<url><loc>{BASE}{u}</loc><lastmod>{today}</lastmod></url>" for u in urls)
    (SITE / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>', encoding="utf-8")
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n", encoding="utf-8")
    top = ", ".join(f"{country(cc)} {n:,}" for cc, n in list(stats["countries"].items())[:12])
    (SITE / "llms.txt").write_text(
        f"# EU Tenders · Ullswater Investments\n\n> Open public tenders in Europe, updated daily ({stats['updated'][:10]}): {stats['eu']:,} tenders of the EU institutions and agencies "
        f"(EU Funding & Tenders Portal) and {stats['ted']:,} national tenders from TED. Compiled by Ullswater Investments S.L., EU funding advisors in Madrid and Brussels ({MAIN}/).\n\n"
        f"- [Tender Finder]({BASE}/) · [Spanish]({BASE}/es/)\n- [EU-institution tenders]({BASE}/country/eu/) · [JSON]({BASE}/data/eu.json)\n"
        f"- [Closing in 15 days]({BASE}/closing-soon/)\n- Countries: {top}\n- National tenders as JSON: {BASE}/data/ted/<ISO3>.json (e.g. ESP)\n"
        f"- Statistics: {BASE}/data/stats.json\n- EU grants (not tenders): {CALLS}/\n", encoding="utf-8")
    key = (ROOT / "content" / "indexnow_key.txt").read_text().strip()
    (SITE / f"{key}.txt").write_text(key, encoding="utf-8")  # IndexNow ownership file
    print(f"Built {len(urls)} pages into {SITE}")


if __name__ == "__main__":
    main()
