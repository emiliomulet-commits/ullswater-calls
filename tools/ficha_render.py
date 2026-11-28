"""Render one tender factsheet (ficha.json, written from reading every official document) as a web page and a PDF.

python tools/ficha_render.py samples/ficha-licitacion/20957771  ->  ficha.html (self-contained) + ficha.pdf
Every fact carries its source: document + page ("ANX 13" = Anexos al PCAP, page 13), linked to the official PDF page.
"""
import json
import sys
from datetime import date
from html import escape as e
from pathlib import Path

MON = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def eur(v):
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def eur0(v):
    return f"{v:,.0f}".replace(",", ".") + " €"


def fd(iso):
    d = date.fromisoformat(iso)
    return f"{d.day} de {MON[d.month - 1]} de {d.year}"


def cites(c, docs_url, pdf=False):
    """'ANX 13 · PPT 1–3' -> source chips linked to the official PDF page."""
    out = []
    for part in [x.strip() for x in (c or "").split("·") if x.strip()]:
        k, _, pg = part.partition(" ")
        first = pg.split("–")[0].strip()
        url = docs_url.get(k, "")
        if url and first.isdigit() and not pdf:
            out.append(f'<a class="cite" href="{e(url)}#page={first}" target="_blank" rel="noopener" title="Abrir el documento oficial en la página {first}">{e(k)} p.{e(pg)}</a>')
        else:
            out.append(f'<span class="cite">{e(k)} p.{e(pg)}</span>')
    return "".join(out)


def rows(items, docs_url, pdf=False):
    return "".join(f'<div class="row"><dt>{e(k)}</dt><dd>{e(v)} {cites(c, docs_url, pdf)}</dd></div>' for k, v, c in items)


LOGO = "data:image/svg+xml;base64," + __import__("base64").b64encode((Path(__file__).resolve().parent.parent / "scripts" / "fichas_assets" / "logo_white.svg").read_bytes()).decode()


COLORS = ["#c9a227", "#4f7cff", "#22b07d", "#e46a4f", "#8b5cf6", "#0ea5e9"]
ICON = {
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    "crane": '<path d="M4 21V5h14M4 5l6 6M18 5v5M15 10h6M8 21h-4"/>',
    "alert": '<path d="M12 3 2 20h20L12 3Z"/><path d="M12 10v4M12 17h.01"/>',
}


def ic(k, s=18, c="currentColor"):
    return f'<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICON[k]}</svg>'


def num(v):
    return f"{v:,.0f}".replace(",", ".")


