"""AI factsheets for Spanish tenders: read EVERY official document of a PLACSP tender and write our ficha + diagnosis rules.

python tools/ficha_ai.py                 -> picks FICHA_N (default 10) varied open tenders from PLACSP and processes them
FICHA_IDS="123,456" python tools/ficha_ai.py  -> processes those PLACSP entry ids

For each tender it writes tenders/fichas/<id>/: index.json (documents), ficha.json (web + PDF factsheet), reglas.json
(free diagnosis, only if it passes tenders/diagnostico/check.js), ficha.pdf, ai_usage.json (tokens and cost).
The official documents are NOT stored in the repo: the ficha links to them on the Plataforma.
Same structure as the hand-made example tenders/fichas/20957771, which the model receives as the reference.
Run on GitHub Actions (PLACSP and the Claude API are not reachable from the dev container). Needs ANTHROPIC_API_KEY.
"""
import io
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import traceback
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sample_ficha as S  # noqa: E402  (feed reading and document download, already proven against PLACSP's WAF)
import ficha_render as R  # noqa: E402

EXAMPLE = ROOT / "tenders" / "fichas" / "20957771"
FICHAS = ROOT / os.environ.get("FICHA_OUT", "tenders/fichas")  # comparisons with other models go elsewhere
MODEL = os.environ.get("FICHA_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("FICHA_EFFORT", "high")
BATCH = os.environ.get("FICHA_BATCH", "") in ("1", "true", "yes")  # Message Batches API: half price, answer within hours
MAX_CHARS = int(os.environ.get("FICHA_MAX_CHARS", "520000"))  # ~150k tokens of document text per tender
PRICES = {  # $ per million tokens: input, output, cache read (cache write = 1.25 x input)
    "claude-opus-5-5": (4.0, 20.0, 0.20), "claude-sonnet-5-5": (2.0, 10.0, 0.10), "claude-haiku-5-5": (0.10, 0.50, 0.01),
}
EUR_PER_USD = float(os.environ.get("EUR_PER_USD", "0.92"))
CODE = {"Legal": "PCAP", "Technical": "PPT", "General": "ANU"}


# ---------- 1. which tenders ----------

def candidates(n):
    """Varied open tenders: every level of government, works / services / supplies, enough time to bid, with a PCAP."""
    url, picked, pages, per_type = S.FEED, [], 0, {}
    cap = max(1, math.ceil(n / 3))
    seen_buyers = set()
    vmin = float(os.environ.get("FICHA_MIN_VALUE") or 0)  # scale mode: every open tender from this amount up, no variety rule
    vmax = float("inf") if vmin else 20_000_000
    vmin = vmin or 40_000
    scale = bool(os.environ.get("FICHA_MIN_VALUE"))
    min_days = int(os.environ.get("FICHA_MIN_DAYS") or 10)
    while url and pages < (400 if scale else 25) and len(picked) < n:
        raw, _, _ = S.get(url); pages += 1
        root = ET.fromstring(raw)
        for entry in (e for e in root if S.local(e.tag) == "entry"):
            cfs = next((e for e in entry if S.local(e.tag) == "ContractFolderStatus"), None)
            if cfs is None or S.first(cfs, "ContractFolderStatusCode") != "PUB":
                continue
            eid = S.first(entry, "id").rsplit("/", 1)[-1]
            if (ROOT / "tenders" / "fichas" / eid / "ficha.json").exists():
                continue
            dl = S.first(cfs, "EndDate")[:10]
            if not dl or dl < (date.today() + timedelta(days=min_days)).isoformat():
                continue
            ds = S.docs_of(cfs)
            if "Legal" not in {d["kind"] for d in ds}:
                continue
            try:
                v = float(S.first(cfs, "TaxExclusiveAmount") or 0)
            except ValueError:
                v = 0
            if not vmin <= v <= vmax:
                continue
            tc, buyer = S.first(cfs, "TypeCode"), S.buyer_of(cfs)
            if not scale and (per_type.get(tc, 0) >= cap or buyer in seen_buyers):
                continue
            per_type[tc] = per_type.get(tc, 0) + 1
            seen_buyers.add(buyer)
            picked.append((eid, entry, cfs, ds))
            print("picked", eid, tc, round(v), buyer[:60], flush=True)
            if len(picked) >= n:
                break
        url = next((l.get("href") for l in root if S.local(l.tag) == "link" and l.get("rel") == "next"), None)
    return picked


def by_ids(ids):
    want, found, url, pages = set(ids), [], S.FEED, 0
    while url and want and pages < 60:
        raw, _, _ = S.get(url); pages += 1
        root = ET.fromstring(raw)
        for entry in (e for e in root if S.local(e.tag) == "entry"):
            eid = S.first(entry, "id").rsplit("/", 1)[-1]
            if eid in want:
                cfs = next(e for e in entry if S.local(e.tag) == "ContractFolderStatus")
                found.append((eid, entry, cfs, S.docs_of(cfs))); want.discard(eid)
        url = next((l.get("href") for l in root if S.local(l.tag) == "link" and l.get("rel") == "next"), None)
    if want:
        print("not found in the feed:", ", ".join(sorted(want)))
    return found


# ---------- 2. documents -> text with page numbers ----------

def pdf_pages(data):
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / "d.pdf"
        p.write_bytes(data)
        out = subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True).stdout.decode("utf-8", "replace")
    pages = out.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return pages


