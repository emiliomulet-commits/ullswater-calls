"""Downloadable PDF factsheets ("fichas") for every published call, in the Ullswater house style.

- EU calls (site/data/calls.json, data/topic_text.json, data/partners.json) -> factsheet in English.
- Spanish calls (site/data/spain.json, BDNS)                               -> ficha en español.

Each PDF is encrypted with AES-256-GCM (key: env FICHAS_KEY, 32 bytes in base64) and written to
site/fichas/<slug>.bin, so the public site never exposes the PDF itself. The "ullswater-fichas" Worker
decrypts and serves it only after the visitor has verified their email address.

Pages 1 and 2 are public: they are rendered as images (site/fichas/p/<slug>-1.jpg, -2.jpg) and shown on the call
page by assets/ficha.js; the full PDF and its download need the email check. Previews are written even without
FICHAS_KEY (index.json then marks the factsheets as not downloadable, "dl": 0).

PDFs are cached in .cache/fichas by a fingerprint of their content, so only changed calls are re-rendered.

Local preview (no key needed):  python scripts/fichas.py --preview HORIZON-MSCA-2026-DN-01-01 936950
  -> writes plain PDFs to .cache/fichas/preview/
"""
import base64
import hashlib
import json
import os
import re
import sys
from datetime import date
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
OUT = SITE / "fichas"
CACHE = ROOT / ".cache" / "fichas"
ASSETS = Path(__file__).resolve().parent / "fichas_assets"
VERSION = "1"  # bump to force every PDF to be rebuilt after a template change