def body(f, idx, pdf=False, local=None, logo=True, pdf_url=None, today=None):
    """Design B («historia visual»): hero with the key figures, calendar, the 100 points as a bar, lots as tiles; detail below."""
    docs_url = {}
    by_file = {d.get("file"): d for d in idx["docs"]}
    for k, d in f["docs"].items():
        docs_url[k] = by_file.get(d.get("file"), {}).get("uri", "")
    pub, dl = date.fromisoformat(f["published"]), date.fromisoformat(f["deadline"])
    today = today or (date.fromisoformat(f["reviewed"]) if pdf else date.today())
    days = max((dl - today).days, 0)
    v = f["verdict"]
    secs = {s["key"]: s for s in f["sections"]}
    lots = secs["lots"]
    tot_fee, tot_w = sum(x["fee"] for x in lots["lots"]), sum(x.get("works") or 0 for x in lots["lots"])
    n_lots = len(lots["lots"])
    has_w = all(x.get("works") for x in lots["lots"])
    max_w = max(((x.get("works") if has_w else x["fee"]) or 1) for x in lots["lots"])
    max_lots = f.get("max_lots_per_bidder") or n_lots
    win = secs["win"]
    total_pts = sum(c["pts"] for c in win["criteria"]) or 100
    risk = secs["risk"]
    risk_html = "".join(f'<div class="rg"><h3>{e(g["h"])}</h3><dl>{rows(g["items"], docs_url, pdf)}</dl></div>' for g in risk["groups"])
    err = secs.get("errors") or {"h": "Incoherencias en los pliegos", "items": [], "advice": ""}
    judge_pts = sum(c["pts"] for c in win["criteria"] if "juicio" in (c.get("kind") or "").lower())
    auto_pts = total_pts - judge_pts
    NW = {1: "Un", 2: "Dos", 3: "Tres", 4: "Cuatro", 5: "Cinco", 6: "Seis", 7: "Siete", 8: "Ocho", 9: "Nueve", 10: "Diez"}
    nw = lambda n: NW.get(n, str(n))  # noqa: E731
    if n_lots == 1:
        lots_h, lots_sub = "Un solo lote", f"Importe sin IVA: {eur(tot_fee)}."
    else:
        lots_h = f"{nw(n_lots)} lotes" + ("" if max_lots >= n_lots else f", elige {nw(max_lots).lower()}")
        lots_sub = f"Importe sin IVA de cada lote. Total: {eur(tot_fee)}" + (f" y {f'{tot_w / 1e6:.2f}'.replace('.', ',')} M€ de obra." if has_w else ".")
    pts_sub = f.get("points_sub") or ("Sin memoria técnica ni juicio de valor: cada punto sale de una fórmula." if not judge_pts
                                      else f"{auto_pts:g} puntos salen de una fórmula y {judge_pts:g} dependen de la valoración técnica (juicio de valor).")
    crumbs = f.get("crumbs") or ("Licitaciones › España" + "".join(" › " + e(x) for x in [(f.get("tags") or {}).get("level")] if x))
    third = (f'<b>{max_lots} de {n_lots}</b><span>lotes como máximo<br>por empresa</span>' if n_lots > 1 and max_lots < n_lots
             else f'<b>{n_lots}</b><span>lotes<br>puedes ir a todos</span>' if n_lots > 1
             else f'<b>{auto_pts:g} de {total_pts:g}</b><span>puntos con<br>fórmula</span>')
    ab = {k: d.get("label", k) for k, d in f["docs"].items()}
    n_pages = sum(d.get("pages") or 0 for d in f["docs"].values())
    files = "".join(
        f'<tr><td>{e(x["name"])}</td><td>{e(x.get("type") or "")}{" · " + str(x["pages"]) + " págs." if x.get("pages") else ""}</td><td class="num">{(x.get("bytes") or 0) / 1e3:,.0f} KB</td>'
        + ("" if pdf else f'<td><a class="dl" href="{e(local(x) if local else by_file.get(x["file"], {}).get("uri", f["official_url"]))}" target="_blank" rel="noopener">Descargar</a></td>') + "</tr>"
        for x in f["files"])
    MS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    short = lambda d: f"{d.day} {MS[d.month - 1]}"  # noqa: E731
    # calendar: published -> last day for questions -> answers due -> deadline, with today's marker
    span = max((dl - pub).days, 1)
    pos = lambda d: min(max((d - pub).days / span * 100, 0), 100)  # noqa: E731
    qd = date.fromisoformat(f["questions_until"]) if f.get("questions_until") else None
    ev = [(pub, "Publicada", "first")]
    if qd:
        ev += [(qd, "Último día para preguntar", "q"), (dl - __import__("datetime").timedelta(days=6), "Respuestas a las preguntas", "")]
    ev += [(dl, "Cierre de ofertas · " + f["deadline_time"] + " h", "end")]
    marks = "".join(f'<div class="ev {c}{" past" if d < today else ""}" style="left:{pos(d):.1f}%"><i></i><b>{"Hoy, " if d == today else ""}{short(d)}</b><span>{e(t)}</span></div>' for d, t, c in ev)
    now = "" if today > dl else f'<div class="now" style="left:{pos(today):.1f}%" title="Hoy"></div>'
    cal = (f'<section class="cal"><div class="in"><h2 class="lbl">Calendario</h2><div class="track"><div class="done" style="width:{pos(today):.1f}%"></div>{now}{marks}</div>'
           f'<ol class="evl">' + "".join(f'<li class="{c}{" past" if d < today else ""}"><b>{"Hoy, " if d == today else ""}{short(d)}</b> {e(t)}</li>' for d, t, c in ev) + "</ol></div></section>")
    stack = "".join(f'<div style="width:{c["pts"] / total_pts * 100:.2f}%;background:{COLORS[i % 6]}">{c["pts"]}</div>' for i, c in enumerate(win["criteria"]))
    legend = "".join(f'<div style="border-color:{COLORS[i % 6]}"><b>{e(c["name"])} · {c["pts"]}</b><span>{e(c["how"])}</span></div>' for i, c in enumerate(win["criteria"]))
    def meta(x):
        bits = ([f'{num(x["works"])} € de obra'] if x.get("works") else []) + ([f'{x["months"]} meses'] if x.get("months") else [])
        return f'<div class="m">{ic("crane", 14) if x.get("works") else ""} {" · ".join(bits)}</div>' if bits else ""
    tiles = "".join(f'<div class="lot"><div class="lk">LOTE {e(str(x["n"]))}</div><b>{num(x["fee"])} €</b><div class="c">{e(x.get("centres") or x.get("label") or "")}</div>'
                    f'<div class="h"><i style="width:{((x.get("works") if has_w else x["fee"]) or 0) / max_w * 100:.0f}%"></i></div>{meta(x)}</div>' for x in lots["lots"])
    lvl = {"alta": "hi", "media": "mid", "baja": "lo"}
    first_err = err["items"][0] if err.get("items") else None
    btns = "" if pdf else ('<div class="cta-row"><a class="btn" href="#pregunta">Pregunta al asistente</a>'
                           + (f'<a class="btn g" href="{e(pdf_url)}" download>Descargar ficha PDF</a>' if pdf_url else "") + "</div>")
    headline = f.get("headline") or f["title"]
    hl = e(headline)
    if f.get("headline_em") and f["headline_em"] in headline:
        hl = e(headline).replace(e(f["headline_em"]), f'<em>{e(f["headline_em"])}</em>', 1)
    return f"""
<header class="hero"><div class="in hg"><div class="l">
 {'<img class="logo" src="' + LOGO + '" alt="Ullswater Investments">' if logo else ''}
 <p class="crumbs">{crumbs}</p>
 <span class="kick">{ic("target", 14)} Oportunidad {e(v['opportunity'])} · Dificultad {e(v['difficulty'])}</span>
 <h1>{hl}</h1>
 <p class="lede">{e(f.get('lede') or f['summary'][0])}</p>
 <p class="buyer">{e(f['buyer'])} · Expte. {e(f['ref'])}</p>
 {btns}
</div><div class="r">
 <div class="big gold"><b>{days} {"día" if days == 1 else "días"}</b><span>para presentar<br>{short(dl)} · {e(f['deadline_time'])} h</span></div>
 <div class="big"><b>{num(tot_fee)} €</b><span>sin IVA<br>en {n_lots} lotes</span></div>
 <div class="big last">{third}</div>
</div></div></header>
<!--ASK-->
{cal}
<main class="in">
 <section class="sec0"><h2>Así se ganan los {total_pts} puntos</h2><p class="sub">{e(pts_sub)} {cites(win['cite'], docs_url, pdf)}</p>
  <div class="stack">{stack}</div><div class="leg">{legend}</div>
  <p class="insight"><b>Dónde se decide.</b> {e(win.get('insight') or '')}</p></section>
 <section class="sec0"><h2>{lots_h}</h2><p class="sub">{e(f.get("lots_sub") or lots_sub)}</p>
  <div class="lots" style="grid-template-columns:repeat({min(max(n_lots, 1), 5)},minmax(0,1fr))">{tiles}</div><p class="note">{e(lots.get('note') or '')} {cites(lots.get('cite'), docs_url, pdf)}</p></section>
 {f'<div class="alert">{ic("alert", 26, "#e46a4f")}<div><b>Hemos encontrado {len(err["items"])} incoherencias en los pliegos.</b> {e(first_err[0])}: {e(first_err[1])} <a href="#incoherencias">Ver todas</a></div></div>' if first_err else ''}
 <section class="verd"><h2>Nuestra lectura</h2><div class="lights"><span class="lt {lvl[v['opportunity']]}">Oportunidad {e(v['opportunity'])}</span><span class="lt {lvl[v['difficulty']]}">Dificultad {e(v['difficulty'])}</span></div><p>{e(v['text'])}</p></section>
 <section><h2>{e(secs['what']['h'])}</h2><dl>{rows(secs['what']['items'], docs_url, pdf)}</dl></section>
 <section><h2>{e(secs['can']['h'])}</h2><dl>{rows(secs['can']['items'], docs_url, pdf)}</dl></section>
 <section><h2>{e(secs['money']['h'])}</h2><dl>{rows(secs['money']['items'], docs_url, pdf)}</dl></section>
 <section><h2>La letra pequeña de la puntuación</h2><dl>{rows(win['items'], docs_url, pdf)}</dl></section>
 <section><h2>{e(secs['when']['h'])}</h2><dl>{rows(secs['when']['items'], docs_url, pdf)}</dl></section>
 <section><h2>{e(risk['h'])}</h2><div class="rgs">{risk_html}</div></section>
 {f'<section class="errs" id="incoherencias"><h2>{e(err["h"])}</h2><dl>{rows(err["items"], docs_url, pdf)}</dl><p class="note">{e(err.get("advice") or "")}</p></section>' if err.get("items") else ''}
 <section><h2>Documentos oficiales</h2><p class="note">Copia de los documentos publicados en la Plataforma de Contratación del Sector Público. La versión válida es siempre la de la Plataforma.</p>
  <div class="tw"><table class="files"><thead><tr><th>Documento</th><th>Formato</th><th class="num">Tamaño</th>{'' if pdf else '<th></th>'}</tr></thead><tbody>{files}</tbody></table></div>
  <p class="note">Anuncio, pliegos y rectificaciones en la <a href="{e(f['official_url'])}" target="_blank" rel="noopener">ficha oficial de la licitación</a>.</p></section>
 <section class="cta"><h2>¿Te presentas?</h2><p>Hacemos gratis un primer diagnóstico de esta licitación con tu empresa: si cumples la solvencia, qué puntuación puedes esperar y qué precio te deja opciones. Después, si quieres, un consultor te ayuda a preparar la oferta.</p>
  <p><a class="btn" href="https://www.ullswaterinvestments.com/es/contacto/" target="_blank" rel="noopener">Pedir diagnóstico gratuito</a></p></section>
 <p class="disc">Resumen elaborado con IA a partir de los {len(f['docs'])} documentos principales del expediente{f" ({n_pages} páginas)" if n_pages else ""}. Revisado el {fd(f['reviewed'])}. Prevalecen siempre los pliegos y el anuncio oficial. Cada dato indica el documento y la página de donde sale: {e("; ".join(f"{k} = {v}" for k, v in ab.items()))}.</p>
</main>"""


