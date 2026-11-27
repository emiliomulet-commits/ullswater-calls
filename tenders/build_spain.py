"""Spain section of tenders.ullswaterinvestments.com: public tenders by level of government (data: fetch_spain.py, PLACSP).

Pages (EN + ES):
  /es/espana/  and /spain/                    promo block (same layout as «Ayudas España» on www), levels, regions and the finder
  /es/espana/<nivel>/  and /spain/<level>/    one page per level: Estado, comunidades autónomas, diputaciones, comarcas, ayuntamientos
  /es/espana/<comunidad>/ and /spain/<region>/ one page per autonomous community (regional and local buyers)
Also spain_band(lang): the promo block for the home of this site. Tender titles stay in Spanish (official text).
"""
import json
import re
import unicodedata
from datetime import date, timedelta
from html import escape

LEVELS = ["nacional", "autonomico", "diputacion", "comarca", "ayuntamiento", "otros"]
LV = {  # key: (EN label, ES label, EN slug, ES slug, EN short, ES short)
    "nacional": ("National (State administration)", "Estatales (Administración General del Estado)", "national", "estatales", "State", "Estatales"),
    "autonomico": ("Regional governments", "Autonómicas (comunidades autónomas)", "regional", "autonomicas", "Regional", "Autonómicas"),
    "diputacion": ("Provincial councils, cabildos and island councils", "Diputaciones, cabildos y consells insulars", "provincial", "diputaciones", "Provincial councils", "Diputaciones"),
    "comarca": ("County councils and associations of municipalities", "Consejos comarcales, comarcas y mancomunidades", "county", "comarcas", "County councils", "Comarcas"),
    "ayuntamiento": ("Town and city councils", "Ayuntamientos", "municipal", "ayuntamientos", "Town councils", "Ayuntamientos"),
    "otros": ("Other public bodies (universities, consortia, public companies)", "Otros organismos (universidades, consorcios, empresas públicas)", "other", "otros", "Other", "Otros"),
}
LV_LEAD = {
    "nacional": ("Ministries, State agencies, the Armed Forces, Adif, Aena, port authorities, river basin authorities and every other body of the State administration.",
                 "Ministerios, agencias estatales, Fuerzas Armadas, Adif, Aena, autoridades portuarias, confederaciones hidrográficas y el resto del sector público estatal."),
    "autonomico": ("Departments, health services, agencies and public companies of the 17 autonomous communities and of Ceuta and Melilla.",
                   "Consejerías, servicios de salud, agencias y empresas públicas de las 17 comunidades autónomas y de Ceuta y Melilla."),
    "diputacion": ("The 38 diputaciones provinciales and the 3 diputaciones forales, the cabildos of the Canary Islands and the consells insulars of the Balearic Islands.",
                   "Las diputaciones provinciales y forales, los cabildos insulares de Canarias y los consells insulars de Baleares, con sus organismos."),
    "comarca": ("Consells comarcals of Catalonia, comarcas of Aragón, mancomunidades and other groupings of municipalities.",
                "Consells comarcals de Cataluña, comarcas de Aragón, mancomunidades, cuadrillas y otras agrupaciones de municipios."),
    "ayuntamiento": ("Town and city councils and their municipal bodies and companies, in every province.",
                     "Ayuntamientos de toda España y sus organismos y empresas municipales."),
    "otros": ("Public universities, consortia, foundations and other public-sector bodies not attached to one level.",
              "Universidades públicas, consorcios, fundaciones y otras entidades del sector público."),
}
REGION_EN = {"Andalucía": "Andalusia", "Aragón": "Aragon", "Canarias": "Canary Islands", "Castilla y León": "Castile and León",
             "Castilla-La Mancha": "Castile-La Mancha", "Cataluña": "Catalonia", "Comunidad de Madrid": "Madrid", "Comunitat Valenciana": "Valencian Community",
             "Illes Balears": "Balearic Islands", "Navarra": "Navarre", "País Vasco": "Basque Country", "Región de Murcia": "Murcia"}
NAT = {"works": ("Works", "Obras"), "supplies": ("Supplies", "Suministros"), "services": ("Services", "Servicios"), "other": ("Other", "Otros")}
STATIC_CAP = 300

