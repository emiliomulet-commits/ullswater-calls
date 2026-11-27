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


def body(f, idx, pdf=False):
    docs_url = {}
    by_file = {d.get("file"): d for d in idx["docs"]}
    for k, d in f["docs"].items():
        docs_url[k] = by_file.get(d["file"], {}).get("uri", "")
    days = (date.fromisoformat(f["deadline"]) - date.fromisoformat(f["reviewed"])).days
    v = f["verdict"]
    lvl = {"alta": "hi", "media": "mid", "baja": "lo"}
    tags = "".join(f'<li>{e(t)}</li>' for t in f["tags"].values())
    secs = {s["key"]: s for s in f["sections"]}
    lots = secs["lots"]
    lot_rows = "".join(f'<tr><td class="n">{x["n"]}</td><td>{e(x["centres"])}</td><td class="num">{eur(x["fee"])}</td>'
                       f'<td class="num">{eur0(x["works"])}</td><td class="num">{x["months"]} meses</td></tr>' for x in lots["lots"])
    tot_fee, tot_w = sum(x["fee"] for x in lots["lots"]), sum(x["works"] for x in lots["lots"])
    win = secs["win"]
    bars = "".join(f'<div class="crit"><div class="ch"><b>{e(c["name"])}</b><span class="pts">{c["pts"]} pts</span></div>'
                   f'<div class="bar"><i style="width:{c["pts"]}%"></i></div><p>{e(c["how"])}</p></div>' for c in win["criteria"])
    risk = secs["risk"]
    risk_html = "".join(f'<div class="rg"><h3>{e(g["h"])}</h3><dl>{rows(g["items"], docs_url, pdf)}</dl></div>' for g in risk["groups"])
    err = secs["errors"]
    files = "".join(
        f'<tr><td>{e(x["name"])}</td><td>{e(x["type"])}{" · " + str(x["pages"]) + " págs." if x.get("pages") else ""}</td><td class="num">{x["bytes"] / 1e3:,.0f} KB</td>'
        + ("" if pdf else f'<td><a class="dl" href="{e(by_file.get(x["file"], {}).get("uri", f["official_url"]))}" target="_blank" rel="noopener">Descargar</a></td>') + "</tr>"
        for x in f["files"])
    summ = "".join(f"<li>{e(s)}</li>" for s in f["summary"])
    return f"""
<header class="hero"><div class="in">
 <img class="logo" src="{LOGO}" alt="Ullswater Investments">
 <p class="crumbs">Licitaciones › España › Ayuntamientos › Andalucía</p>
 <p class="kicker">Ficha Ullswater · expediente {e(f['ref'])}</p>
 <h1>{e(f['title'])}</h1>
 <p class="buyer">{e(f['buyer'])} · {e(f['unit'])}</p>
 <ul class="tags">{tags}</ul>
</div></header>
<section class="key"><div class="in grid">
 <div class="k due"><small>Fecha límite</small><b>{date.fromisoformat(f['deadline']).day} dic</b><span>{f['deadline_time']} h · quedan {days} días</span></div>
 <div class="k"><small>Presupuesto sin IVA</small><b>{eur0(tot_fee)}</b><span>5 lotes de 30.133 € a 33.971 €</span></div>
 <div class="k"><small>Obras que se dirigen</small><b>{f"{tot_w / 1e6:.2f}".replace(".", ",")} M€</b><span>13 colegios de Infantil</span></div>
 <div class="k sem"><small>Valoración Ullswater</small>
  <div class="lights"><span class="lt {lvl[v['opportunity']]}">Oportunidad {e(v['opportunity'])}</span><span class="lt {lvl[v['difficulty']]}">Dificultad {e(v['difficulty'])}</span></div></div>
</div></section>
<main class="in">
 <section class="sum"><h2>En cinco líneas</h2><ol>{summ}</ol>
  <p class="verdict"><b>Nuestra lectura.</b> {e(v['text'])}</p></section>
 <section><h2>{e(secs['what']['h'])}</h2><dl>{rows(secs['what']['items'], docs_url, pdf)}</dl></section>
 <section><h2>{e(lots['h'])}</h2><div class="tw"><table class="lots"><thead><tr><th>Lote</th><th>Colegios</th><th class="num">Honorarios sin IVA</th><th class="num">Obra que se dirige</th><th class="num">Duración</th></tr></thead>
  <tbody>{lot_rows}</tbody><tfoot><tr><td></td><td>Total</td><td class="num">{eur(tot_fee)}</td><td class="num">{eur0(tot_w)}</td><td></td></tr></tfoot></table></div>
  <p class="note">{e(lots['note'])} {cites(lots['cite'], docs_url, pdf)}</p></section>
 <section><h2>{e(secs['money']['h'])}</h2><dl>{rows(secs['money']['items'], docs_url, pdf)}</dl></section>
 <section><h2>{e(secs['can']['h'])}</h2><dl>{rows(secs['can']['items'], docs_url, pdf)}</dl></section>
 <section><h2>{e(win['h'])} <span class="h2n">100 puntos, todos con fórmula</span></h2><div class="crits">{bars}</div>
  <p class="note">{cites(win['cite'], docs_url, pdf)}</p>
  <p class="insight"><b>Dónde se decide.</b> {e(win['insight'])}</p><dl>{rows(win['items'], docs_url, pdf)}</dl></section>
 <section><h2>{e(secs['when']['h'])}</h2><dl>{rows(secs['when']['items'], docs_url, pdf)}</dl></section>
 <section><h2>{e(risk['h'])}</h2><div class="rgs">{risk_html}</div></section>
 <section class="errs"><h2>{e(err['h'])}</h2><dl>{rows(err['items'], docs_url, pdf)}</dl><p class="note">{e(err['advice'])}</p></section>
 <section><h2>Documentos oficiales</h2><p class="note">Copia de los documentos publicados en la Plataforma de Contratación del Sector Público. La versión válida es siempre la de la Plataforma.</p>
  <div class="tw"><table class="files"><thead><tr><th>Documento</th><th>Formato</th><th class="num">Tamaño</th>{'' if pdf else '<th></th>'}</tr></thead><tbody>{files}</tbody></table></div>
  <p class="note">Anuncio, pliegos y rectificaciones en la <a href="{e(f['official_url'])}" target="_blank" rel="noopener">ficha oficial de la licitación</a>.</p></section>
 <section class="cta"><h2>¿Te presentas?</h2><p>Hacemos gratis un primer diagnóstico de esta licitación con tu empresa: si cumples la solvencia, qué puntuación puedes esperar y qué precio te deja opciones. Después, si quieres, un consultor te ayuda a preparar la oferta.</p>
  <p><a class="btn" href="https://www.ullswaterinvestments.com/es/contacto/" target="_blank" rel="noopener">Pedir diagnóstico gratuito</a></p></section>
 <p class="disc">Resumen elaborado con IA a partir de los {len(f['docs'])} documentos principales del expediente (PCAP, PPT y anexos; {sum(d['pages'] for d in f['docs'].values())} páginas). Revisado el {fd(f['reviewed'])}. Prevalecen siempre los pliegos y el anuncio oficial. Cada dato indica el documento y la página de donde sale: PCAP = pliego administrativo, PPT = pliego técnico, ANX = anexos al PCAP.</p>
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
"""