CSS = """
:root{--navy:#233567;--navy2:#1a2850;--gold:#c9a646;--ink:#1f2937;--muted:#5b6475;--line:#e3e6ec;--bg:#ffffff;--soft:#f4f6f9;--chip:#eef1f7;
 --hi:#1f7a4d;--hi-bg:#e4f4ea;--mid:#9a6a00;--mid-bg:#fbf1d9;--lo:#b42318;--lo-bg:#fde8e6;--sans:Inter,system-ui,-apple-system,"Segoe UI",sans-serif}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--ink:#e7eaf0;--muted:#a3abba;--line:#2c3446;--bg:#12161f;--soft:#1a2030;--chip:#232b3d;
 --hi:#6fd39d;--hi-bg:#143324;--mid:#e9c15a;--mid-bg:#3a2e10;--lo:#ff8f85;--lo-bg:#3d1714;color-scheme:dark}}
:root[data-theme="dark"]{--ink:#e7eaf0;--muted:#a3abba;--line:#2c3446;--bg:#12161f;--soft:#1a2030;--chip:#232b3d;
 --hi:#6fd39d;--hi-bg:#143324;--mid:#e9c15a;--mid-bg:#3a2e10;--lo:#ff8f85;--lo-bg:#3d1714;color-scheme:dark}
body{background:var(--bg);color:var(--ink);font:15px/1.55 var(--sans);margin:0}
.in{max-width:1040px;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.hero{background:var(--navy);color:#fff;margin-top:calc(-1*env(safe-area-inset-top,0px));padding-top:calc(env(safe-area-inset-top,0px) + 28px);padding-bottom:30px}
.logo{height:30px;width:auto;display:block;margin-bottom:14px}.crumbs{font-size:13px;color:#c8cfe0;margin:0 0 14px}.kicker{color:var(--gold);font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;margin:0 0 6px}
h1{font-size:clamp(22px,3.2vw,32px);line-height:1.2;margin:0 0 10px;text-wrap:balance;font-weight:800;max-width:34ch}
.buyer{margin:0 0 16px;color:#dfe4ef}
.tags{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:6px}.tags li{border:1px solid rgba(255,255,255,.3);background:rgba(255,255,255,.07);border-radius:999px;padding:3px 11px;font-size:13px}
.key{background:var(--soft);border-bottom:1px solid var(--line)}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;padding-block:16px}
.k{background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:12px 14px;display:flex;flex-direction:column;gap:2px;min-width:0}
.k small{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.05em}.k b{font-size:22px;font-variant-numeric:tabular-nums}.k span{color:var(--muted);font-size:13px}
.k.due{border-color:var(--gold)}.lights{display:flex;flex-direction:column;gap:6px;margin-top:4px}
.lt{border-radius:6px;padding:3px 8px;font-size:13px;font-weight:600}.lt::before{content:"●  "}
.lt.hi{background:var(--hi-bg);color:var(--hi)}.lt.mid{background:var(--mid-bg);color:var(--mid)}.lt.lo{background:var(--lo-bg);color:var(--lo)}
main section{padding-block:20px;border-bottom:1px solid var(--line)}h2{font-size:20px;margin:0 0 12px;color:var(--ink);text-wrap:balance}
.h2n{font-size:13px;font-weight:600;color:var(--muted);margin-left:8px}
.sum ol{margin:0;padding-left:20px;display:grid;gap:6px;max-width:75ch}.verdict,.insight{background:var(--soft);border-left:3px solid var(--gold);padding:10px 14px;margin:14px 0 0;max-width:80ch}
dl{margin:0;display:grid}.row{display:grid;grid-template-columns:220px minmax(0,1fr);gap:16px;padding:9px 0;border-top:1px solid var(--line)}.row:first-child{border-top:0}
dt{font-weight:700}dd{margin:0;max-width:75ch}
.cite{display:inline-block;font-size:11.5px;font-weight:600;color:var(--navy);background:var(--chip);border-radius:4px;padding:0 6px;margin-left:4px;text-decoration:none;white-space:nowrap}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) .cite{color:#c9d3f0}}:root[data-theme="dark"] .cite{color:#c9d3f0}
a.cite:hover,a.cite:focus-visible{outline:2px solid var(--gold)}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th{text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);border-bottom:2px solid var(--line);padding:6px 8px}
td{padding:8px;border-bottom:1px solid var(--line);vertical-align:top}td.n{font-weight:800;color:var(--gold)}.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}tfoot td{font-weight:700}
.note{color:var(--muted);font-size:14px;max-width:80ch}
.crits{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.crit p{margin:6px 0 0;font-size:14px;color:var(--muted)}
.ch{display:flex;justify-content:space-between;gap:8px}.pts{font-weight:800;color:var(--navy);font-variant-numeric:tabular-nums}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) .pts{color:var(--gold)}}:root[data-theme="dark"] .pts{color:var(--gold)}
.bar{height:8px;background:var(--chip);border-radius:4px;margin-top:6px;overflow:hidden}.bar i{display:block;height:100%;background:var(--gold)}
.rgs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.rg h3{font-size:15px;margin:0 0 4px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}.rg .row{grid-template-columns:150px minmax(0,1fr)}
.errs dt{color:var(--lo)}
.dl{display:inline-block;background:var(--navy);color:#fff;text-decoration:none;border-radius:6px;padding:4px 12px;font-size:13px;font-weight:600}
.cta{border-bottom:0}.cta p{max-width:70ch}.btn{display:inline-block;background:var(--gold);color:#1a2850;font-weight:700;text-decoration:none;border-radius:8px;padding:10px 18px}
.btn:focus-visible,.dl:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.disc{font-size:12.5px;color:var(--muted);padding-block:18px 40px;max-width:90ch}
@media (max-width:760px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.row,.rg .row{grid-template-columns:minmax(0,1fr);gap:2px}.crits,.rgs{grid-template-columns:minmax(0,1fr)}}
/* design B */
.hero{background:linear-gradient(90deg,#0b1f3a 50%,#1a2b5a 50%);padding:0;color:#fff}.hg{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr)}
.hero .l{background:#0b1f3a;padding:36px 36px 40px 0}.hero .r{background:none;padding:32px 0 32px 34px;display:grid;gap:14px;align-content:center}
.kick{display:inline-flex;gap:8px;align-items:center;background:#c9a227;color:#0b1f3a;font-weight:900;font-size:12px;letter-spacing:.1em;text-transform:uppercase;padding:6px 12px;border-radius:6px}
.hero h1{font-size:clamp(30px,4.4vw,46px);line-height:1.04;font-weight:900;letter-spacing:-.025em;margin:16px 0 14px;max-width:none}.hero h1 em{font-style:normal;color:#e9c75a}
.lede{color:#d3d9e8;font-size:16.5px;line-height:1.55;margin:0 0 10px;max-width:60ch}.hero .buyer{color:#9aa6c2;font-size:13.5px;margin:0}
.cta-row{display:flex;gap:12px;margin-top:24px;flex-wrap:wrap}.btn.g{background:transparent;color:#fff;border:1.5px solid rgba(255,255,255,.4)}
.big{display:flex;align-items:baseline;gap:12px;border-bottom:1px solid rgba(255,255,255,.13);padding-bottom:14px}.big.last{border:0;padding:0}
.big b{font-size:clamp(34px,4.6vw,52px);font-weight:900;letter-spacing:-.03em;line-height:1;white-space:nowrap}.big span{color:#c8cfe0;font-size:13.5px;line-height:1.3}.big.gold b{color:#e9c75a}
.cal{background:var(--bg);border-bottom:1px solid var(--line)}.cal .in{padding-top:22px;padding-bottom:22px}
.lbl{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:0 0 16px}
.track{position:relative;height:6px;background:var(--line);border-radius:9px;margin:0 10px 62px}.track .done{position:absolute;left:0;top:0;bottom:0;background:#23356b;border-radius:9px}
.ev{position:absolute;top:-7px;margin-left:-75px;text-align:center;width:150px}.ev i{display:block;width:20px;height:20px;border-radius:50%;background:var(--bg);border:4px solid #23356b;margin:0 auto 8px;box-sizing:border-box}
.ev b{display:block;font-size:14px}.ev span{display:block;font-size:12px;color:var(--muted);line-height:1.3}.ev.end i{background:#c9a227;border-color:#c9a227}.ev.q i{border-color:#e46a4f}.ev.past i{background:#23356b}
.ev.first{margin-left:-10px;text-align:left}.ev.first i{margin-left:0}.ev.end{margin-left:-140px;text-align:right}.ev.end i{margin-right:0}
.now{position:absolute;top:-6px;width:18px;height:18px;margin-left:-9px;border-radius:50%;background:#e46a4f;box-shadow:0 0 0 6px rgba(228,106,79,.22);z-index:2}
.evl{display:none}
main section.sec0{border-bottom:0;padding-top:34px}.sec0 h2{font-size:clamp(24px,3vw,30px);font-weight:900;letter-spacing:-.02em;margin:0 0 6px}.sub{color:var(--muted);margin:0 0 20px}
.stack{display:flex;height:60px;border-radius:14px;overflow:hidden;box-shadow:0 8px 24px rgba(15,26,51,.10)}.stack div{display:flex;align-items:center;justify-content:center;color:#fff;font-weight:900;font-size:21px;min-width:0}
.leg{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-top:14px}.leg div{background:var(--soft);border-radius:12px;padding:14px;border-top:5px solid}.leg b{display:block;font-size:14.5px;margin-bottom:4px}.leg span{font-size:13.5px;color:var(--muted);line-height:1.45}
.lots{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.lot{background:var(--bg);border-radius:14px;padding:16px;border:1px solid var(--line);box-shadow:0 2px 8px rgba(15,26,51,.04)}
.lot .lk{font-size:12px;font-weight:800;color:#9a7a12;letter-spacing:.1em}.lot b{display:block;font-size:22px;font-weight:900;margin:4px 0 6px;white-space:nowrap}.lot .c{font-size:13px;color:var(--muted);line-height:1.4;min-height:54px}
.lot .h{height:6px;background:var(--chip);border-radius:9px;margin-top:10px}.lot .h i{display:block;height:100%;background:#4f7cff;border-radius:9px}.lot .m{margin-top:8px;font-size:12px;color:var(--muted);display:flex;gap:6px;align-items:center}
.alert{margin:30px 0 8px;background:#fff4f1;border:1px solid #f6cfc5;border-radius:16px;padding:18px 20px;display:flex;gap:14px;align-items:flex-start;color:#8f2f1c}.alert b{color:#0f1a33}.alert svg{flex:none}.alert a{color:#8f2f1c;font-weight:700}
.verd .lights{flex-direction:row;flex-wrap:wrap;margin:0 0 10px}.verd p{max-width:80ch;margin:0}
@media (max-width:820px){.hero{background:#0b1f3a}.hg{grid-template-columns:minmax(0,1fr)}.hero .l{padding:26px 0 28px}.hero .r{margin:0 -16px;padding:22px 16px}
.leg{grid-template-columns:repeat(2,minmax(0,1fr))}.lots{grid-template-columns:repeat(2,minmax(0,1fr))}.stack div{font-size:16px}
.track{display:none}.evl{display:grid;list-style:none;margin:0;padding:0 0 0 18px;border-left:3px solid var(--line);gap:10px}.evl li{position:relative;font-size:14px}.evl li::before{content:"";position:absolute;left:-26px;top:4px;width:13px;height:13px;border-radius:50%;background:var(--bg);border:3px solid #23356b}
.evl li.past::before{background:#23356b}.evl li.end::before{background:#c9a227;border-color:#c9a227}.evl li.q::before{border-color:#e46a4f}}
"""