S = {
    "en": dict(
        home="/spain/", other="/es/espana/", tenders_home="/", crumbs="All tenders", h_short="Spain",
        kicker="Public tenders in Spain", new="New",
        h1="Every open public tender in Spain, from the State to your town council",
        lead=("Every day we read the Public Sector Procurement Platform (PLACSP), which also gathers the regional platforms of Catalonia, the Basque Country, "
              "Madrid, Galicia, Andalusia, Navarre and La Rioja, and publish every tender open for bids: State, regional governments, provincial councils, "
              "county councils and town councils, with deadline, buyer, value and a direct link to the official notice. Free."),
        s_open="tenders open today", s_nat="State tenders", s_aut="regional", s_loc="local (diputaciones, comarcas, ayuntamientos)", s_soon="closing in the next 7 days",
        cta="See the {n} open tenders →", cta2="By level of government", src="Source: Plataforma de Contratación del Sector Público (Ministry of Finance), incl. aggregated regional platforms · updated {d}",
        levels_h="Tenders by level of government", regions_h="Regional and local tenders by autonomous community", open_n="open",
        f_lvl="Level", f_all_lvl="All levels", f_reg="Region", f_all_reg="All of Spain", f_q="Search", f_qph="Keyword, buyer, town, CPV code, e.g. limpieza, software, Zaragoza…",
        f_nat="Contract", f_all_nat="All contracts", f_cpv="Sector (CPV)", f_all_cpv="All sectors", f_dl="Deadline", f_any="Any deadline",
        f_d=["Within 7 days", "Within 15 days", "Within 30 days"], f_val="Value", f_any_val="Any value",
        count="tenders match your filters", reset="Reset filters", more="Show more", loading="Loading tenders…",
        empty="No tenders match these filters. Try a broader keyword or another region.",
        deadline="Deadline", value="Value (excl. VAT)", portal="Official notice ↗", help="Bid with our support",
        lvl_h1="{l}: open public tenders in Spain", lvl_lead="{n} open tenders. {x} The ones closing first are listed below; use the finder for every filter.",
        reg_h1="Public tenders in {r}", reg_lead="{n} open tenders of the regional government and the local entities of {r} (diputaciones, comarcas and town councils). State tenders are listed apart.",
        open_finder="Open in the finder →", in_region="in", band_more="Every level of government",
        about_h="About this list",
        about=("Data from the open syndication service of the Plataforma de Contratación del Sector Público (Ministerio de Hacienda), which includes the contracting "
               "profiles hosted on the platform and the regional platforms that aggregate into it. Minor contracts are not included. Only tenders open for bids "
               "(status «en plazo») with a deadline still ahead are shown; the list is refreshed twice a day. The level of government is inferred from the "
               "buyer and its place in the platform's tree of contracting bodies. Always read the official notice and tender documents before bidding."),
        why_h="Bidding for Spanish public contracts with Ullswater",
        why=["<b>Bid / no-bid in 48 h.</b> We read the pliegos and tell you if it is worth bidding, what solvency you need and the risks.",
             "<b>Offer writing.</b> Technical proposal, award-criteria strategy, economic offer and the administrative envelope (DEUC, declarations).",
             "<b>UTE and subcontracting.</b> We find partners to reach the required solvency and set up joint bids."],
        title="Public tenders in Spain: {n} open tenders by level of government | Ullswater Investments",
    ),
    "es": dict(
        home="/es/espana/", other="/spain/", tenders_home="/es/", crumbs="Todas las licitaciones", h_short="España",
        kicker="Licitaciones públicas en España", new="Nuevo",
        h1="Todas las licitaciones públicas abiertas en España, del Estado a tu ayuntamiento",
        lead=("Cada día revisamos la Plataforma de Contratación del Sector Público (PLACSP), que agrega también las plataformas autonómicas de Cataluña, "
              "País Vasco, Madrid, Galicia, Andalucía, Navarra y La Rioja, y publicamos todas las licitaciones en plazo: Estado, comunidades autónomas, "
              "diputaciones, consejos comarcales y ayuntamientos, con plazo, órgano de contratación, importe y enlace directo al anuncio oficial. Gratis y en español."),
        s_open="licitaciones abiertas hoy", s_nat="licitaciones estatales", s_aut="autonómicas", s_loc="locales (diputaciones, comarcas, ayuntamientos)", s_soon="cierran en los próximos 7 días",
        cta="Ver las {n} licitaciones abiertas →", cta2="Por nivel de administración", src="Fuente: Plataforma de Contratación del Sector Público (Ministerio de Hacienda), con las plataformas autonómicas agregadas · actualizado el {d}",
        levels_h="Licitaciones por nivel de administración", regions_h="Licitaciones autonómicas y locales por comunidad autónoma", open_n="abiertas",
        f_lvl="Nivel", f_all_lvl="Todos los niveles", f_reg="Comunidad", f_all_reg="Toda España", f_q="Buscar", f_qph="Palabra clave, organismo, municipio, código CPV, p. ej. limpieza, software, Zaragoza…",
        f_nat="Contrato", f_all_nat="Todos los contratos", f_cpv="Sector (CPV)", f_all_cpv="Todos los sectores", f_dl="Plazo", f_any="Cualquier plazo",
        f_d=["En 7 días", "En 15 días", "En 30 días"], f_val="Importe", f_any_val="Cualquier importe",
        count="licitaciones con estos filtros", reset="Quitar filtros", more="Ver más", loading="Cargando licitaciones…",
        empty="Ninguna licitación con estos filtros. Prueba otra palabra u otra comunidad.",
        deadline="Plazo", value="Importe (sin IVA)", portal="Anuncio oficial ↗", help="Preséntate con nuestro apoyo",
        lvl_h1="Licitaciones {l}", lvl_lead="{n} licitaciones abiertas. {x} Abajo, las que cierran antes; usa el buscador para filtrar.",
        reg_h1="Licitaciones públicas en {r}", reg_lead="{n} licitaciones abiertas del gobierno autonómico y de las entidades locales de {r} (diputaciones, comarcas y ayuntamientos). Las del Estado se listan aparte.",
        open_finder="Abrir en el buscador →", in_region="en", band_more="Todos los niveles de la administración",
        about_h="Sobre este listado",
        about=("Datos del servicio abierto de sindicación de la Plataforma de Contratación del Sector Público (Ministerio de Hacienda), que incluye los perfiles "
               "de contratante alojados en la plataforma y las plataformas autonómicas que agregan sus datos en ella. No se incluyen contratos menores. Solo se "
               "muestran licitaciones en plazo con fecha límite por llegar; el listado se actualiza dos veces al día. El nivel de administración se deduce del "
               "órgano de contratación y de su lugar en el árbol de órganos de la plataforma. Lee siempre el anuncio oficial y los pliegos antes de presentarte."),
        why_h="Cómo te ayuda Ullswater a ganar contratos públicos en España",
        why=["<b>Decisión de presentarse en 48 h.</b> Leemos los pliegos y te decimos si merece la pena, qué solvencia necesitas y qué riesgos hay.",
             "<b>Redacción de la oferta.</b> Memoria técnica, estrategia ante los criterios de adjudicación, oferta económica y sobre administrativo (DEUC, declaraciones).",
             "<b>UTE y subcontratación.</b> Buscamos socios para alcanzar la solvencia exigida y montamos ofertas conjuntas."],
        title="Licitaciones públicas en España: {n} abiertas por nivel de administración | Ullswater Investments",
    ),
}
LVL_H1_ES = {"nacional": "estatales (Administración General del Estado)", "autonomico": "de las comunidades autónomas",
             "diputacion": "de diputaciones, cabildos y consells insulars", "comarca": "de consejos comarcales, comarcas y mancomunidades",
             "ayuntamiento": "de ayuntamientos", "otros": "de otros organismos públicos"}