def office_text(data):
    """.odt / .docx: plain text of the XML (no page numbers: cited as page 1)."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        name = "content.xml" if "content.xml" in z.namelist() else "word/document.xml" if "word/document.xml" in z.namelist() else None
        if not name:
            return None
        x = z.read(name).decode("utf-8", "replace")
        x = re.sub(r"</(text:p|w:p|text:h)>", "\n", x)
        return re.sub(r"[ \t]+", " ", re.sub(r"<[^>]+>", "", x)).strip()
    except Exception:  # noqa: BLE001
        return None


def read_doc(body):
    """-> list of (sub-name, [page texts]) for one downloaded file (a zip may hold several PDFs)."""
    if body[:4] == b"%PDF":
        return [("", pdf_pages(body))]
    if body[:2] == b"PK":
        t = office_text(body)
        if t is not None:
            return [("", [t])]
        res = []
        try:
            z = zipfile.ZipFile(io.BytesIO(body))
            for m in z.namelist()[:30]:
                b = z.read(m)
                if b[:4] == b"%PDF":
                    res.append((Path(m).name, pdf_pages(b)))
                elif m.lower().endswith((".odt", ".docx")):
                    t = office_text(b)
                    if t:
                        res.append((Path(m).name, [t]))
        except Exception:  # noqa: BLE001
            pass
        return res
    return []


def fetch(eid, entry, cfs, ds):
    """Download every document of the notice. Returns index (as tenders/fichas/<id>/index.json) and the text parts."""
    pp = next((e for e in cfs if S.local(e.tag) == "ProcurementProject"), cfs)
    idx = {"id": eid, "title": S.first(pp, "Name"), "buyer": S.buyer_of(cfs),
           "link": next((l.get("href") for l in entry if S.local(l.tag) == "link"), ""), "docs": []}
    parts, counters = [], {}
    for n, doc in enumerate(ds, 1):
        try:
            body, ctype, disp = S.get(doc["uri"])
        except RuntimeError:
            doc["error"] = "download failed"; idx["docs"].append(doc); continue
        ext = "pdf" if body[:4] == b"%PDF" else "zip" if body[:2] == b"PK" else "html" if b"<html" in body[:500].lower() else "bin"
        doc.update(file=f"{n:02d}_{doc['kind']}.{ext}", bytes=len(body), content_type=ctype, disposition=disp[:200])
        m = re.search(r'filename=(?:DOC\d{14})?([^;]+)', disp or "")
        if m and not doc.get("name"):
            doc["name"] = m.group(1).strip('" ')
        if body[:5] == b"<?xml" or "xml" in (ctype or ""):
            doc["type"] = "XML"; idx["docs"].append(doc); continue  # DEUC in xml: nothing to read
        for sub, pages in read_doc(body):
            base = CODE.get(doc["kind"], "ANX")
            counters[base] = counters.get(base, 0) + 1
            code = base if counters[base] == 1 else f"{base}{counters[base]}"
            if base == "ANX" and counters[base] == 1:
                code = "ANX"
            parts.append({"code": code, "file": doc["file"], "name": (doc.get("name") or "") + (f" › {sub}" if sub else ""), "pages": pages})
            doc.setdefault("codes", []).append(code)
            if sub == "" and ext == "pdf":
                doc["pages"] = len(pages)
        doc["type"] = {"pdf": "PDF", "zip": "ZIP"}.get(ext, ext.upper())
        idx["docs"].append(doc)
        print(eid, "doc", doc["file"], len(body), doc.get("codes"), flush=True)
    return idx, parts


def doc_block(parts):
    """All the text, page by page, inside the character budget. Anything left out is listed (never silently cut)."""
    order = sorted(parts, key=lambda p: (0 if p["code"].startswith("PCAP") else 1 if p["code"].startswith("ANX") else 2 if p["code"].startswith("PPT") else 3))
    left, out, cut = MAX_CHARS, [], []
    for p in order:
        head = f'\n\n===== DOCUMENTO {p["code"]}: {p["name"]} ({len(p["pages"])} páginas) =====\n'
        out.append(head)
        for i, t in enumerate(p["pages"], 1):
            t = re.sub(r"[ \t]{3,}", "  ", t).strip()
            if len(t) > left:
                cut.append(f'{p["code"]} desde la página {i} de {len(p["pages"])}')
                out.append(f"\n[… resto de {p['code']} no incluido por tamaño …]\n")
                break
            out.append(f"\n--- [{p['code']} p.{i}] ---\n{t}")
            left -= len(t) + 20
    return "".join(out), cut


# ---------- 3. the model ----------

def system_prompt():
    ex_f = json.loads((EXAMPLE / "ficha.json").read_text(encoding="utf-8"))
    ex_r = (EXAMPLE / "reglas.json").read_text(encoding="utf-8")
    reglas_md = (ROOT / "tenders" / "diagnostico" / "REGLAS.md").read_text(encoding="utf-8")
    for k in ("files",):
        ex_f.pop(k, None)
    return f"""Eres un consultor experto en contratación pública española (LCSP 9/2017) que trabaja para Ullswater Investments.