PDF_CSS = """
@page{size:A4;margin:16mm 15mm 16mm 15mm;@bottom-left{content:"Ullswater Investments · ficha de licitación · www.ullswaterinvestments.com";font:7.5pt Inter,sans-serif;color:#6b7280}
 @bottom-right{content:counter(page) " / " counter(pages);font:7.5pt Inter,sans-serif;color:#6b7280}}
body{font-size:9.6pt;line-height:1.45}.in{max-width:none;padding:0}.hero{margin:0;padding:14px 16px 16px;border-radius:6px}h1{font-size:17pt;max-width:none}
.key{background:none;border:0}.grid{grid-template-columns:repeat(4,1fr);padding:10px 0}.k b{font-size:14pt}
main section{padding:10px 0;break-inside:auto}h2{font-size:13pt;break-after:avoid}.row{grid-template-columns:42mm 1fr;padding:5px 0;break-inside:avoid}.rg .row{grid-template-columns:30mm 1fr}
.crits{grid-template-columns:1fr 1fr}.crit,.k,.rg h3{break-inside:avoid}.rgs{grid-template-columns:1fr}table{font-size:8.6pt}.cta .btn{display:none}.logo{height:30px;width:auto;display:block;margin-bottom:14px}.crumbs{display:none}
.hero{border-radius:8px;overflow:hidden;background:#0b1f3a}.hero .l{padding:16px 18px 18px}.hero .r{padding:16px 18px}.hero h1{font-size:22pt}.lede{font-size:10pt}.big b{font-size:20pt}.big span{font-size:8pt}.kick{font-size:7pt;display:inline-block}
.cal .in{padding:12px 0 4px}.track{margin:0 8px 46px}.ev{width:110px;margin-left:-55px}.ev.end{margin-left:-100px}.ev b{font-size:8.5pt}.ev span{font-size:7.5pt}
main section.sec0{padding-top:12px}.sec0 h2{font-size:15pt}.stack{height:34px;box-shadow:none}.stack div{font-size:12pt}.leg div{padding:8px}.leg b{font-size:9pt}.leg span{font-size:8pt}
.lots{gap:6px}.lot{padding:8px;box-shadow:none}.lot b{font-size:12pt}.lot .c{font-size:7.5pt;min-height:0}.lot .m{font-size:7pt}.alert{padding:10px 12px;font-size:9pt}.sec0,.lots,.leg,.alert,.hero{break-inside:avoid}
"""