CSS = """.esp{background:#fbf8f1;border-bottom:1px solid #efe6d2}.esp .wrap{padding:44px 20px 34px}
.esp-k{font-size:13px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#a8862f;margin:0 0 14px;display:flex;align-items:center;gap:10px}
.esp-new{background:var(--navy);color:#fff;border-radius:4px;padding:4px 9px;letter-spacing:.08em}
.esp-g{display:grid;grid-template-columns:1.35fr 1fr;gap:40px;align-items:center}.esp h1,.esp h2{font-size:38px;line-height:1.18;color:var(--navy);margin:0 0 16px}
.esp .sub{font-size:18px;color:var(--muted);margin:0 0 22px}.esp-st{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:14px}
.esp-st li{background:#fff;border:1px solid var(--line);border-radius:12px;padding:0}.esp-st a{display:block;padding:18px 20px;text-decoration:none;color:var(--muted);font-size:15px;line-height:1.3}
.esp-st strong{display:block;font-size:36px;line-height:1.1;color:var(--navy);margin-bottom:4px}.esp-st li.hl{border-color:#c9a646;background:#fffdf6}.esp-st li.hl strong{color:#8a6d1f}
.esp-st a:hover{box-shadow:inset 0 0 0 1px var(--navy);border-radius:12px}
.esp .actions{display:flex;gap:12px;flex-wrap:wrap}.esp .btn{padding:14px 24px;font-size:17px}.esp .btn.ghost{background:#fff}
.esp-rg{display:flex;flex-wrap:wrap;gap:10px;margin:26px 0 0}.esp-rg a{background:#fff;border:1px solid var(--line);border-radius:999px;padding:8px 15px;text-decoration:none;color:var(--navy);font-size:15px}
.esp-rg a b{margin-left:6px;color:#8a6d1f}.esp-rg a:hover{border-color:#c9a646}.esp-src{font-size:14px;color:var(--muted);margin:18px 0 0}
.esp-lv{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:6px 0 0}.esp-lv a{display:block;border:1px solid var(--line);border-radius:12px;padding:18px;background:#fff;text-decoration:none;color:var(--muted);font-size:14px}
.esp-lv a strong{display:block;font-size:30px;color:var(--navy);line-height:1.1}.esp-lv a b{display:block;color:var(--navy);font-size:16px;margin:4px 0}.esp-lv a:hover{border-color:#c9a646}
.lvtag{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;border-radius:4px;padding:3px 8px;background:#fbf3dc;color:#7a5f17}
.filters.es7 .wrap{grid-template-columns:1fr 1fr 2fr repeat(4,1fr)}@media(max-width:1100px){.filters.es7 .wrap{grid-template-columns:1fr 1fr}.filters.es7 .q{grid-column:1/-1}}
@media(max-width:900px){.esp-g{grid-template-columns:1fr;gap:26px}.esp h1,.esp h2{font-size:29px}.esp-lv{grid-template-columns:1fr 1fr}}
@media(max-width:520px){.esp-st strong{font-size:28px}.esp-lv{grid-template-columns:1fr}.esp .btn{width:100%;text-align:center}}"""