NAVY, NAVY_BG, GOLD, GOLD_L, GOLD_BG = "#233567", "#E9ECF4", "#C9A646", "#EDBC6C", "#FBF3E2"
INK, GREY, LIGHT, BORDER, RED = "#1F2937", "#6B7280", "#F4F5F7", "#D5D8DE", "#A84343"
MONTHS = {"en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
          "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]}
MAIN = "https://www.ullswaterinvestments.com"
CALLS = "https://calls.ullswaterinvestments.com"
CONTACT = "eufunding@ullswaterinvestments.com"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def fdate(iso, lang="en"):
    if not iso:
        return ""
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {MONTHS[lang][d.month - 1]} {d.year}" if lang == "en" else f"{d.day} de {MONTHS[lang][d.month - 1]} de {d.year}"


def money(v, lang="en"):
    if not v:
        return ""
    if v >= 1_000_000:
        s = f"{v / 1_000_000:.1f}".rstrip("0").rstrip(".")
        return f"€{s}M" if lang == "en" else f"{s.replace('.', ',')} M€"
    if lang == "en":
        return f"€{round(v / 1000):,}k"
    return f"{v:,.0f} €".replace(",", ".")


def e(s):
    return escape(str(s or ""))


def cut(text, n):
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= n:
        return text
    i = text.rfind(". ", 0, n)
    return text[: i + 1] if i > n * 0.5 else text[:n].rsplit(" ", 1)[0] + "…"


# ------------------------------------------------------------------ SVG infographics
W = 760


def t(x, y, s, size=11.5, w=400, fill=INK, anchor="start"):
    return f'<text x="{x}" y="{y}" font-family="Inter" font-size="{size}" font-weight="{w}" fill="{fill}" text-anchor="{anchor}">{e(s)}</text>'


def wrap(s, n):
    out, cur = [], ""
    for word in str(s).split():
        if len(cur) + len(word) + 1 > n and cur:
            out.append(cur)
            cur = word
        else:
            cur = (cur + " " + word).strip()
    if cur:
        out.append(cur)
    return out


def tl(x, y, lines, size=11, w=400, fill=GREY, lh=15, anchor="start"):
    return "".join(t(x, y + i * lh, s, size, w, fill, anchor) for i, s in enumerate(lines))


def box(x, y, w, h, fill="#FFFFFF", stroke=BORDER, sw=1.1, r=8):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def head(title, sub):
    return f'<rect x="24" y="20" width="34" height="4" fill="{GOLD}"/>' + t(24, 48, title, 16, 700, NAVY) + t(24, 67, sub, 11, 400, GREY)


def band(y, main, sub=""):
    s = box(24, y, W - 48, 44 if sub else 34, NAVY, NAVY, 1, 8) + t(40, y + (20 if sub else 22), main, 12, 600, "#FFFFFF")
    return s + (t(40, y + 36, sub, 10.5, 400, GOLD_L) if sub else "")


def svg(h, body):
    return f'<svg class="info" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="100%">{body}</svg>'


def kpi_panel(title, sub, cards, band_main, band_sub, source):
    """3 x 2 (or 3 x 1) grid of KPI cards. cards: [(big, label, [lines], accent)]"""
    b = head(title, sub)
    cw, ch, gap = 226, 112, 17
    for i, (num, lab, lines, acc) in enumerate(cards[:6]):
        x = 24 + (i % 3) * (cw + gap)
        y = 86 + (i // 3) * (ch + 14)
        b += box(x, y, cw, ch, GOLD_BG if acc else "#FFFFFF", GOLD if acc else BORDER, 2 if acc else 1.1)
        size = 24 if len(num) <= 11 else 18
        b += t(x + 16, y + 34, num, size, 700, NAVY) + t(x + 16, y + 55, lab, 12, 600, INK)
        b += tl(x + 16, y + 74, [ln for l_ in lines for ln in wrap(l_, 34)][:2], 10.5, 400, GREY, 14)
    rows = (min(len(cards), 6) + 2) // 3
    y = 86 + rows * (ch + 14) + 2
    b += band(y, band_main, band_sub)
    b += t(24, y + 64, source, 9, 400, GREY)
    return svg(y + 74, b)


def timeline(title, sub, points, phases, note, source):
    """points: [(iso, label_lines, key)], phases: [(iso_from, iso_to, label, colour, text colour)]"""
    days = [date.fromisoformat(p[0]) for p in points] + [date.fromisoformat(a) for a, *_ in phases] + [date.fromisoformat(p[1]) for p in phases]
    d0, d1 = min(days), max(days)
    span = max((d1 - d0).days, 30)
    x0, x1 = 60, W - 60

    def X(iso):
        return x0 + (x1 - x0) * (date.fromisoformat(iso) - d0).days / span
    b = head(title, sub)
    yA = 140
    b += f'<line x1="{x0 - 20}" y1="{yA}" x2="{x1 + 20}" y2="{yA}" stroke="{BORDER}" stroke-width="2"/>'
    for a, z, lab, fill, tc in phases:
        b += f'<rect x="{X(a):.1f}" y="{yA - 40}" width="{max(X(z) - X(a), 2):.1f}" height="24" rx="4" fill="{fill}"/>'
        if X(z) - X(a) > len(lab) * 6.2 + 12:
            b += t((X(a) + X(z)) / 2, yA - 24, lab, 10.5, 600, tc, "middle")
    lines_, txt = "", ""
    for i, (iso, lab, key) in enumerate(points):
        x = X(iso)
        row = i % 3
        yy = yA + 40 + row * 46
        lines_ += f'<line x1="{x:.1f}" y1="{yA + 8}" x2="{x:.1f}" y2="{yy - 12}" stroke="{GOLD if key else BORDER}" stroke-width="{2 if key else 1}"/>'
        lines_ += f'<circle cx="{x:.1f}" cy="{yA}" r="{6 if key else 4.5}" fill="{GOLD if key else NAVY}"/>'
        anc = "start" if x < 200 else ("end" if x > W - 200 else "middle")
        tx = x + 5 if anc == "start" else (x - 5 if anc == "end" else x)
        wmax = max(len(lab[0]) * 7.2, *(len(s_) * 6.2 for s_ in lab[1:])) + 6
        bx = tx - 3 if anc == "start" else (tx - wmax + 3 if anc == "end" else tx - wmax / 2)
        txt += f'<rect x="{bx:.1f}" y="{yy - 13}" width="{wmax:.1f}" height="{14 + 13 * len(lab[1:]) + 4}" fill="#FFFFFF"/>'
        txt += t(tx, yy, lab[0], 11.5, 700, GOLD if key else NAVY, anc) + tl(tx, yy + 14, lab[1:], 10.5, 400, GREY, 13, anc)
    b += lines_ + txt
    y = yA + 40 + 3 * 46 + 4
    b += band(y, note[0], note[1] if len(note) > 1 else "")
    b += t(24, y + 64, source, 9, 400, GREY)
    return svg(y + 74, b)


def consortium(title, sub, a, fnd, lang, source):
    labels = {"en": ("partners (median)", "countries (median)", "of partners are SMEs", "Organisation mix in the closest funded projects",
                     "median EU grant of the closest projects", "projects funded in earlier topics of this line"),
              "es": ("socios (mediana)", "países (mediana)", "de los socios son pymes", "Tipo de organización en los proyectos más parecidos",
                     "subvención UE mediana de los proyectos más parecidos", "proyectos financiados en temas anteriores")}[lang]
    cols = {"Company": NAVY, "Research organisation": GOLD, "University": "#3B6FB6", "Public body": "#067647", "Other": "#9AA3B2"}
    b = head(title, sub)
    cards = [(str(a.get("partners", "–")), labels[0]), (str(a.get("countries", "–")), labels[1]), (f'{a.get("sme_share", 0) * 100:.0f} %', labels[2])]
    if fnd.get("median_eu"):
        cards.append((money(fnd["median_eu"], lang), labels[4]))
    cw = (W - 48 - (len(cards) - 1) * 16) / len(cards)
    for i, (n, l_) in enumerate(cards):
        x = 24 + i * (cw + 16)
        b += box(x, 84, cw, 86, LIGHT, BORDER) + t(x + 14, 118, n, 22, 700, NAVY) + tl(x + 14, 138, wrap(l_, int(cw / 6.4)), 10.5, 400, GREY, 13.5)
    b += t(24, 200, labels[3], 11.5, 600, INK)
    x = 24.0
    mix = sorted(a.get("mix", {}).items(), key=lambda kv: -kv[1])
    for k, v in mix:
        w_ = (W - 48) * v
        b += f'<rect x="{x:.1f}" y="210" width="{w_:.1f}" height="26" fill="{cols.get(k, "#999")}"/>'
        if w_ > 46:
            b += t(x + w_ / 2, 227, f"{v * 100:.0f} %", 10.5, 600, "#FFFFFF", "middle")
        x += w_
    lx = 24
    for k, v in mix:
        b += f'<rect x="{lx}" y="248" width="10" height="10" rx="2" fill="{cols.get(k, "#999")}"/>' + t(lx + 15, 257, k, 10.5, 400, GREY)
        lx += 15 + len(k) * 6 + 22
    y = 276
    note = ("Benchmark, not a rule: check the minimum consortium in the call conditions." if lang == "en"
            else "Referencia orientativa: compruebe el consorcio mínimo en las condiciones de la convocatoria.")
    b += band(y, note)
    b += t(24, y + 52, source, 9, 400, GREY)
    return svg(y + 62, b)


# ------------------------------------------------------------------ HTML template
CSS = f"""
@page {{ size: A4; margin: 20mm 18mm 18mm 18mm;
  @top-left {{ content: element(hdr); }}
  @bottom-left {{ content: "Ullswater Investments · EU Funding Advisors · www.ullswaterinvestments.com"; font: 7.5pt Inter, sans-serif; color: {GREY}; }}
  @bottom-right {{ content: counter(page) " / " counter(pages); font: 700 7.5pt Inter, sans-serif; color: {NAVY}; }} }}
@page :first {{ margin: 12mm 14mm 14mm 14mm; @top-left {{ content: none; }} @bottom-left {{ content: none; }} @bottom-right {{ content: none; }} }}
html {{ font-family: Inter, "DejaVu Sans", sans-serif; font-size: 9.6pt; color: {INK}; line-height: 1.45; }}
.hdr {{ position: running(hdr); width: 174mm; border-bottom: 0.8pt solid {GOLD}; padding-bottom: 2mm; display: flex; justify-content: space-between; align-items: flex-end; }}
.hdr img {{ height: 6mm; }} .hdr span {{ font-size: 7.5pt; color: {GREY}; }}
.cover-band {{ background: {NAVY}; border-radius: 3mm; padding: 16mm 14mm 13mm; color: #fff; }}
.cover-band img {{ width: 120mm; }} .cover-band .rule {{ height: 0.8mm; background: {GOLD}; margin: 9mm 0 6mm; }}
.cover-band .tag {{ font-size: 13pt; font-weight: 700; }} .cover-band .sub {{ color: {GOLD_L}; font-size: 9.5pt; margin-top: 1.5mm; }}
.kicker {{ color: {GOLD}; font-weight: 700; letter-spacing: 0.08em; font-size: 8.5pt; margin: 9mm 0 2mm; text-transform: uppercase; }}
h1 {{ color: {NAVY}; font-size: 20pt; line-height: 1.18; margin: 0 0 3mm; font-weight: 800; }}
.lead {{ font-size: 11pt; border-bottom: 0.9pt solid {GOLD}; padding-bottom: 3mm; margin: 0 0 5mm; }}
h2 {{ color: {NAVY}; font-size: 14pt; margin: 7mm 0 3mm; padding-bottom: 1.2mm; border-bottom: 0.9pt solid {GOLD}; break-after: avoid; }}
h3 {{ color: {NAVY}; font-size: 11pt; margin: 4mm 0 1.5mm; break-after: avoid; }}
p {{ margin: 0 0 2.4mm; }} ul {{ margin: 0 0 3mm; padding-left: 5mm; }} li {{ margin-bottom: 1.2mm; }} li::marker {{ color: {GOLD}; }}
table.kv, table.list {{ width: 100%; border-collapse: collapse; font-size: 8.6pt; margin-bottom: 4mm; }}
table.kv td, table.list td, table.list th {{ border: 0.5pt solid {BORDER}; padding: 1.6mm 2.2mm; vertical-align: top; }}
table.kv td:first-child {{ background: {LIGHT}; font-weight: 700; width: 34%; }}
table.list th {{ background: {NAVY}; color: #fff; text-align: left; font-weight: 700; }} table.list td.n {{ text-align: right; }}
ol {{ margin: 0 0 3mm; padding-left: 6mm; }} ol li::marker {{ color: {NAVY}; font-weight: 700; }}
table.kv tr, table.list tr {{ break-inside: avoid; }}
.fig {{ margin: 3mm 0 1mm; break-inside: avoid; }} .cap {{ font-size: 7.8pt; color: {GREY}; font-style: italic; margin-bottom: 4mm; }}
.callout {{ background: {GOLD_BG}; border-left: 1.6mm solid {GOLD}; padding: 3mm 4.5mm; margin: 4mm 0; break-inside: avoid; }}
.callout.navy {{ background: {NAVY_BG}; border-color: {NAVY}; }} .callout b.t {{ color: {NAVY}; display: block; margin-bottom: 1.5mm; font-size: 10.5pt; }}
.meta {{ font-size: 8pt; color: {GREY}; }} .src {{ font-size: 7.8pt; color: {GREY}; word-break: break-all; }}
.disc {{ font-size: 7.6pt; color: {GREY}; font-style: italic; }} .keep {{ break-inside: avoid; }}
a {{ color: {NAVY}; text-decoration: none; }}
"""


def logo(which):
    return (ASSETS / f"logo_{which}.svg").as_uri()


def document(lang, title, kicker, lead, cover_rows, body, header_txt, prepared):
    L = {"en": ("Key information", "Detail", "Prepared by Ullswater Investments · EU Funding Advisors",
                "Information factsheet generated automatically from official data. It does not replace the official call documents, which always prevail."),
         "es": ("Dato clave", "Detalle", "Preparado por Ullswater Investments · EU Funding Advisors",
                "Ficha informativa generada automáticamente a partir de datos oficiales. No sustituye a las bases y la convocatoria oficiales, que prevalecen siempre.")}[lang]
    rows = "".join(f"<tr><td>{e(k)}</td><td>{v}</td></tr>" for k, v in cover_rows)
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{e(title)}</title><style>{CSS}</style></head><body>
<div class="hdr"><img src="{logo('navy')}"><span>{e(header_txt)}</span></div>
<section class="cover"><div class="cover-band"><img src="{logo('white')}"><div class="rule"></div>
<div class="tag">EU Funding Advisors · Madrid &amp; Brussels</div><div class="sub">Horizon Europe · EIC · Digital Europe · LIFE · CDTI · {'Spanish & regional grants' if lang == 'en' else 'ayudas nacionales y autonómicas'}</div></div>
<p class="kicker">{e(kicker)}</p><h1>{e(title)}</h1><p class="lead">{lead}</p>
<table class="kv">{rows}</table>
<p style="margin-top:8mm"><b style="color:{NAVY}">{L[2]}</b><br><span class="meta">Madrid · Brussels · www.ullswaterinvestments.com · {e(prepared)}</span></p>
<p class="disc">{L[3]}</p></section>
<div style="break-before: page"></div>{body}</body></html>"""


def fig(svg_, caption):
    return f'<div class="fig">{svg_}<p class="cap">{e(caption)}</p></div>'


def help_box(lang, url):
    if lang == "en":
        items = ["Eligibility check and fit with your project, free of charge and within 2 working days.",
                 "Consortium building: partner search, track-record analysis and introductions.",
                 "Proposal writing, budget and work plan, and review against the evaluation criteria.",
                 "Grant management after award: reporting, amendments and audits."]
        head_, contact = "How Ullswater Investments can help", "Contact"
    else:
        items = ["Diagnóstico de elegibilidad y encaje con su proyecto, gratuito y en 2 días hábiles.",
                 "Estructuración de la agrupación o consorcio y búsqueda de socios.",
                 "Redacción de la memoria técnica, presupuesto y plan de trabajo, y revisión frente a los criterios de valoración.",
                 "Acompañamiento en la ejecución: seguimiento, modificaciones y justificación."]
        head_, contact = "Cómo puede ayudar Ullswater Investments", "Contacto"
    li = "".join(f"<li>{e(i)}</li>" for i in items)
    return (f'<div class="callout navy"><b class="t">{head_}</b><ul>{li}</ul>'
            f'<p style="margin:0"><b>{contact}:</b> {CONTACT} · <a href="{e(url)}">{e(url)}</a></p></div>')


# ------------------------------------------------------------------ EU calls
def split_topic(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    out = {}
    m = re.search(r"(Expected Outcome:|Project results are expected to contribute)", text)
    s = re.search(r"Scope:", text)
    if m:
        out["outcome"] = text[m.start(): s.start() if s and s.start() > m.start() else None].replace("Expected Outcome:", "").strip()
    if s:
        out["scope"] = text[s.end():].strip()
    if not out and text:
        out["scope"] = text
    return out


def action_code(actions):
    a = " ".join(actions).upper()
    for k, v in (("COFUND", "COFUND"), ("RESEARCH AND INNOVATION", "RIA"), ("-RIA", "RIA"), ("INNOVATION ACTION", "IA"), ("-IA", "IA"),
                 ("COORDINATION AND SUPPORT", "CSA"), ("-CSA", "CSA"), ("MSCA", "MSCA"), ("ERC", "ERC"), ("EIC", "EIC"), ("LUMP SUM", "Lump sum"),
                 ("SIMPLE GRANT", "Grant"), ("SME", "SME support"), ("PCP", "PCP"), ("PPI", "PPI")):
        if k in a:
            return v
    return "Grant"


def eu_ficha(c, p, ttext, today):
    lang = "en"
    ident = c["id"] if c["kind"] == "topic" else (c.get("call") or c["id"])
    prog = c.get("programmeName") or c["programme"]
    page_url = f"{CALLS}/call/{slug(c['id'])}/"
    x = c.get("extra") or {}
    per = ""
    if c.get("minEU") and c.get("maxEU"):
        per = money(c["minEU"]) if c["minEU"] == c["maxEU"] else f"{money(c['minEU'])}–{money(c['maxEU'])}"
    elif c.get("maxEU"):
        per = f"up to {money(c['maxEU'])}"
    status = "Open" if c["status"] == "open" else "Forthcoming"
    cover_rows = [("Programme", e(prog)), ("Call / topic", e(ident)), ("Status", status)]
    if c.get("opening"): cover_rows.append(("Opening", fdate(c["opening"])))
    if c.get("deadline"): cover_rows.append(("Deadline", f"<b>{fdate(c['deadline'])}</b>" + (f" · {e(x['deadline_time'])}" if x.get("deadline_time") else "")))
    if c.get("budget"): cover_rows.append(("Indicative budget", money(c["budget"])))
    if per: cover_rows.append(("EU contribution per project", e(per)))
    if c.get("grants"): cover_rows.append(("Expected grants", str(c["grants"])))
    if c.get("actions"): cover_rows.append(("Type of action", e("; ".join(c["actions"][:3]))))
    lead = e(cut(c.get("summary") or "", 260)) or e(c.get("callTitle") or "")

    # 1. Key facts
    cards = [(fdate(c["deadline"]) if c.get("deadline") else "TBC", "Deadline", [c.get("deadlineModel", "").replace("-", " ").capitalize() or "Check the call"], True),
             (money(c["budget"]) if c.get("budget") else "n/a", "Indicative budget", ["Total for this topic/call" if c["kind"] == "topic" else "Total cascade funding"], False),
             (per or "See call", "Per project (EU)", ["Requested EU contribution" if per else "Not published as a range"], False)]
    if c.get("grants"):
        cards.append((str(c["grants"]), "Expected grants", ["Official indicative number"], False))
    cards.append((status, "Status", [f"Opened {fdate(c['opening'])}" if c.get("opening") and c["status"] == "open" else (f"Opens {fdate(c['opening'])}" if c.get("opening") else "")], False))
    if c.get("actions"):
        cards.append((action_code(c["actions"]), "Type of action", [c["actions"][0]], False))
    k1 = kpi_panel(f"{ident}: the key figures", cut(c["title"], 95), cards,
                   f"Submission through the EU Funding & Tenders Portal{' by ' + fdate(c['deadline']) if c.get('deadline') else ''}",
                   "Always check the exact deadline time and the call documents on the official topic page",
                   "Source: European Commission, Funding & Tenders Portal. Elaboration: Ullswater Investments.")
    rows = [("Programme", e(prog)), ("Call", e(c.get("callTitle") or c.get("call") or "")), ("Identifier", e(ident)),
            ("Kind", "EU topic (direct EU grant)" if c["kind"] == "topic" else "Cascade funding (financial support to third parties)")]
    rows += [r for r in cover_rows if r[0] in ("Opening", "Deadline", "Indicative budget", "EU contribution per project", "Expected grants", "Type of action")]
    if c.get("deadlineModel"): rows.append(("Submission model", e(c["deadlineModel"].replace("-", " "))))
    if c.get("tags"): rows.append(("Keywords", e(", ".join(c["tags"][:10]))))
    rows.append(("Official page", f'<a href="{e(x.get("official_url") or c["url"])}">{e(x.get("official_url") or c["url"])}</a>'))
    body = ["<h2>1. Key facts</h2>", fig(k1, "Infographic 1 · Key figures of the call."),
            '<table class="kv">' + "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows) + "</table>"]

    # 2. What the call funds
    parts = split_topic(ttext)
    body.append("<h2>2. What the call funds</h2>")
    if c.get("summary"):
        body.append(f"<p>{e(cut(c['summary'], 900))}</p>")
    if parts.get("outcome") and not (c.get("summary") or "")[:120].strip() in parts["outcome"]:
        body.append(f"<h3>Expected outcomes</h3><p>{e(cut(parts['outcome'], 1600))}</p>")
    if parts.get("scope"):
        body.append(f"<h3>Scope</h3><p>{e(cut(parts['scope'], 2200))}</p>")
    if parts:
        body.append('<p class="disc">Excerpt from the official topic description (European Commission). Read the full text and the call conditions on the official page.</p>')
    if x.get("conditions"):
        body.append("<h3>Key conditions</h3><ul>" + "".join(f"<li>{e(i)}</li>" for i in x["conditions"]) + "</ul>")

    # 3. Calendar
    if c.get("deadline"):
        pts, phases = [], []
        if c.get("opening") and c["opening"] < c["deadline"]:
            pts.append((c["opening"], ["Opening", fdate(c["opening"])], False))
            phases.append((c["opening"], c["deadline"], "Submission window", "#C7CCD8", INK))
        pts.append((c["deadline"], ["Deadline", fdate(c["deadline"])], True))
        note = ("Start the consortium and the proposal at least 3–4 months before the deadline", "Register your organisation (PIC) in the Funding & Tenders Portal early")
        if c["programme"] in ("HORIZON", "EURATOM") and c["kind"] == "topic" and c.get("deadlineModel") == "single-stage":
            dl = date.fromisoformat(c["deadline"])
            ev = date(dl.year + (dl.month + 5 > 12), (dl.month + 4) % 12 + 1, min(dl.day, 28)).isoformat()
            ga = date(dl.year + (dl.month + 8 > 12), (dl.month + 7) % 12 + 1, min(dl.day, 28)).isoformat()
            phases.append((c["deadline"], ev, "Evaluation", NAVY, "#FFFFFF"))
            phases.append((ev, ga, "Grant preparation", GOLD, "#FFFFFF"))
            pts.append((ev, ["~5 months", "Evaluation result"], False))
            pts.append((ga, ["~8 months", "Grant signature"], False))
            sub = "Dates after the deadline are indicative (Horizon Europe targets: result in 5 months, grant in 8)"
        else:
            sub = "Opening and deadline as published in the Funding & Tenders Portal"
        if len(pts) >= 2:
            body.append("<h2>3. Calendar</h2>")
            body.append(fig(timeline("From opening to grant", sub, pts, phases, note, "Source: Funding & Tenders Portal; Horizon Europe time-to-grant targets. Elaboration: Ullswater Investments."),
                            "Infographic 2 · Calendar of the call."))
    n = 4 if any("<h2>3." in s for s in body) else 3

    # Competition and partners (CORDIS)
    show = bool(p) and c["kind"] == "topic" and c["programme"] in {"HORIZON", "EURATOM", "DIGITAL", "EUBA"} and p.get("max_sim", 0) >= 0.10
    if show:
        body.append(f"<h2>{n}. Competition and consortium</h2>")
        body.append("<p>Benchmarks from the EU-funded projects (Horizon Europe and Horizon 2020) whose content is closest to this call, from CORDIS open data.</p>")
        if p.get("archetype"):
            body.append(fig(consortium("What a typical winning consortium looks like", f"Based on the {p['archetype'].get('based_on', '')} funded projects closest to this call",
                                       p["archetype"], p.get("funding") or {}, "en", "Source: CORDIS open data (European Commission). Elaboration: Ullswater Investments."),
                            "Infographic 3 · Typical consortium in comparable funded projects."))
        orgs = p.get("orgs", [])[:10]
        if orgs:
            tr = "".join(f'<tr><td><b>{e(o["name"].title() if o["name"].isupper() else o["name"])}</b></td><td>{e(o.get("country") or "")}</td><td class="n">{o["n"]}</td><td class="n">{o["coord"]}</td></tr>' for o in orgs)
            body.append('<h3>Organisations with a track record in this topic</h3><table class="list"><tr><th>Organisation</th><th>Country</th><th>Similar projects</th><th>As coordinator</th></tr>' + tr + "</table>")
        es = p.get("orgs_es", [])[:6]
        if es:
            body.append("<h3>Spanish organisations with experience in this field</h3><ul>" + "".join(f'<li>{e(o["name"].title() if o["name"].isupper() else o["name"])} ({o["n"]} similar projects)</li>' for o in es) + "</ul>")
        sim = p.get("similar", [])[:6]
        if sim:
            body.append("<h3>Most similar funded projects</h3><ul>" + "".join(f'<li><b>{e(s["acronym"])}</b> – {e(cut(s["title"].capitalize() if s["title"].isupper() else s["title"], 110))} ({e(s["fp"])}, {s["year"]})</li>' for s in sim) + "</ul>")
        n += 1

    # Next steps + help
    body.append(f"<h2>{n}. Next steps</h2><ul>"
                "<li>Read the topic conditions and the general annexes (eligibility, admissibility, evaluation criteria and thresholds).</li>"
                "<li>Check that your organisation and partners are eligible and register a PIC in the Funding &amp; Tenders Portal.</li>"
                "<li>Define the consortium and the role of each partner; use the partner-search tools on the call page.</li>"
                "<li>Prepare a concept note (objectives, impact, work packages, budget) and validate it with an expert before writing.</li></ul>")
    body.append(help_box("en", page_url))
    body.append(f'<p class="src"><b>Sources:</b> European Commission, Funding &amp; Tenders Portal ({e(c["url"])}); '
                f'{"CORDIS open data; " if show else ""}Ullswater Investments call page ({e(page_url)}).</p>')
    html = document(lang, c["title"], f"Funding factsheet · {prog}", lead, cover_rows, "".join(body),
                    f"Funding factsheet · {ident}", f"data as of {fdate(today)}")
    return html


# ------------------------------------------------------------------ Spanish calls (BDNS)
def es_ficha(c, x=None, today=None):
    if x and x.get("data"):
        return es_ficha_full(c, x, today)
    lang = "es"
    d = c.get("detail") or {}
    region = c.get("region") or ""
    cover_rows = [("Organismo convocante", e(c.get("body"))), ("Ámbito", e("Estatal" if c.get("level") == "State" else f"Autonómico · {region}")),
                  ("Código BDNS", e(c["id"]))]
    if c.get("start"): cover_rows.append(("Inicio de solicitudes", fdate(c["start"], lang)))
    if c.get("end"): cover_rows.append(("Fin de solicitudes", f"<b>{fdate(c['end'], lang)}</b>"))
    elif d.get("startText"): cover_rows.append(("Plazo", e(d["startText"])))
    if c.get("budget"): cover_rows.append(("Presupuesto total", money(c["budget"], lang)))
    if c.get("beneficiaries"): cover_rows.append(("Beneficiarios", e(", ".join(c["beneficiaries"]))))
    lead = e(f"{c.get('body', '')} · {('convocatoria estatal' if c.get('level') == 'State' else 'convocatoria autonómica de ' + region)} · {d.get('type') or 'subvención'}")

    status = "Abierta" if c.get("open") else "Próxima"
    cards = [(date.fromisoformat(c["end"]).strftime("%d/%m/%Y") if c.get("end") else "Por confirmar", "Fin de solicitudes", [d.get("startText") or (f"Desde el {fdate(c['start'], lang)}" if c.get("start") else "")], True),
             (money(c["budget"], lang) if c.get("budget") else "n/d", "Presupuesto total", ["Crédito de la convocatoria"], False),
             (status, "Estado", [f"Publicada el {fdate(c['published'], lang)}" if c.get("published") else ""], False)]
    if d.get("instrument"):
        cards.append(((d["instrument"].split()[0] or "Ayuda").capitalize(), "Instrumento", [d["instrument"].capitalize()], False))
    if d.get("type"):
        cards.append(("Competitiva" if "competitiva" in d["type"].lower() else "Directa/otra", "Procedimiento", [d["type"]], False))
    if d.get("stateAid") or d.get("regulation"):
        cards.append((d.get("stateAid") or "RGEC/minimis", "Ayudas de Estado", [d.get("regulation") or ""], False))
    k1 = kpi_panel("Las cifras clave de la convocatoria", cut(c["title"], 95), cards,
                   f"Solicitud por la sede electrónica del organismo{' hasta el ' + fdate(c['end'], lang) if c.get('end') else ''}",
                   "Compruebe la hora límite y los requisitos en las bases y la convocatoria oficiales",
                   "Fuente: Base de Datos Nacional de Subvenciones (BDNS, IGAE). Elaboración: Ullswater Investments.")

    rows = [("Título", e(c["title"]))]
    if d.get("titleCo"): rows.append(("Título en lengua cooficial", e(d["titleCo"])))
    rows += [("Organismo", e(c.get("body"))), ("Nivel", e("Estado" if c.get("level") == "State" else "Comunidad autónoma")), ("Región", e(region))]
    for k, lab in (("type", "Tipo de convocatoria"), ("instrument", "Instrumento"), ("finalidad", "Finalidad")):
        if d.get(k): rows.append((lab, e(d[k])))
    if c.get("beneficiaries"): rows.append(("Tipos de beneficiario", e("; ".join(c["beneficiaries"]))))
    if d.get("sectors"): rows.append(("Sectores", e("; ".join(d["sectors"][:4]))))
    if d.get("regions"): rows.append(("Regiones de impacto", e("; ".join(d["regions"][:4]))))
    if c.get("budget"): rows.append(("Presupuesto total", money(c["budget"], lang)))
    if c.get("funds"): rows.append(("Fondos europeos", e(", ".join(c["funds"]))))
    if c.get("mrr"): rows.append(("Plan de Recuperación (MRR)", "Sí"))
    if d.get("regulation"): rows.append(("Reglamento de ayudas", e(d["regulation"])))
    if d.get("objectives"): rows.append(("Objetivo (ayudas de Estado)", e("; ".join(d["objectives"]))))
    if d.get("stateAid"): rows.append(("Referencia ayuda de Estado", e(d["stateAid"])))
    body = ["<h2>1. Ficha resumen</h2>", fig(k1, "Infografía 1 · Cifras clave de la convocatoria."),
            '<table class="kv">' + "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows) + "</table>"]

    n = 2
    pts, phases = [], []
    if c.get("published"): pts.append((c["published"], ["Publicación", fdate(c["published"], lang)], False))
    if c.get("start"): pts.append((c["start"], ["Inicio", fdate(c["start"], lang)], False))
    if c.get("end"):
        pts.append((c["end"], ["Cierre", fdate(c["end"], lang)], True))
        if c.get("start"):
            phases.append((c["start"], c["end"], "Plazo de solicitud", NAVY, "#FFFFFF"))
    if len(pts) >= 2:
        body.append(f"<h2>{n}. Calendario</h2>")
        body.append(fig(timeline("Plazos de la convocatoria", "Fechas según la BDNS; la resolución y la ejecución dependen de las bases",
                                 sorted(pts), phases, ("Prepare la solicitud con antelación: la documentación técnica y económica suele ser extensa",
                                                       "Nada iniciado antes de solicitar suele ser subvencionable (efecto incentivador)"),
                                 "Fuente: BDNS. Elaboración: Ullswater Investments."), "Infografía 2 · Calendario de la convocatoria."))
        n += 1

    docs = []
    if d.get("basesUrl") or d.get("basesTitle"):
        docs.append(("Bases reguladoras", d.get("basesTitle") or "", d.get("basesUrl") or ""))
    for a in d.get("announcements", [])[:3]:
        docs.append((f"Publicación en {a.get('diario') or 'diario oficial'}" + (f" ({fdate(a['date'], lang)})" if a.get("date") else ""), "Extracto/convocatoria", a.get("url") or ""))
    docs.append(("Ficha oficial BDNS", f"Convocatoria {c['id']}", c.get("bdns") or ""))
    if c.get("url"): docs.append(("Sede electrónica", "Trámite de solicitud", c["url"]))
    body.append(f"<h2>{n}. Documentos oficiales</h2><table class=\"list\"><tr><th>Documento</th><th>Detalle</th></tr>" +
                "".join(f'<tr><td><b>{e(a)}</b></td><td>{e(b)}{"<br><span class=src>" + e(u) + "</span>" if u else ""}</td></tr>' for a, b, u in docs) + "</table>")
    n += 1
    body.append(f"<h2>{n}. Próximos pasos</h2><ul>"
                "<li>Lea las bases reguladoras y la convocatoria completas: requisitos, gastos subvencionables, intensidad y criterios de valoración.</li>"
                "<li>Compruebe que su entidad cumple los requisitos (tamaño, ubicación, estar al corriente con Hacienda y la Seguridad Social).</li>"
                "<li>Verifique que el proyecto no se ha iniciado antes de presentar la solicitud y prepare la memoria y el presupuesto.</li>"
                "<li>Disponga de certificado digital del representante legal para la presentación electrónica.</li></ul>")
    body.append(help_box("es", f"{CALLS}/spain/"))
    body.append('<p class="src"><b>Fuentes:</b> Sistema Nacional de Publicidad de Subvenciones y Ayudas Públicas (BDNS, IGAE), API pública; '
                f'{e(c.get("bdns") or "")}. Los datos pueden ser corregidos por el organismo convocante: consulte siempre la convocatoria oficial.</p>')
    return document(lang, c["title"], f"Ficha de ayuda · {'España' if c.get('level') == 'State' else region} · BDNS {c['id']}", lead, cover_rows,
                    "".join(body), f"Ficha de ayuda · BDNS {c['id']}", f"datos a {fdate(today, lang)}")


# ------------------------------------------------------------------ Spanish calls: full factsheet from the official text
def bars_chart(title, sub, rows, unit, band_main, band_sub, source, max_value=None):
    """Horizontal bars: rows = [(label, value)]; the largest value is the accent."""
    b = head(title, sub)
    rows = rows[:14]
    mx = max_value or max(v for _, v in rows) or 1
    top = max(v for _, v in rows)
    lab_w, bar_x, bar_w = 300, 330, 330
    y = 92
    for lab, v in rows:
        lines_ = wrap(lab, 48)[:2]
        h = 16 + 13 * (len(lines_) - 1)
        b += tl(24, y + 12, lines_, 10.5, 600 if v == top else 400, NAVY if v == top else INK, 13)
        b += f'<rect x="{bar_x}" y="{y + 1}" width="{bar_w}" height="14" rx="4" fill="{LIGHT}"/>'
        b += f'<rect x="{bar_x}" y="{y + 1}" width="{max(bar_w * v / mx, 3):.1f}" height="14" rx="4" fill="{NAVY if v == top else "#9AA1B1"}"/>'
        val = f"{v:g}{unit}"
        b += t(bar_x + bar_w + 12, y + 13, val.replace(".", ","), 11.5, 700, NAVY if v == top else INK)
        y += h + 12
    y += 6
    b += band(y, band_main, band_sub)
    b += t(24, y + 64, source, 9, 400, GREY)
    return svg(y + 74, b)


def es_ficha_full(c, x, today):
    lang = "es"
    d, X = c.get("detail") or {}, x["data"]
    q, pl = X.get("cuantia") or {}, X.get("plazos") or {}
    region = c.get("region") or ""
    end = pl.get("solicitud_fin") or c.get("end")
    start = pl.get("solicitud_inicio") or c.get("start")
    budget = q.get("presupuesto_total") or c.get("budget")
    ints = [i for i in q.get("intensidad") or [] if isinstance(i.get("porcentaje"), (int, float)) and 0 < i["porcentaje"] <= 100]
    irange = ""
    if ints:
        lo, hi = min(i["porcentaje"] for i in ints), max(i["porcentaje"] for i in ints)
        irange = f"{lo:g} %" if lo == hi else f"{lo:g}–{hi:g} %"

    def money_es(v):
        return money(v, "es") if v else ""
    cover_rows = [("Organismo convocante", e(c.get("body"))), ("Ámbito", e("Estatal" if c.get("level") == "State" else f"Autonómico · {region}")),
                  ("Código BDNS", e(c["id"]))]
    if end: cover_rows.append(("Fin de solicitudes", f"<b>{fdate(end, lang)}</b>" + (f" · {e(pl['hora_fin'])}" if pl.get("hora_fin") else "")))
    if budget: cover_rows.append(("Presupuesto total", money_es(budget)))
    if q.get("importe_maximo"): cover_rows.append(("Ayuda máxima", money_es(q["importe_maximo"])))
    if irange: cover_rows.append(("Intensidad", irange + " del gasto subvencionable"))
    if X.get("beneficiarios"): cover_rows.append(("Quién puede pedirla", e(cut("; ".join(X["beneficiarios"]), 220))))
    lead = e(cut(X.get("resumen") or "", 300))

    # 1. Ficha resumen
    cards = [(date.fromisoformat(end).strftime("%d/%m/%Y") if end and re.match(r"\d{4}-\d\d-\d\d$", end) else "Ver bases", "Fin de solicitudes",
              [pl.get("hora_fin") or (f"Desde el {fdate(start, lang)}" if start else "")], True),
             (money_es(budget) or "n/d", "Presupuesto total", [f"{len(q['lineas'])} líneas o categorías" if q.get("lineas") else "Crédito de la convocatoria"], False),
             (money_es(q.get("importe_maximo")) or "Según bases", "Ayuda máxima", ["Por beneficiario o proyecto"] + ([f"Mínimo {money_es(q['importe_minimo'])}"] if q.get("importe_minimo") else []), False),
             (irange or "Ver bases", "Intensidad de ayuda", ["Sobre el gasto subvencionable"], False)]
    if pl.get("ejecucion_meses"):
        cards.append((f"{pl['ejecucion_meses']:g} meses", "Plazo de ejecución", [cut(pl.get("ejecucion") or "", 60)], False))
    elif pl.get("ejecucion"):
        cards.append(("Ejecución", "Plazo de ejecución", [cut(pl["ejecucion"], 60)], False))
    if X.get("puntuacion_minima"):
        cards.append((f"{X['puntuacion_minima']:g} pts", "Puntuación mínima", [cut(X.get("procedimiento") or "Concurrencia competitiva", 60)], False))
    elif X.get("procedimiento"):
        cards.append(("Competitiva" if "competitiva" in X["procedimiento"].lower() else "Procedimiento", "Procedimiento", [cut(X["procedimiento"], 60)], False))
    k1 = kpi_panel("Las cifras clave de la convocatoria", cut(c["title"], 95), cards[:6],
                   f"Solicitud{' hasta el ' + fdate(end, lang) if end else ''}" + (f" · {cut(X.get('presentacion') or '', 70)}" if X.get("presentacion") else ""),
                   "Compruebe la hora límite y los requisitos en la convocatoria oficial",
                   f"Fuente: {x.get('docName') or 'convocatoria oficial'} (BDNS {c['id']}). Elaboración: Ullswater Investments.")
    rows = [("Organismo", e(c.get("body"))), ("Ámbito", e("Estado" if c.get("level") == "State" else f"Comunidad autónoma · {region}"))]
    if d.get("type") or X.get("procedimiento"): rows.append(("Procedimiento", e(X.get("procedimiento") or d.get("type"))))
    if d.get("instrument"): rows.append(("Instrumento", e(d["instrument"])))
    if budget: rows.append(("Presupuesto", money_es(budget)))
    if q.get("importe_maximo"): rows.append(("Ayuda máxima", money_es(q["importe_maximo"])))
    if q.get("inversion_minima"): rows.append(("Proyecto o inversión mínima", money_es(q["inversion_minima"])))
    if irange: rows.append(("Intensidad", irange))
    if start: rows.append(("Inicio de solicitudes", fdate(start, lang) if re.match(r"\d{4}-\d\d-\d\d$", start) else e(start)))
    if end: rows.append(("Fin de solicitudes", (fdate(end, lang) if re.match(r"\d{4}-\d\d-\d\d$", end) else e(end)) + (f" · {e(pl['hora_fin'])}" if pl.get("hora_fin") else "")))
    for k_, lab in (("ejecucion", "Ejecución"), ("justificacion", "Justificación"), ("resolucion", "Resolución")):
        if pl.get(k_): rows.append((lab, e(pl[k_])))
    if X.get("regimen") or d.get("regulation"): rows.append(("Marco de ayudas de Estado", e(X.get("regimen") or d.get("regulation"))))
    if d.get("stateAid"): rows.append(("Referencia ayuda de Estado", e(d["stateAid"])))
    if c.get("mrr"): rows.append(("Plan de Recuperación (MRR)", "Sí"))
    if c.get("funds"): rows.append(("Fondos europeos", e(", ".join(c["funds"]))))
    body = ["<h2>1. Ficha resumen</h2>"]
    if X.get("resumen"): body.append(f"<p>{e(X['resumen'])}</p>")
    body += [fig(k1, "Infografía 1 · Cifras clave de la convocatoria."),
             '<table class="kv">' + "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows) + "</table>"]
    n = 2

    def ul(items_):
        return "<ul>" + "".join(f"<li>{e(i)}</li>" for i in items_) + "</ul>"
    # 2. Objeto y actuaciones
    if X.get("objeto") or X.get("actuaciones"):
        body.append(f"<h2>{n}. Qué financia</h2>")
        if X.get("objeto"): body.append(f"<p>{e(X['objeto'])}</p>")
        if X.get("actuaciones"): body.append("<h3>Actuaciones subvencionables</h3>" + ul(X["actuaciones"]))
        n += 1
    # 3. Beneficiarios
    if X.get("beneficiarios") or X.get("requisitos"):
        body.append(f"<h2>{n}. Beneficiarios y requisitos</h2>")
        if X.get("beneficiarios"): body.append("<h3>Quién puede solicitarla</h3>" + ul(X["beneficiarios"]))
        if X.get("requisitos"): body.append("<h3>Requisitos</h3>" + ul(X["requisitos"]))
        n += 1
    # 4. Gastos
    if X.get("gastos") or X.get("excluidos"):
        body.append(f"<h2>{n}. Gastos subvencionables</h2>")
        if X.get("gastos"):
            body.append('<table class="list"><tr><th>Partida</th><th>Condiciones</th></tr>' +
                        "".join(f"<tr><td><b>{e(g.get('partida'))}</b></td><td>{e(g.get('condiciones') or '')}</td></tr>" for g in X["gastos"][:16]) + "</table>")
        if X.get("excluidos"): body.append("<h3>No subvencionable</h3>" + ul(X["excluidos"]))
        n += 1
    # 5. Cuantía
    if ints or q.get("lineas") or q.get("notas"):
        body.append(f"<h2>{n}. Cuantía e intensidad</h2>")
        if q.get("notas"): body.append(f"<p>{e(q['notas'])}</p>")
        if len(ints) >= 2:
            body.append(fig(bars_chart("Porcentaje máximo de ayuda", "Intensidad sobre el gasto subvencionable, según la convocatoria",
                                       [(i["categoria"], i["porcentaje"]) for i in ints], " %",
                                       f"Ayuda máxima: {money_es(q.get('importe_maximo')) or 'según bases'}" + (f" · presupuesto total {money_es(budget)}" if budget else ""),
                                       "La intensidad efectiva depende del tamaño de la empresa y del gasto finalmente justificado",
                                       "Fuente: convocatoria oficial. Elaboración: Ullswater Investments.", 100),
                            "Infografía 2 · Intensidad de la ayuda."))
        elif ints:
            body.append(f"<p><b>Intensidad:</b> {e(ints[0]['categoria'])} – {ints[0]['porcentaje']:g} %.</p>")
        if q.get("lineas"):
            body.append('<table class="list"><tr><th>Línea o categoría</th><th>Dotación</th></tr>' +
                        "".join(f"<tr><td>{e(l_.get('nombre'))}</td><td class='n'>{money_es(l_.get('importe')) or '–'}</td></tr>" for l_ in q["lineas"][:10]) + "</table>")
        n += 1
    # 6. Criterios
    crit = [cr for cr in X.get("criterios") or [] if cr.get("criterio")]
    if crit:
        body.append(f"<h2>{n}. Criterios de valoración</h2>")
        scored = [(cr["criterio"], cr["puntos"]) for cr in crit if isinstance(cr.get("puntos"), (int, float)) and cr["puntos"] > 0]
        total = sum(v for _, v in scored)
        if len(scored) >= 2:
            body.append(fig(bars_chart("Dónde se gana la puntuación", f"Puntuación máxima por criterio{f' (total {total:g} puntos)' if total else ''}",
                                       scored, " pts",
                                       f"Puntuación mínima: {X['puntuacion_minima']:g} puntos" if X.get("puntuacion_minima") else "Concentre el esfuerzo en los criterios de más peso",
                                       "Los criterios y su detalle completo están en la convocatoria oficial",
                                       "Fuente: convocatoria oficial. Elaboración: Ullswater Investments."),
                            "Infografía 3 · Peso de los criterios de valoración."))
        else:
            body.append(ul([cr["criterio"] + (f" ({cr['puntos']:g} puntos)" if isinstance(cr.get("puntos"), (int, float)) else "") for cr in crit]))
        n += 1
    # 7. Calendario
    pts, phases = [], []
    if c.get("published"): pts.append((c["published"], ["Publicación", fdate(c["published"], lang)], False))
    if start and re.match(r"\d{4}-\d\d-\d\d$", start): pts.append((start, ["Inicio", fdate(start, lang)], False))
    if end and re.match(r"\d{4}-\d\d-\d\d$", end):
        pts.append((end, ["Cierre", fdate(end, lang)], True))
        if start and re.match(r"\d{4}-\d\d-\d\d$", start) and start < end:
            phases.append((start, end, "Plazo de solicitud", NAVY, "#FFFFFF"))
    if len(pts) >= 2:
        body.append(f"<h2>{n}. Calendario</h2>")
        note2 = cut(f"Ejecución: {pl['ejecucion']}", 110) if pl.get("ejecucion") else "Nada iniciado antes de solicitar suele ser subvencionable (efecto incentivador)"
        body.append(fig(timeline("Plazos de la convocatoria", "Fechas de solicitud según la convocatoria y la BDNS", sorted(pts), phases,
                                 ("Prepare la solicitud con antelación: memoria, presupuesto y declaraciones suelen ser extensas", note2),
                                 "Fuente: convocatoria oficial y BDNS. Elaboración: Ullswater Investments."), "Infografía 4 · Calendario de la convocatoria."))
        n += 1
    # 8. Solicitud, pago y justificación
    if X.get("documentacion") or X.get("pago") or X.get("justificacion") or X.get("presentacion"):
        body.append(f"<h2>{n}. Solicitud, pago y justificación</h2>")
        if X.get("presentacion"): body.append(f"<p><b>Presentación:</b> {e(X['presentacion'])}</p>")
        if X.get("documentacion"): body.append("<h3>Documentación de la solicitud</h3><ol>" + "".join(f"<li>{e(i)}</li>" for i in X["documentacion"][:14]) + "</ol>")
        if X.get("pago"): body.append(f"<p><b>Pago:</b> {e(X['pago'])}</p>")
        if X.get("justificacion"): body.append(f"<p><b>Justificación:</b> {e(X['justificacion'])}</p>")
        if X.get("obligaciones"): body.append("<h3>Obligaciones principales</h3>" + ul(X["obligaciones"][:10]))
        if X.get("compatibilidad"): body.append(f"<p><b>Compatibilidad:</b> {e(X['compatibilidad'])}</p>")
        n += 1
    if X.get("atencion"):
        body.append('<div class="callout"><b class="t">Puntos de atención de Ullswater</b>' + ul(X["atencion"][:6]) + "</div>")
    # 9. Documentos
    docs = []
    if d.get("basesUrl") or d.get("basesTitle"): docs.append(("Bases reguladoras", d.get("basesTitle") or "", d.get("basesUrl") or ""))
    for a in d.get("announcements", [])[:3]:
        docs.append((f"Publicación en {a.get('diario') or 'diario oficial'}" + (f" ({fdate(a['date'], lang)})" if a.get("date") else ""), "Convocatoria / extracto", a.get("url") or ""))
    docs.append(("Ficha oficial BDNS", f"Convocatoria {c['id']}", c.get("bdns") or ""))
    if c.get("url"): docs.append(("Sede electrónica", "Trámite de solicitud", c["url"]))
    body.append(f"<div class=\"keep\"><h2>{n}. Documentos oficiales</h2><table class=\"list\"><tr><th>Documento</th><th>Detalle</th></tr>" +
                "".join(f'<tr><td><b>{e(a)}</b></td><td>{e(b)}{"<br><span class=src>" + e(u) + "</span>" if u else ""}</td></tr>' for a, b, u in docs) + "</table></div>")
    body.append(help_box("es", f"{CALLS}/spain/"))
    body.append(f'<p class="src"><b>Fuentes:</b> {e(x.get("docName") or "texto oficial de la convocatoria")} publicado en la BDNS ({e(c.get("bdns") or "")}); '
                'Sistema Nacional de Publicidad de Subvenciones y Ayudas Públicas (IGAE).</p>'
                f'<p class="disc">Contenido extraído del texto oficial de la convocatoria con ayuda de inteligencia artificial ({e(fdate(x.get("extracted"), lang))}). '
                'Puede contener omisiones: la convocatoria y las bases reguladoras oficiales prevalecen siempre.</p>')
    return document(lang, c["title"], f"Ficha de ayuda · {'España' if c.get('level') == 'State' else region} · BDNS {c['id']}", lead, cover_rows,
                    "".join(body), f"Ficha de ayuda · BDNS {c['id']}", f"datos a {fdate(today, lang)}")


# ------------------------------------------------------------------ build
def render(html):
    from weasyprint import HTML
    return HTML(string=html, base_url=str(ASSETS)).write_pdf()


PREVIEW_PAGES = 2


def previews(pdf, sl, fp):
    """JPEG images of the first pages (cached by the PDF fingerprint). Returns (number of preview pages, total pages)."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf)
    total, n = len(doc), min(PREVIEW_PAGES, len(doc))
    (OUT / "p").mkdir(parents=True, exist_ok=True)
    for i in range(n):
        cached = CACHE / f"{sl}.{fp}.p{i + 1}.jpg"
        if not cached.exists():
            for old in CACHE.glob(f"{sl}.*.p{i + 1}.jpg"):
                old.unlink()
            img = doc[i].render(scale=1.5).to_pil().convert("RGB")  # A4 -> ~890 x 1260 px
            img.save(cached, "JPEG", quality=78, optimize=True, progressive=True)
        (OUT / "p" / f"{sl}-{i + 1}.jpg").write_bytes(cached.read_bytes())
    doc.close()
    return n, total


def encrypt(pdf, key):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import hmac as _h
    nonce = _h.new(key, pdf, hashlib.sha256).digest()[:12]  # deterministic per content: unchanged PDFs give identical files
    return nonce + AESGCM(key).encrypt(nonce, pdf, None)


def items():
    data = json.loads((SITE / "data" / "calls.json").read_text(encoding="utf-8"))
    calls = data["calls"]
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        import enrich
        enrich.apply(calls)
    except Exception as ex:
        print(f"  enrich skipped: {ex}")
    tfile, pfile = ROOT / "data" / "topic_text.json", ROOT / "data" / "partners.json"
    texts = json.loads(tfile.read_text(encoding="utf-8")) if tfile.exists() else {}
    partners = json.loads(pfile.read_text(encoding="utf-8")) if pfile.exists() else {}
    for c in calls:
        yield "eu", c["id"], slug(c["id"]), (c, partners.get(c["id"]), texts.get(c["id"], ""))
    sfile, xfile = SITE / "data" / "spain.json", SITE / "data" / "spain_x.json"
    extracts = json.loads(xfile.read_text(encoding="utf-8")) if xfile.exists() else {}
    if sfile.exists():
        for c in json.loads(sfile.read_text(encoding="utf-8")).get("calls", []):
            yield "es", c["id"], "bdns-" + slug(c["id"]), (c, extracts.get(c["id"]))


def build(only=None, preview=False):
    key_b64 = os.environ.get("FICHAS_KEY", "")
    key = base64.b64decode(key_b64) if key_b64 else None
    if not key and not preview:
        print("  FICHAS_KEY not set: only the public preview (pages 1-2) is published; set the secret to enable PDF downloads.")
    if key and len(key) != 32:
        raise SystemExit("FICHAS_KEY must be 32 bytes, base64-encoded")
    today = date.today().isoformat()
    tpl = hashlib.sha256((Path(__file__).read_text(encoding="utf-8") + VERSION).encode()).hexdigest()[:12]
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / "preview").mkdir(exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    index, made, reused = {}, 0, 0
    for kind, cid, sl, args in items():
        if only and cid not in only:
            continue
        fp = hashlib.sha256((tpl + json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)).encode()).hexdigest()[:20]
        cached = CACHE / f"{sl}.{fp}.pdf"
        if cached.exists():
            pdf = cached.read_bytes()
            reused += 1
        else:
            for old in CACHE.glob(f"{sl}.*.pdf"):
                old.unlink()
            html = eu_ficha(*args, today) if kind == "eu" else es_ficha(*args, today=today)
            try:
                pdf = render(html)
            except Exception as ex:
                print(f"  ! {cid}: {ex}")
                continue
            cached.write_bytes(pdf)
            made += 1
        if preview:
            (CACHE / "preview" / f"{sl}.pdf").write_bytes(pdf)
        if key:
            (OUT / f"{sl}.bin").write_bytes(encrypt(pdf, key))
        try:
            pv, pages = previews(pdf, sl, fp)
        except Exception as ex:
            print(f"  ! preview {cid}: {ex}")
            pv, pages = 0, 0
        index[cid] = {"f": sl, "k": kind, "kb": round(len(pdf) / 1024), "pg": pages, "pv": pv, "dl": 1 if key else 0}
    (OUT / "index.json").write_text(json.dumps({"updated": today, "fichas": index}, separators=(",", ":")), encoding="utf-8")
    print(f"  factsheets: {len(index)} ({made} rendered, {reused} from cache){' · preview in .cache/fichas/preview' if preview else ''}")


if __name__ == "__main__":
    args = sys.argv[1:]
    pv = "--preview" in args
    ids = [a for a in args if not a.startswith("--")]
    build(set(ids) if ids else None, preview=pv)