Lees TODOS los documentos oficiales de una licitación (anuncio, pliego administrativo PCAP, pliego técnico PPT, anexos) y escribes:
1) la «ficha» que publicamos en la web y en PDF, para que el gerente de una pyme entienda en 3 minutos si le interesa y qué necesita;
2) la «hoja de reglas del diagnóstico» que usa nuestra calculadora gratuita «¿puedes ganar esta licitación?».

Responde SOLO con un objeto JSON válido (sin texto antes ni después, sin ```): {{"ficha": {{...}}, "reglas": {{...}}}}

REGLAS DE CONTENIDO (obligatorias)
- Copia importes, porcentajes, plazos y fechas EXACTOS de los pliegos. No inventes nada. Si un dato no aparece, dilo («El pliego no lo indica») y no lo supongas.
- Cada dato lleva su cita: el código del documento tal como aparece en las marcas «--- [CÓDIGO p.N] ---» y la página. En la ficha, formato «PCAP 12», «ANX 3–5», varias separadas por « · » (ej. «PCAP 9 · ANX 22»). En las reglas, formato «PCAP p.12».
- Lenguaje sencillo, frases cortas, sin jerga. Explica las siglas la primera vez. Español de España.
- La estructura experta de la ficha debe cubrir siempre (aunque sea para decir «No procede»): objeto y lotes, presupuesto base y valor estimado, IVA, duración y prórrogas, revisión de precios, modificaciones previstas, subrogación de personal (con número de trabajadores y coste si lo dan), solvencia económica y técnica (con cifras y cómo se acredita), clasificación si se exige o admite, habilitaciones, criterios de adjudicación separando los automáticos (fórmula) de los de juicio de valor con sus puntos y umbrales, fórmula del precio, baja anormal o temeraria, desempate, garantía provisional y definitiva, sobres y forma de presentación, plazo para preguntas, penalidades, forma de pago, condiciones especiales de ejecución, subcontratación, riesgos y recurso especial (art. 44 LCSP, si procede por importe).
- Si encuentras contradicciones entre documentos, ponlas en la sección «errors» y en reglas.known_issues.
- El veredicto («verdict») es nuestra lectura honesta: para qué tipo de empresa es buena oportunidad, dificultad y dónde se gana. opportunity y difficulty valen «alta», «media» o «baja».
- Nada de datos personales (nombres de técnicos o firmantes) ni nombres de empresas competidoras.

ESTRUCTURA DE LA FICHA: la misma que el ejemplo de abajo (licitación 20957771), con estas claves:
- id, ref (expediente), title (título claro en lenguaje sencillo), title_official (literal), buyer, unit, place («Ciudad (Comunidad)»), deadline («AAAA-MM-DD»), deadline_time («HH:MM»), questions_until (o null), published.
- headline (titular periodístico de menos de 70 caracteres) y headline_em (un trozo literal del headline que se resalta), lede (1–2 frases), crumbs («Licitaciones › España › <nivel en plural> › <Comunidad>»).
- docs: un objeto por código de documento citado → {{"label": nombre claro del documento}}.
- tags: exactamente las 10 claves del ejemplo (level, where, contract, sector, size, deadline, procedure, funds, lots, award), con valores cortos como en el ejemplo.
- verdict, summary (4–6 frases), max_lots_per_bidder (número; si no hay límite, el número de lotes).
- sections: en este orden y con estas key: what, lots, money, can, win, when, risk, errors.
  · items = lista de [etiqueta, texto, cita].
  · lots.lots = lista de {{"n", "label" (qué incluye, corto), "fee" (importe sin IVA, número), "months" (si se sabe), "works" (solo si es dirección de obra: importe de la obra)}}. Si no hay lotes, un único lote n=1 con el importe total. lots.note y lots.cite.
  · win.criteria = lista de {{"name", "pts" (número), "kind" («fórmula» o «juicio de valor»), "how" (cómo se reparten los puntos, con umbrales)}} que sume el total del pliego (normalmente 100). win.cite, win.items (juicio de valor, baja anormal, desempate…), win.insight (dónde se decide la adjudicación, 1–2 frases).
  · risk.groups = lista de {{"h", "items"}} (cobro, penalidades, obligaciones, personal…).
  · errors.items (puede estar vacío) y errors.advice.

ESTRUCTURA DE LAS REGLAS: sigue exactamente REGLAS.md y el ejemplo. Solo puedes usar los «kind» que existen:
requirements.kind ∈ number_vs_lot | number_min | yesno | roles_vs_lot; criteria.kind ∈ price | role_excess | choice | judgement;
abnormal.kind ∈ below_mean_pp | (el más parecido del ejemplo). Los puntos de criteria deben sumar 100, judgement_pts = suma de los de juicio de valor,
lots[].budget sin IVA y que cuadre con la ficha, deadline igual que en la ficha. Si un criterio no encaja en ningún kind, usa «choice» con opciones razonables o «judgement» y explícalo en note.

=== REGLAS.md ===
{reglas_md}

=== EJEMPLO: ficha.json de la licitación 20957771 ===
{json.dumps(ex_f, ensure_ascii=False, indent=1)}

=== EJEMPLO: reglas.json de la licitación 20957771 ===
{ex_r}
"""


def price(usage):
    if MODEL.startswith("kimi"):  # Moonshot list price, $ per million tokens (override with KIMI_PRICES="in,out,cache")
        pin, pout, pc = (float(x) for x in os.environ.get("KIMI_PRICES", "2.00,10.00,0.20").split(","))
        c = usage.get("cache_read_input_tokens", 0)
        return round(((usage.get("input_tokens", 0) - c) * pin + c * pc + usage.get("output_tokens", 0) * pout) / 1e6, 4)
    if MODEL.startswith("@cf/"):  # Workers AI: free daily allowance, then ~0.27 $/M input and 0.85 $/M output (llama-4-scout)
        return round((usage.get("input_tokens", 0) * 0.27 + usage.get("output_tokens", 0) * 0.85) / 1e6, 4)
    pin, pout, pcache = PRICES.get(MODEL, PRICES["claude-opus-5-5"])
    u = usage
    usd = (u["input_tokens"] * pin + u["cache_creation_input_tokens"] * pin * 1.25 + u["cache_read_input_tokens"] * pcache + u["output_tokens"] * pout) / 1e6
    if BATCH:
        usd /= 2
    return round(usd, 4)


def call_batch(client, params, usage):
    """One request through the Message Batches API (50 % off). Each tender runs in its own thread, so many wait in parallel."""
    import uuid
    b = client.messages.batches.create(requests=[{"custom_id": "f-" + uuid.uuid4().hex[:20], "params": params}])
    t0 = time.time()
    while True:
        time.sleep(30)
        try:
            b = client.messages.batches.retrieve(b.id)
        except Exception as e:  # noqa: BLE001
            print("batch poll retry", type(e).__name__, flush=True)
            continue
        if b.processing_status == "ended":
            break
        if time.time() - t0 > 5 * 3600:
            client.messages.batches.cancel(b.id)
            raise RuntimeError("batch took more than 5 h")
    for r in client.messages.batches.results(b.id):
        if r.result.type != "succeeded":
            raise RuntimeError(f"batch {r.result.type}: {str(getattr(r.result, 'error', ''))[:200]}")
        usage["batch_seconds"] = usage.get("batch_seconds", 0) + int(time.time() - t0)
        return r.result.message
    raise RuntimeError("batch without results")


def call_cf(system, messages, usage):
    """Cloudflare Workers AI (free tier) through the REST API, same prompts."""
    import urllib.request
    import urllib.error
    url, key = os.environ["COMPARE_URL"], os.environ["COMPARE_KEY"]
    flat = [{"role": "system", "content": system}] + [
        {"role": m["role"], "content": m["content"] if isinstance(m["content"], str) else "".join(b["text"] for b in m["content"])} for m in messages]
    body = json.dumps({"model": MODEL, "messages": flat, "max_tokens": 16000}).encode()
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=body, headers={"x-key": key, "Content-Type": "application/json", "User-Agent": "ullswater-fichas"})
            text, u = [], {}
            with urllib.request.urlopen(req, timeout=1800) as r:
                for line in r:
                    line = line.decode("utf-8", "replace").strip()
                    if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                        continue
                    try:
                        ev = json.loads(line[5:])
                    except ValueError:
                        continue
                    piece = ev.get("response")
                    text.append("" if piece is None else str(piece))
                    u = ev.get("usage") or u
            j = {"result": {"response": "".join(text), "usage": u}}
            break
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:400]
            print("workers ai error", e.code, msg, flush=True)
            if attempt == 2 or e.code in (400, 401, 403):
                raise RuntimeError(f"Workers AI {e.code}: {msg}")
            time.sleep(30)
    res = j.get("result") or {}
    u = res.get("usage") or {}
    usage["input_tokens"] = usage.get("input_tokens", 0) + (u.get("prompt_tokens") or 0)
    usage["output_tokens"] = usage.get("output_tokens", 0) + (u.get("completion_tokens") or 0)
    usage["calls"] = usage.get("calls", 0) + 1
    out = res.get("response")
    if not isinstance(out, str):
        out = json.dumps(out, ensure_ascii=False) if out is not None else ""
    return out, "end"


def call_kimi(system, messages, usage):
    """Kimi (Moonshot AI) through its OpenAI-compatible API, same prompts. Streamed so long answers do not time out."""
    import urllib.request
    import urllib.error
    key = os.environ["KIMI_API_KEY"].strip()
    base = os.environ.get("KIMI_BASE_URL", "https://api.moonshot.ai/v1")
    flat = [{"role": "system", "content": system}] + [
        {"role": m["role"], "content": m["content"] if isinstance(m["content"], str) else "".join(b["text"] for b in m["content"])} for m in messages]
    body = json.dumps({"model": MODEL, "messages": flat, "max_tokens": int(os.environ.get("KIMI_MAX_TOKENS", "32000")),
                       "stream": True, "stream_options": {"include_usage": True}}).encode()
    for attempt in range(4):
        try:
            req = urllib.request.Request(base + "/chat/completions", data=body, headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
            text, u, stop = [], {}, "end"
            with urllib.request.urlopen(req, timeout=1800) as r:
                for line in r:
                    line = line.decode("utf-8", "replace").strip()
                    if not line.startswith("data:") or line == "data: [DONE]":
                        continue
                    ev = json.loads(line[5:])
                    for ch in ev.get("choices") or []:
                        piece = (ch.get("delta") or {}).get("content")
                        if piece:
                            text.append(str(piece))
                        if ch.get("finish_reason"):
                            stop = ch["finish_reason"]
                            u = ch.get("usage") or u
                    u = ev.get("usage") or u
            break
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode("utf-8", "replace")
            print("kimi http", e.code, msg, flush=True)
            if e.code in (400, 401, 402, 403, 404) or attempt == 3:
                raise RuntimeError(f"kimi {e.code}: {msg}")
            time.sleep(30 * (attempt + 1))
        except Exception as e:  # noqa: BLE001
            print("kimi retry", attempt, type(e).__name__, str(e)[:200], flush=True)
            if attempt == 3:
                raise
            time.sleep(30 * (attempt + 1))
    usage["input_tokens"] = usage.get("input_tokens", 0) + (u.get("prompt_tokens") or 0)
    usage["cache_read_input_tokens"] = usage.get("cache_read_input_tokens", 0) + (u.get("cached_tokens") or (u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
    usage["output_tokens"] = usage.get("output_tokens", 0) + (u.get("completion_tokens") or 0)
    usage["calls"] = usage.get("calls", 0) + 1
    return "".join(text), ("max_tokens" if stop == "length" else stop)


def call(client, system, messages, usage):
    if MODEL.startswith("kimi"):
        return call_kimi(system, messages, usage)
    if MODEL.startswith("@cf/"):
        return call_cf(system, messages, usage)
    params = dict(model=MODEL, max_tokens=64000, output_config={"effort": EFFORT},
                  system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}], messages=messages)
    for attempt in range(4):
        if BATCH:
            msg = call_batch(client, params, usage)
            break
        try:
            try:
                with client.beta.messages.stream(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params) as st:
                    msg = st.get_final_message()
            except TypeError:  # older SDK without fallbacks
                with client.messages.stream(**params) as st:
                    msg = st.get_final_message()
            break
        except Exception as e:  # noqa: BLE001
            print("api retry", attempt, type(e).__name__, str(e)[:200], flush=True)
            if attempt == 3:
                raise
            time.sleep(20 * (attempt + 1))
    u = msg.usage
    for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
        usage[k] = usage.get(k, 0) + (getattr(u, k, 0) or 0)
    usage["calls"] = usage.get("calls", 0) + 1
    if msg.stop_reason == "refusal":
        raise RuntimeError("refusal")
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    return text, msg.stop_reason


def parse(text):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    a, b = t.find("{"), t.rfind("}")
    return json.loads(t[a:b + 1])


# ---------- 4. checks ----------

def finish_ficha(f, eid, idx, entry, cfs, parts, cut):
    f["id"] = eid
    f["reviewed"] = date.today().isoformat()
    f["official_url"] = idx["link"] or f.get("official_url", "")
    f["updated"] = S.first(entry, "updated")[:10]
    f.setdefault("published", f["updated"])
    file_of = {p["code"]: p for p in parts}
    docs = {}
    for k, v in (f.get("docs") or {}).items():
        if k in file_of:
            docs[k] = {"label": v.get("label", k) if isinstance(v, dict) else str(v), "file": file_of[k]["file"], "pages": len(file_of[k]["pages"])}
    for k, p in file_of.items():  # every document read, even if never cited
        docs.setdefault(k, {"label": p["name"] or k, "file": p["file"], "pages": len(p["pages"])})
    f["docs"] = docs
    lab = {}
    for k, d in docs.items():
        lab.setdefault(d["file"], d["label"])
    f["files"] = [{"name": lab.get(x.get("file"), x.get("name") or x.get("file")), "file": x.get("file"), "type": x.get("type", ""),
                   "pages": x.get("pages"), "bytes": x.get("bytes", 0)} for x in idx["docs"] if x.get("file")]
    if cut:
        f["not_read"] = cut
    return f


def check_ficha(f, idx):
    errs = []
    keys = {s.get("key") for s in f.get("sections", [])}
    for k in ("what", "lots", "money", "can", "win", "when", "risk"):
        if k not in keys:
            errs.append(f"falta la sección {k}")
    if len(f.get("tags") or {}) != 10:
        errs.append("tags debe tener exactamente 10 claves")
    if (f.get("verdict") or {}).get("opportunity") not in ("alta", "media", "baja") or (f.get("verdict") or {}).get("difficulty") not in ("alta", "media", "baja"):
        errs.append("verdict.opportunity y verdict.difficulty deben ser alta, media o baja")
    for k in ("deadline", "published"):
        try:
            date.fromisoformat(f.get(k) or "")
        except ValueError:
            errs.append(f"{k} no es una fecha AAAA-MM-DD")
    if not errs:
        try:
            R.body(f, idx)
        except Exception:  # noqa: BLE001
            errs.append("la ficha no se puede maquetar: " + traceback.format_exc(limit=2)[-400:])
    return errs


def check_rules(eid):
    r = subprocess.run(["node", str(ROOT / "tenders" / "diagnostico" / "check.js"), eid], capture_output=True, text=True, env=dict(os.environ, FICHAS_DIR=str(FICHAS)))
    return r.returncode == 0, (r.stdout + r.stderr).strip()


# ---------- 5. one tender ----------

def process(client, system, item):
    eid, entry, cfs, ds = item
    t0 = time.time()
    d = FICHAS / eid
    usage = {"model": MODEL, "effort": EFFORT}
    try:
        idx, parts = fetch(eid, entry, cfs, ds)
        if not parts:
            return {"id": eid, "status": "sin documentos legibles"}
        text, cut = doc_block(parts)
        usage["doc_chars"] = len(text)
        usage["doc_pages"] = sum(len(p["pages"]) for p in parts)
        meta = (f"Licitación PLACSP id {eid}. Título oficial: {idx['title']}. Órgano: {idx['buyer']}. Enlace: {idx['link']}. "
                f"Fecha de hoy: {date.today().isoformat()}. Datos del anuncio: plazo {S.first(cfs, 'EndDate')} {S.first(cfs, 'EndTime')}, "
                f"importe sin IVA {S.first(cfs, 'TaxExclusiveAmount')} €, valor estimado {S.first(cfs, 'EstimatedOverallContractAmount')} €, "
                f"CPV {S.first(cfs, 'ItemClassificationCode')}, tipo {S.first(cfs, 'TypeCode')}, procedimiento {S.first(cfs, 'ProcedureCode')}.")
        user = [{"type": "text", "text": "DOCUMENTOS OFICIALES:" + text, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": meta + "\nEscribe ahora el JSON {\"ficha\": …, \"reglas\": …} de esta licitación."}]
        msgs = [{"role": "user", "content": user}]
        out, stop = call(client, system, msgs, usage)
        problems = []
        for rnd in range(2):
            try:
                j = parse(out)
                f, rules = j["ficha"], j.get("reglas")
            except Exception as e:  # noqa: BLE001
                problems = [f"el JSON no es válido ({e}; stop={stop})"]
                f, rules = None, None
            if f is not None:
                f = finish_ficha(f, eid, idx, entry, cfs, parts, cut)
                problems = check_ficha(f, idx)
                if rules and not problems:
                    d.mkdir(parents=True, exist_ok=True)
                    rules.update(id=eid, reviewed=date.today().isoformat(), official_url=f["official_url"])
                    (d / "reglas.json").write_text(json.dumps(rules, ensure_ascii=False, indent=1), encoding="utf-8")
                    (d / "ficha.json").write_text(json.dumps(f, ensure_ascii=False, indent=1), encoding="utf-8")
                    ok, log = check_rules(eid)
                    usage["rules_check"] = log
                    if not ok:
                        problems = ["la hoja de reglas no pasa el control automático: " + log]
            if not problems or rnd == 1:
                break
            print(eid, "repair:", problems, flush=True)
            msgs = msgs[:1] + [{"role": "assistant", "content": out},
                               {"role": "user", "content": "Corrige estos problemas y devuelve el JSON completo otra vez, igual de detallado:\n- " + "\n- ".join(problems)}]
            out, stop = call(client, system, msgs, usage)
        status = "ok"
        if f is None or any(p.startswith(("falta", "tags", "verdict", "deadline", "published", "la ficha", "el JSON")) for p in problems):
            status = "error: " + "; ".join(problems)[:300]
            for x in ("ficha.json", "reglas.json"):
                (d / x).unlink(missing_ok=True)
            if FICHAS != ROOT / "tenders" / "fichas":  # comparison: keep what the model wrote, to show it
                d.mkdir(parents=True, exist_ok=True)
                (d / "raw_output.txt").write_text(out or "", encoding="utf-8")
        else:
            d.mkdir(parents=True, exist_ok=True)
            if problems:  # ficha fine, diagnosis rules not: publish the ficha without the diagnosis
                (d / "reglas.json").unlink(missing_ok=True)
                status = "ok sin diagnóstico (reglas no superan el control)"
            (d / "ficha.json").write_text(json.dumps(f, ensure_ascii=False, indent=1), encoding="utf-8")
            (d / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
            R.main(d)
            (d / "ficha.html").unlink(missing_ok=True)
        usage.update(cost_usd=price(usage), seconds=round(time.time() - t0), status=status, problems=problems, not_read=cut)
        usage["cost_eur"] = round(usage["cost_usd"] * EUR_PER_USD, 4)
        if d.exists():
            (d / "ai_usage.json").write_text(json.dumps(usage, ensure_ascii=False, indent=1), encoding="utf-8")
        print(eid, status, usage.get("cost_usd"), "USD", flush=True)
        return dict(usage, id=eid, title=idx["title"], buyer=idx["buyer"])
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        usage.update(status=f"error: {type(e).__name__}: {str(e)[:200]}", id=eid)
        if usage.get("calls"):
            usage["cost_usd"] = price(usage)
        return usage


def main():
    global MAX_CHARS
    client = None
    if MODEL.startswith("@cf/"):  # free comparison: Cloudflare Workers AI reads at most ~131k tokens
        MAX_CHARS = min(MAX_CHARS, int(os.environ.get("FICHA_CF_MAX_CHARS", "280000")))
    elif MODEL.startswith("kimi"):  # 256k-token context
        if not os.environ.get("KIMI_API_KEY", "").strip():
            sys.exit("KIMI_API_KEY is empty: add it in GitHub › Settings › Secrets › Actions")
        print("KIMI_API_KEY: set", flush=True)
        import urllib.request
        try:  # list the models this key can use, so the log shows the right name
            req = urllib.request.Request(os.environ.get("KIMI_BASE_URL", "https://api.moonshot.ai/v1") + "/models", headers={"Authorization": "Bearer " + os.environ["KIMI_API_KEY"].strip()})
            names = [m["id"] for m in json.load(urllib.request.urlopen(req, timeout=60)).get("data", [])]
            print("kimi models:", ", ".join(sorted(names)), flush=True)
        except Exception as e:  # noqa: BLE001
            sys.exit(f"Kimi rejects KIMI_API_KEY or is unreachable: {type(e).__name__} {str(e)[:200]}")
        MAX_CHARS = min(MAX_CHARS, int(os.environ.get("FICHA_KIMI_MAX_CHARS", "520000")))
    else:
        import anthropic
        key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        print("ANTHROPIC_API_KEY:", "set" if key else "NOT SET", flush=True)
        if not key:
            sys.exit("ANTHROPIC_API_KEY is empty: add it in GitHub › Settings › Secrets › Actions")
        client = anthropic.Anthropic(api_key=key, max_retries=4, timeout=1800)
        try:  # one tiny call first, so a bad key stops the run before any download
            client.messages.create(model=MODEL, max_tokens=16, messages=[{"role": "user", "content": "ok"}])
        except anthropic.AuthenticationError:
            sys.exit("The Claude API rejects ANTHROPIC_API_KEY (401): the key in GitHub secrets is not valid")
    ids = [x.strip() for x in os.environ.get("FICHA_IDS", "").split(",") if x.strip()]
    items = by_ids(ids) if ids else candidates(int(os.environ.get("FICHA_N", "10")))
    system = system_prompt()
    with ThreadPoolExecutor(int(os.environ.get("FICHA_WORKERS", "3"))) as ex:
        res = list(ex.map(lambda it: process(client, system, it), items))
    tot = sum(r.get("cost_usd") or 0 for r in res)
    ok = [r for r in res if str(r.get("status", "")).startswith("ok")]
    rep = {"date": date.today().isoformat(), "model": MODEL, "effort": EFFORT, "batch": BATCH, "tenders": len(res), "ok": len(ok),
           "cost_usd": round(tot, 2), "cost_eur": round(tot * EUR_PER_USD, 2),
           "avg_cost_eur_per_ok": round(tot * EUR_PER_USD / max(len(ok), 1), 3), "results": res}
    out = ROOT / "tenders" / "fichas_batches"
    out.mkdir(exist_ok=True)
    (out / f"{date.today().isoformat()}_{MODEL.replace('/', '_').lstrip('@_')}_{int(time.time())}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [f"## Fichas IA: {len(ok)} de {len(res)} hechas · modelo {MODEL} ({EFFORT}{', por lotes -50 %' if BATCH else ''})", "",
             f"Coste total: **{rep['cost_eur']} €** ({rep['cost_usd']} $) · media por ficha: **{rep['avg_cost_eur_per_ok']} €**", "",
             "| id | órgano | págs. | tokens entrada | tokens salida | € | estado |", "|---|---|---|---|---|---|---|"]
    for r in res:
        tin = (r.get("input_tokens") or 0) + (r.get("cache_creation_input_tokens") or 0) + (r.get("cache_read_input_tokens") or 0)
        lines.append(f"| {r.get('id')} | {(r.get('buyer') or '')[:50]} | {r.get('doc_pages', '')} | {tin} | {r.get('output_tokens', '')} | "
                     f"{round((r.get('cost_usd') or 0) * EUR_PER_USD, 3)} | {r.get('status')} |")
    md = "\n".join(lines)
    print(md)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(md + "\n")


if __name__ == "__main__":
    main()