def slug(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def rname(r, lang):
    return REGION_EN.get(r, r) if lang == "en" else r


def lvl_label(k, lang, short=False):
    v = LV[k]
    return v[4 if short else 0] if lang == "en" else v[5 if short else 1]


def lvl_path(k, lang):
    return S[lang]["home"] + LV[k][2 if lang == "en" else 3] + "/"


def reg_path(r, lang):
    return S[lang]["home"] + slug(rname(r, lang) if lang == "en" else r) + "/"


def load(data_dir):
    f, s = data_dir / "es" / "spain.json", data_dir / "es" / "stats.json"
    if not f.exists() or not s.exists():
        return None, None
    return json.loads(f.read_text(encoding="utf-8")), json.loads(s.read_text(encoding="utf-8"))


def spain_band(lang, st, fdate, h="h2", crumbs=""):
    """Promo block, same layout as «Ayudas para empresas en España» on the www home."""
    if not st or not st.get("total"):
        return ""
    t = S[lang]
    lv = st["levels"]
    local = lv.get("diputacion", 0) + lv.get("comarca", 0) + lv.get("ayuntamiento", 0)
    upd = fdate(st["updated"][:10], lang)
    chips = "".join(f'<a href="{reg_path(r, lang)}">{escape(rname(r, lang))}<b>{n:,}</b></a>' for r, n in sorted(st["regions"].items(), key=lambda kv: rname(kv[0], lang)))
    return f"""<section class="esp" id="espana"><div class="wrap">{crumbs}<p class="esp-k"><span class="esp-new">{t['new']}</span>{t['kicker']}</p>
<div class="esp-g"><div><{h}>{t['h1']}</{h}><p class="sub">{t['lead']}</p>
<div class="actions"><a class="btn" href="{t['home']}#finder">{t['cta'].format(n=f"{st['total']:,}")}</a><a class="btn ghost" href="{t['home']}#niveles">{t['cta2']}</a></div></div>
<ul class="esp-st"><li><a href="{t['home']}#finder"><strong>{st['total']:,}</strong>{t['s_open']}</a></li><li><a href="{lvl_path('nacional', lang)}"><strong>{lv.get('nacional', 0):,}</strong>{t['s_nat']}</a></li>
<li><a href="{lvl_path('autonomico', lang)}"><strong>{lv.get('autonomico', 0):,}</strong>{t['s_aut']}</a></li><li><a href="{t['home']}#niveles"><strong>{local:,}</strong>{t['s_loc']}</a></li>
<li class="hl" style="grid-column:1/-1"><a href="{t['home']}?closing=7#finder"><strong>{st['closingIn7Days']:,}</strong>{t['s_soon']}</a></li></ul></div>
<nav class="esp-rg" aria-label="{t['regions_h']}">{chips}</nav><p class="esp-src">{t['src'].format(d=upd)}</p></div></section>"""


def card(x, lang, T, MON, money, cpv_label, help_url):
    t = S[lang]
    d = date.fromisoformat(x["deadline"])
    dbox = f'<div class="date{" soon" if (d - date.today()).days <= 7 else ""}"><small>{t["deadline"]}</small><b>{d.day}</b><i>{MON[lang][d.month - 1]} {d.year}</i></div>'
    facts = []
    if x.get("value"):
        facts.append(f'<span>{t["value"]} <b>{money(x["value"])}</b></span>')
    if x.get("nature"):
        facts.append(f'<span>{NAT.get(x["nature"], ("", ""))[1 if lang == "es" else 0]}</span>')
    if x.get("procedure"):
        facts.append(f'<span>{escape(x["procedure"])}</span>')
    cp = (x.get("cpv") or [""])[0]
    if cp and cpv_label(cp, lang):
        facts.append(f'<span>{escape(cpv_label(cp, lang))}</span>')
    where = ", ".join(filter(None, [x.get("city"), x.get("province") if x.get("province") != x.get("city") else "", rname(x["region"], lang) if x.get("region") and x.get("region") != x.get("province") else ""]))
    url = escape(x.get("url") or "https://contrataciondelsectorpublico.gob.es/")
    return (f'<article class="call">{dbox}<div><div class="meta"><span class="lvtag">{lvl_label(x["level"], lang, True)}</span>'
            + (f'<span class="src">{escape(where)}</span>' if where else "") + f'<span class="code">{escape(x.get("ref") or "")}</span></div>'
            f'<h3><a href="{url}" target="_blank" rel="noopener">{escape(x["title"])}</a></h3><p><b>{escape(x.get("buyer") or "")}</b></p>'
            + (f'<div class="facts">{"".join(facts)}</div>' if facts else "")
            + f'<div class="links"><a class="more" href="{url}" target="_blank" rel="noopener">{t["portal"]}</a>'
            f'<a class="more ext" href="{escape(help_url(x.get("ref") or x["id"], t["home"]))}" target="_blank" rel="noopener">{t["help"]}</a></div></div></article>')


def finder(lang, st, CPV, money, level="", region=""):
    t = S[lang]
    lv = "".join(f'<option value="{k}"{" selected" if k == level else ""}>{lvl_label(k, lang, True)} ({st["levels"].get(k, 0):,})</option>' for k in LEVELS if st["levels"].get(k))
    rg = "".join(f'<option value="{escape(r)}"{" selected" if r == region else ""}>{escape(rname(r, lang))}</option>' for r in sorted(st["regions"], key=lambda r: rname(r, lang)))
    nat = "".join(f'<option value="{k}">{v[1 if lang == "es" else 0]}</option>' for k, v in NAT.items() if k != "other")
    cpv = "".join(f'<option value="{k}">{k} · {escape(v[1 if lang == "es" else 0])}</option>' for k, v in CPV.items())
    dls = "".join(f'<option value="{d}">{lab}</option>' for d, lab in zip((7, 15, 30), t["f_d"]))
    vals = "".join(f'<option value="{v}">≥ {money(v)}</option>' for v in (15_000, 100_000, 500_000, 1_000_000, 5_000_000))
    return f"""<div class="filters es7" id="filters" role="search"><div class="wrap">
<label>{t['f_lvl']}<select id="f-lvl" data-default="{level}"><option value="">{t['f_all_lvl']}</option>{lv}</select></label>
<label>{t['f_reg']}<select id="f-reg" data-default="{escape(region)}"><option value="">{t['f_all_reg']}</option>{rg}</select></label>
<label class="q">{t['f_q']}<input id="f-q" type="search" placeholder="{escape(t['f_qph'])}" autocomplete="off"></label>
<label>{t['f_nat']}<select id="f-nat"><option value="">{t['f_all_nat']}</option>{nat}</select></label>
<label>{t['f_cpv']}<select id="f-cpv"><option value="">{t['f_all_cpv']}</option>{cpv}</select></label>
<label>{t['f_dl']}<select id="f-dl"><option value="">{t['f_any']}</option>{dls}</select></label>
<label>{t['f_val']}<select id="f-val"><option value="">{t['f_any_val']}</option>{vals}</select></label>
</div></div>
<div class="wrap" id="finder" data-lang="{lang}"><div class="resbar"><span><strong id="count">…</strong> {t['count']}</span><button class="linkbtn" id="reset" type="button">{t['reset']}</button></div>
<div id="list"><p class="empty">{t['loading']}</p></div><button class="btn ghost loadmore" id="more" type="button" hidden>{t['more']}</button>
<div class="empty" id="empty" hidden>{t['empty']}</div></div>"""


JS = r"""(function(){
var box=document.getElementById('finder');if(!box||!document.getElementById('f-lvl'))return;
var L=box.getAttribute('data-lang')||'es',T=__I18N__[L],$=function(i){return document.getElementById(i)};
var lvl=$('f-lvl'),reg=$('f-reg'),q=$('f-q'),nat=$('f-nat'),cpv=$('f-cpv'),dl=$('f-dl'),val=$('f-val'),list=$('list'),count=$('count'),more=$('more'),empty=$('empty');
var SUPPORT=__SUPPORT__,data=[],rows=[],shown=0,today=new Date();today.setHours(0,0,0,0);
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function norm(s){return (s||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'')}
function money(v){return v>=1e6?'€'+(v/1e6).toFixed(1).replace('.0','')+'M':v>=1e3?'€'+Math.round(v/1e3).toLocaleString('en')+'k':'€'+v}
function days(iso){return Math.round((new Date(iso+'T00:00:00')-today)/864e5)}
function card(x){var d=new Date(x.deadline+'T00:00:00'),n=days(x.deadline),f=[],c=(x.cpv||[])[0];
 if(x.value)f.push('<span>'+T.value+' <b>'+money(x.value)+'</b></span>');if(x.nature&&T.nat[x.nature])f.push('<span>'+T.nat[x.nature]+'</span>');if(x.procedure)f.push('<span>'+esc(x.procedure)+'</span>');
 if(c&&T.cpv[String(c).slice(0,2)])f.push('<span>'+esc(T.cpv[String(c).slice(0,2)])+'</span>');
 var where=[x.city,x.province!==x.city?x.province:'',x.region&&x.region!==x.province?(T.reg[x.region]||x.region):''].filter(Boolean).join(', '),url=esc(x.url||'https://contrataciondelsectorpublico.gob.es/');
 var help=SUPPORT.replace('CALL',encodeURIComponent('Licitación: '+(x.ref||x.id))).replace('PAGE',encodeURIComponent(location.href));
 return '<article class="call"><div class="date'+(n<=7?' soon':'')+'"><small>'+T.deadline+'</small><b>'+d.getDate()+'</b><i>'+T.mon[d.getMonth()]+' '+d.getFullYear()+'</i></div><div><div class="meta"><span class="lvtag">'+T.lvl[x.level]+'</span>'
  +(where?'<span class="src">'+esc(where)+'</span>':'')+'<span class="code">'+esc(x.ref||'')+'</span></div><h3><a href="'+url+'" target="_blank" rel="noopener">'+esc(x.title)+'</a></h3><p><b>'+esc(x.buyer)+'</b></p>'
  +(f.length?'<div class="facts">'+f.join('')+'</div>':'')+'<div class="links"><a class="more" href="'+url+'" target="_blank" rel="noopener">'+T.portal+'</a><a class="more ext" href="'+esc(help)+'" target="_blank" rel="noopener">'+T.help+'</a></div></div></article>';}
function render(r){if(r){shown=0;list.innerHTML=''}var h='';for(var i=shown;i<Math.min(rows.length,shown+50);i++)h+=card(rows[i]);list.insertAdjacentHTML('beforeend',h);shown=Math.min(rows.length,shown+50);more.hidden=shown>=rows.length}
function apply(){var w=norm(q.value).split(/\s+/).filter(Boolean),lv=lvl.value,rg=reg.value,n=nat.value,c=cpv.value,d=dl.value,v=+val.value||0;
 rows=data.filter(function(x){if(lv&&x.level!==lv)return false;if(rg&&x.region!==rg)return false;if(n&&x.nature!==n)return false;
  if(c&&!(x.cpv||[]).some(function(k){return String(k).slice(0,2)===c}))return false;if(d){var k=days(x.deadline);if(k<0||k>+d)return false}if(v&&!(x.value>=v))return false;
  if(w.length){var h=x._h||(x._h=norm([x.title,x.buyer,x.city,x.province,x.region,x.ref,(x.cpv||[]).join(' ')].join(' ')));if(!w.every(function(t){return h.indexOf(t)>-1}))return false}return true});
 count.textContent=rows.length.toLocaleString(L);empty.hidden=rows.length>0;render(true);
 var u=new URLSearchParams();if(lv!==(lvl.getAttribute('data-default')||''))u.set('level',lv);if(rg!==(reg.getAttribute('data-default')||''))u.set('region',rg);if(q.value)u.set('q',q.value);if(n)u.set('contract',n);if(c)u.set('cpv',c);if(d)u.set('closing',d);if(v)u.set('value',v);
 history.replaceState(null,'',(u.toString()?'?'+u:location.pathname)+location.hash)}
var u=new URLSearchParams(location.search);if(u.has('level'))lvl.value=u.get('level');if(u.has('region'))reg.value=u.get('region');if(u.get('q'))q.value=u.get('q');if(u.get('contract'))nat.value=u.get('contract');if(u.get('cpv'))cpv.value=u.get('cpv');if(u.get('closing'))dl.value=u.get('closing');if(u.get('value'))val.value=u.get('value');
q.addEventListener('input',apply);[lvl,reg,nat,cpv,dl,val].forEach(function(e){e.addEventListener('change',apply)});more.addEventListener('click',function(){render(false)});
$('reset').addEventListener('click',function(){lvl.value=lvl.getAttribute('data-default')||'';reg.value=reg.getAttribute('data-default')||'';q.value='';nat.value='';cpv.value='';dl.value='';val.value='';apply()});
fetch('/data/es/spain.json').then(function(r){return r.json()}).then(function(j){data=j;apply()}).catch(function(){data=[];apply()});})();"""


def js(CPV, MON, support):
    lab = {}
    for lang in ("en", "es"):
        t = S[lang]
        lab[lang] = {"deadline": t["deadline"], "value": t["value"], "portal": t["portal"], "help": t["help"], "mon": MON[lang],
                     "nat": {k: v[1 if lang == "es" else 0] for k, v in NAT.items()}, "cpv": {k: v[1 if lang == "es" else 0] for k, v in CPV.items()},
                     "lvl": {k: lvl_label(k, lang, True) for k in LEVELS}, "reg": dict(REGION_EN) if lang == "en" else {}}
    return JS.replace("__I18N__", json.dumps(lab, ensure_ascii=False)).replace("__SUPPORT__", json.dumps(support))


def build(write, page, why_box_unused, ctx):
    """ctx: T, MON, money, fdate, cpv_label, CPV, help_url, support, data_dir, site_dir. Returns stats (or None without data)."""
    recs, st = load(ctx["data_dir"])
    if not recs:
        print("Spain: no data, section skipped")
        return None
    (ctx["site_dir"] / "assets" / "spain.js").write_text(js(ctx["CPV"], ctx["MON"], ctx["support"]), encoding="utf-8")
    fdate, money = ctx["fdate"], ctx["money"]
    C = lambda x, lang: card(x, lang, ctx["T"], ctx["MON"], money, ctx["cpv_label"], ctx["help_url"])  # noqa: E731
    for lang in ("en", "es"):
        t, o = S[lang], S["es" if lang == "en" else "en"]
        upd = fdate(st["updated"][:10], lang)
        crumbs = f'<div class="crumbs"><a href="{t["tenders_home"]}">{t["crumbs"]}</a> › <a href="{t["home"]}">{t["h_short"]}</a></div>'

        def why():
            return (f'<section class="sec"><h2>{t["why_h"]}</h2><ul class="why">' + "".join(f"<li>{x}</li>" for x in t["why"]) + "</ul></section>"
                    f'<section class="about"><h2>{t["about_h"]}</h2><p>{t["about"]}</p></section>')

        def static_list(rs, finder_q):
            shown = rs[:STATIC_CAP]
            return ("".join(C(x, lang) for x in shown)
                    + (f'<p><a class="btn ghost" href="{t["home"]}?{finder_q}#finder">{t["open_finder"]}</a></p>' if len(rs) > len(shown) else ""))

        lv_tiles = "".join(f'<a href="{lvl_path(k, lang)}"><strong>{st["levels"].get(k, 0):,}</strong><b>{lvl_label(k, lang)}</b>{LV_LEAD[k][1 if lang == "es" else 0]}</a>'
                           for k in LEVELS if st["levels"].get(k))
        body = (f'<main>' + spain_band(lang, st, fdate, "h1", crumbs.replace('class="crumbs"', 'class="crumbs" style="margin-bottom:18px"'))
                + f'<div class="wrap"><section class="sec" id="niveles"><h2>{t["levels_h"]}</h2><div class="esp-lv">{lv_tiles}</div></section></div>'
                + finder(lang, st, ctx["CPV"], money) + f'<div class="wrap">{why()}</div></main>')
        ld = {"@context": "https://schema.org", "@type": "Dataset", "name": t["h1"], "description": t["lead"], "url": ctx["base"] + t["home"],
              "dateModified": st["updated"], "isBasedOn": "https://contrataciondelsectorpublico.gob.es/",
              "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": ctx["base"] + "/data/es/spain.json"}]}
        write(t["home"], page(lang, t["title"].format(n=f"{st['total']:,}"), t["lead"][:300], t["home"], body, o["home"], ld))

        for k in LEVELS:
            rs = [x for x in recs if x["level"] == k]
            if not rs:
                continue
            h1 = t["lvl_h1"].format(l=lvl_label(k, lang)) if lang == "en" else "Licitaciones " + LVL_H1_ES[k]
            lead = t["lvl_lead"].format(n=f"{len(rs):,}", x=LV_LEAD[k][1 if lang == "es" else 0])
            regs = {}
            for x in rs:
                if x.get("region"):
                    regs[x["region"]] = regs.get(x["region"], 0) + 1
            chips = ("" if k == "nacional" else '<nav class="esp-rg" style="margin:18px 0 0">' + "".join(
                f'<a href="{t["home"]}?level={k}&amp;region={escape(r)}#finder">{escape(rname(r, lang))}<b>{n:,}</b></a>' for r, n in sorted(regs.items(), key=lambda kv: rname(kv[0], lang))) + "</nav>")
            b = (f'<main><section class="hero"><div class="wrap">{crumbs}<p class="kicker">{t["kicker"]} · {upd}</p><h1>{escape(h1)}</h1><p class="lead">{lead}</p>{chips}'
                 f'<div class="actions"><a class="btn" href="{t["home"]}?level={k}#finder">{t["open_finder"]}</a></div></div></section>'
                 f'<div class="wrap"><div class="resbar"><span><strong>{len(rs):,}</strong> {t["count"]}</span></div>{static_list(rs, "level=" + k)}{why()}</div></main>')
            write(lvl_path(k, lang), page(lang, f"{h1} ({len(rs):,}) | Ullswater Investments", lead, lvl_path(k, lang), b, lvl_path(k, "es" if lang == "en" else "en")))

        for r in st["regions"]:
            rs = [x for x in recs if x.get("region") == r and x["level"] != "nacional"]
            if not rs:
                continue
            rn = rname(r, lang)
            h1, lead = t["reg_h1"].format(r=rn), t["reg_lead"].format(n=f"{len(rs):,}", r=rn)
            cnt = st["regionLevels"].get(r, {})
            chips = '<nav class="esp-rg" style="margin:18px 0 0">' + "".join(
                f'<a href="{t["home"]}?level={k}&amp;region={escape(r)}#finder">{lvl_label(k, lang, True)}<b>{cnt[k]:,}</b></a>' for k in LEVELS if cnt.get(k)) + "</nav>"
            b = (f'<main><section class="hero"><div class="wrap">{crumbs}<p class="kicker">{t["kicker"]} · {upd}</p><h1>{escape(h1)}</h1><p class="lead">{lead}</p>{chips}'
                 f'<div class="actions"><a class="btn" href="{t["home"]}?region={escape(r)}#finder">{t["open_finder"]}</a><a class="btn ghost" href="{lvl_path("nacional", lang)}">{lvl_label("nacional", lang, True)} →</a></div></div></section>'
                 f'<div class="wrap"><div class="resbar"><span><strong>{len(rs):,}</strong> {t["count"]}</span></div>{static_list(rs, "region=" + escape(r))}{why()}</div></main>')
            write(reg_path(r, lang), page(lang, f"{h1} ({len(rs):,}) | Ullswater Investments", lead, reg_path(r, lang), b, reg_path(r, "es" if lang == "en" else "en")))
    return st