def scoped_css(scope=".fx"):
    """Site version of the CSS: light tokens only, every selector prefixed with the scope so it cannot clash with the site shell."""
    import re
    css = re.sub(r"@media \(prefers-color-scheme: dark\)\{(?:[^{}]*\{[^{}]*\})+\}", "", CSS)
    css = re.sub(r":root\[data-theme=\"dark\"\][^{]*\{[^{}]*\}", "", css)
    css = css.replace(":root{", scope + "{").replace("body{", scope + "{")

    def fix(m):
        sels = ",".join(x.strip() if x.strip().startswith(scope) else f"{scope} {x.strip()}" for x in m.group(1).split(","))
        return f"{sels}{{{m.group(2)}}}"
    return re.sub(r"([^{}@]+)\{([^{}]*)\}", fix, css)


def main(d):
    d = Path(d)
    f = json.loads((d / "ficha.json").read_text(encoding="utf-8"))
    idx = json.loads((d / "index.json").read_text(encoding="utf-8"))
    head = f'<title>{e(f.get("headline") or f["title"])}</title><meta name="claude:viewport-fit-sides" content="cover">'
    fonts = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap">'
    (d / "ficha.html").write_text(f"{head}{fonts}<style>{CSS}</style>{body(f, idx)}", encoding="utf-8")
    html = f'<!doctype html><html lang="es"><head><meta charset="utf-8"><style>{CSS}{PDF_CSS}</style></head><body>{body(f, idx, pdf=True)}</body></html>'
    from weasyprint import HTML
    HTML(string=html).write_pdf(d / "ficha.pdf")
    print("ok", d / "ficha.html", d / "ficha.pdf")


if __name__ == "__main__":
    main(sys.argv[1])