PDF_CSS = """
@page{size:A4;margin:16mm 15mm 16mm 15mm;@bottom-left{content:"Ullswater Investments · ficha de licitación · www.ullswaterinvestments.com";font:7.5pt Inter,sans-serif;color:#6b7280}
 @bottom-right{content:counter(page) " / " counter(pages);font:7.5pt Inter,sans-serif;color:#6b7280}}
body{font-size:9.6pt;line-height:1.45}.in{max-width:none;padding:0}.hero{margin:0;padding:14px 16px 16px;border-radius:6px}h1{font-size:17pt;max-width:none}
.key{background:none;border:0}.grid{grid-template-columns:repeat(4,1fr);padding:10px 0}.k b{font-size:14pt}
main section{padding:10px 0;break-inside:auto}h2{font-size:13pt;break-after:avoid}.row{grid-template-columns:42mm 1fr;padding:5px 0;break-inside:avoid}.rg .row{grid-template-columns:30mm 1fr}
.crits{grid-template-columns:1fr 1fr}.crit,.k,.rg h3{break-inside:avoid}.rgs{grid-template-columns:1fr}table{font-size:8.6pt}.cta .btn{display:none}.logo{height:30px;width:auto;display:block;margin-bottom:14px}.crumbs{display:none}
"""


def main(d):
    d = Path(d)
    f = json.loads((d / "ficha.json").read_text(encoding="utf-8"))
    idx = json.loads((d / "index.json").read_text(encoding="utf-8"))
    head = '<title>Dirección de obras en colegios de Sevilla</title><meta name="claude:viewport-fit-sides" content="cover">'
    fonts = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap">'
    (d / "ficha.html").write_text(f"{head}{fonts}<style>{CSS}</style>{body(f, idx)}", encoding="utf-8")
    html = f'<!doctype html><html lang="es"><head><meta charset="utf-8"><style>{CSS}{PDF_CSS}</style></head><body>{body(f, idx, pdf=True)}</body></html>'
    from weasyprint import HTML
    HTML(string=html).write_pdf(d / "ficha.pdf")
    print("ok", d / "ficha.html", d / "ficha.pdf")


if __name__ == "__main__":
    main(sys.argv[1])
