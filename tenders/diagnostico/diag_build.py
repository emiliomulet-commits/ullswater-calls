"""Free tender diagnosis pages: /es/espana/licitacion/<id>/diagnostico/ for every ficha with a rule sheet (reglas.json).
Called from build_spain.build_fichas. The page is static: the questions, the calculator (engine.js) and the report (ui.js)
run in the visitor's browser; only the name, company, email and a summary go to the Worker when they ask for the full report."""
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
AWARDS = ROOT / ".cache" / "tenders" / "awards_out"  # written by tenders/awards_spain.py (aggregates only)
BOOK = "https://outlook.office.com/bookwithme/user/e458fce3fc324c73bf552650547cf141@ullswaterinvestments.com/meetingtype/nBIRMB9DAUGZ7TZQg15B-A2?anonymous"
API = "https://ullswater-ai.emilio-mulet-b52.workers.dev/diagnostico"
PRIVACY = "https://www.ullswaterinvestments.com/es/privacy/"
MIN_SAMPLES = 10  # fewer comparable tenders than this → keep the engine's illustrative default


def diag_path(i):
    return f"/es/espana/licitacion/{i}/diagnostico/"


def has_rules(fichas_dir, i):
    return (Path(fichas_dir) / i / "reglas.json").exists()


def competition(rules):
    """Best available competition model for this tender: same buyer + CPV group, then province + CPV group, then CPV group."""
    f = AWARDS / "competencia.json"
    if not f.exists():
        return None
    try:
        agg = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return None
    cpv3 = str(rules.get("cpv") or "")[:3]
    tries = [("órgano", f"{rules.get('buyer_key') or rules.get('buyer')}|{cpv3}", "el mismo órgano de contratación"),
             ("provincia", f"{rules.get('province')}|{cpv3}", "la misma provincia"),
             ("cpv", cpv3, "toda España")]
    for level, key, where in tries:
        c = (agg.get(level) or {}).get(key)
        if c and c.get("samples", 0) >= MIN_SAMPLES:
            return dict(c, level=level, source=f"{c['samples']} licitaciones adjudicadas de este tipo de servicio en {where} "
                        f"({c.get('from', '')}–{c.get('to', '')}), datos abiertos de la Plataforma de Contratación del Sector Público.")
    return None


def publish_assets(site):
    (site / "assets").mkdir(parents=True, exist_ok=True)
    js = (HERE / "engine.js").read_text(encoding="utf-8") + "\n" + (HERE / "ui.js").read_text(encoding="utf-8")
    (site / "assets" / "diagnostico.js").write_text(js, encoding="utf-8")
    (site / "assets" / "diagnostico.css").write_text((HERE / "diag.css").read_text(encoding="utf-8"), encoding="utf-8")
    src = AWARDS / "adjudicatarios"
    if src.exists():
        dst = site / "data" / "es" / "adjudicatarios"
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst)


def check(i):
    """Automatic consistency check of the rule sheet (check.js). False = do not publish the diagnosis."""
    import subprocess
    try:
        r = subprocess.run(["node", str(HERE / "check.js"), i], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"  diagnóstico {i}: no se pudo comprobar ({e}); se publica igualmente")
        return True
    print("  " + (r.stdout or r.stderr).strip())
    return r.returncode == 0


def build(write, page, ctx, fichas_dir, i, ficha, ficha_url):
    """Writes the page; returns False (and writes nothing) when the rule sheet fails the automatic check."""
    if not check(i):
        return False
    rules = json.loads((Path(fichas_dir) / i / "reglas.json").read_text(encoding="utf-8"))
    comp = competition(rules)
    cfg = {"rules": rules, "comp": comp, "ficha": ficha_url, "book": BOOK, "api": API, "privacy": PRIVACY}
    cfg_js = json.dumps(cfg, ensure_ascii=False).replace("</", "<\\/")
    qs = ["¿Qué pasa si oferto un precio muy bajo?", "¿Cómo acredito la experiencia del equipo?", "¿Puedo ir en UTE o con otra empresa?", "¿Qué es el DEUC?"]
    ask = ctx["ask"]("es", qs, "Ej.: ¿qué cuenta como trabajo similar?") if ctx.get("ask") else ""
    head = (f'<div class="crumbs"><a href="/es/">Licitaciones</a> › <a href="/es/espana/">España</a> › <a href="{ficha_url}">Ficha</a> › Diagnóstico</div>'
            '<div class="ud-head"><p class="ud-k">Diagnóstico gratuito</p>'
            f'<h1>¿Puedes ganar esta licitación?</h1><p><b>{_e(rules["title"])}</b> · {_e(rules["buyer"])} · cierra el {_fd(rules["deadline"])}</p>'
            '<p>Responde a unas preguntas sobre tu empresa (unos 5 minutos). Te decimos si cumples los requisitos, qué puntuación puedes esperar, '
            'qué probabilidad tienes de ganar con cada rebaja y qué tienes que hacer hasta el cierre.</p></div>'
            '<p class="ud-ai">Este diagnóstico lo prepara un sistema automático con ayuda de inteligencia artificial. Las cuentas siguen las fórmulas del pliego; '
            'el resultado es orientativo y lo puede revisar un consultor de Ullswater.</p>')
    body = (f'<main><link rel="stylesheet" href="/assets/diagnostico.css"><div class="udw"><div class="ud-in">{head}'
            '<div id="udiag"><noscript><p>Activa JavaScript para hacer el diagnóstico.</p></noscript></div>'
            + (f'<section class="esp-ask no-print" style="margin-top:28px"><h2 style="font-size:19px">¿Dudas? Pregunta al asistente</h2>{ask}</section>' if ask else "")
            + f'</div></div><script>window.UDIAG_CFG={cfg_js};</script><script src="/assets/diagnostico.js" defer></script></main>')
    ld = {"@context": "https://schema.org", "@type": "WebApplication", "name": "Diagnóstico gratuito de licitación", "inLanguage": "es",
          "url": ctx["base"] + diag_path(i), "applicationCategory": "BusinessApplication", "isBasedOn": rules["official_url"],
          "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"}, "publisher": {"@type": "Organization", "name": "Ullswater Investments"}}
    write(diag_path(i), page("es", f'Diagnóstico gratuito: {rules["title"]} | Ullswater Investments',
                             f'¿Puedes ganar «{rules["title"]}»? Requisitos, puntuación, rebaja recomendada y hoja de ruta, gratis y en 5 minutos.',
                             diag_path(i), body, None, ld))
    return True


def _e(s):
    from html import escape
    return escape(str(s or ""))


def _fd(iso):
    m = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    y, mo, d = iso.split("-")
    return f"{int(d)} de {m[int(mo) - 1]} de {y}"
