#!/usr/bin/env python3
"""Reads the official text of each Spanish call (BDNS) and extracts the content of its PDF factsheet.

For every call in site/data/spain.json:
  1. picks the official call document published in the BDNS (Spanish text preferred; texts in Catalan,
     Basque, Galician or Valencian are translated by the model),
  2. downloads it (cached in .cache/bdns/docs/) and extracts the text with pypdf,
  3. asks Claude for a structured summary (object, beneficiaries, requirements, eligible costs, amounts and aid
     intensity, deadlines, evaluation criteria, payment, documentation...) — strictly from the text.

The requests go through the Message Batches API (50 % cheaper than the Messages API; results usually within an hour,
at most 24 h). Each run:
  a) collects the results of batches submitted earlier (state in site/data/spain_x_batches.json, committed by the
     daily workflow; ended batches that the state file lost are recovered from the API listing),
  b) submits one new batch with every call that has no extraction for its current document,
  c) waits up to EXTRACT_WAIT_MIN minutes (default 20) and collects it, so most factsheets appear the same day.

Output: site/data/spain_x.json  {bdns id: {"doc", "docName", "model", "extracted", "data": {...}}}
Each call is extracted once per document (re-extracted only if the BDNS publishes a new document or with --force).
Needs ANTHROPIC_API_KEY. Optional: CLAUDE_EXTRACT_MODEL (default claude-haiku-5-5), EXTRACT_MAX (calls per batch,
default 400), EXTRACT_SUBMIT=false (only collect; used on push runs, whose state is not committed).
Without the key it does nothing, and the factsheets keep the basic BDNS layout.

  python scripts/bdns_extract.py [--force] [ID ...]
"""
import io
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPAIN = ROOT / "site" / "data" / "spain.json"
OUT = ROOT / "site" / "data" / "spain_x.json"
STATE = ROOT / "site" / "data" / "spain_x_batches.json"
DOCS = ROOT / ".cache" / "bdns" / "docs"
API = "https://www.infosubvenciones.es/bdnstrans/api/convocatorias/documentos?idDocumento="
ANTHROPIC = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
UA = {"User-Agent": "UllswaterCallsBot/1.0 (+https://calls.ullswaterinvestments.com)"}
MAX_CHARS = 140_000

LIST = {"type": "array", "items": {"type": "string"}}
SCHEMA = {
    "type": "object",
    "properties": {
        "resumen": {"type": "string", "description": "2-3 frases: qué financia, a quién y cuánto"},
        "objeto": {"type": "string", "description": "Objeto y finalidad de la ayuda (máx. 90 palabras)"},
        "beneficiarios": {**LIST, "description": "Quién puede solicitarla (tipos de entidad, tamaño, ubicación)"},
        "requisitos": {**LIST, "description": "Requisitos clave de los beneficiarios y de los proyectos"},
        "actuaciones": {**LIST, "description": "Actuaciones o proyectos subvencionables"},
        "gastos": {"type": "array", "items": {"type": "object", "properties": {"partida": {"type": "string"}, "condiciones": {"type": "string"}}, "required": ["partida"]},
                   "description": "Gastos subvencionables con sus condiciones o límites"},
        "excluidos": {**LIST, "description": "Gastos o actuaciones expresamente no subvencionables"},
        "cuantia": {"type": "object", "properties": {
            "presupuesto_total": {"type": ["number", "null"], "description": "Euros"},
            "importe_maximo": {"type": ["number", "null"], "description": "Ayuda máxima por beneficiario o proyecto, en euros"},
            "importe_minimo": {"type": ["number", "null"]},
            "inversion_minima": {"type": ["number", "null"], "description": "Presupuesto o inversión mínima del proyecto, en euros"},
            "intensidad": {"type": "array", "items": {"type": "object", "properties": {"categoria": {"type": "string", "description": "p. ej. Pequeña empresa, Mediana empresa, Gran empresa, General"},
                                                                                       "porcentaje": {"type": "number"}}, "required": ["categoria", "porcentaje"]},
                           "description": "Porcentaje máximo de ayuda sobre el gasto subvencionable, por categoría"},
            "lineas": {"type": "array", "items": {"type": "object", "properties": {"nombre": {"type": "string"}, "importe": {"type": ["number", "null"]}}, "required": ["nombre"]},
                       "description": "Líneas, categorías o lotes con su dotación"},
            "notas": {"type": "string"}}},
        "plazos": {"type": "object", "properties": {
            "solicitud_inicio": {"type": ["string", "null"], "description": "AAAA-MM-DD"},
            "solicitud_fin": {"type": ["string", "null"], "description": "AAAA-MM-DD"},
            "hora_fin": {"type": ["string", "null"]},
            "ejecucion": {"type": ["string", "null"], "description": "Plazo o periodo de ejecución"},
            "ejecucion_meses": {"type": ["number", "null"]},
            "justificacion": {"type": ["string", "null"]},
            "resolucion": {"type": ["string", "null"], "description": "Plazo máximo de resolución y efecto del silencio"}}},
        "procedimiento": {"type": "string", "description": "Concurrencia competitiva, orden de llegada, etc."},
        "criterios": {"type": "array", "items": {"type": "object", "properties": {"criterio": {"type": "string"}, "puntos": {"type": ["number", "null"]}}, "required": ["criterio"]},
                      "description": "Criterios de valoración con su puntuación máxima"},
        "puntuacion_minima": {"type": ["number", "null"]},
        "pago": {"type": "string", "description": "Forma de pago, anticipos y garantías"},
        "justificacion": {"type": "string", "description": "Cómo se justifica (cuenta justificativa, auditor, informes)"},
        "documentacion": {**LIST, "description": "Documentación que hay que presentar con la solicitud"},
        "obligaciones": {**LIST, "description": "Obligaciones más relevantes del beneficiario"},
        "compatibilidad": {"type": "string"},
        "regimen": {"type": "string", "description": "Marco de ayudas de Estado (RGEC, minimis...)"},
        "presentacion": {"type": "string", "description": "Dónde y cómo se presenta la solicitud"},
        "atencion": {**LIST, "description": "3-5 puntos de atención prácticos para un solicitante (riesgos, exigencias poco habituales, plazos críticos)"},
    },
    "required": ["resumen", "objeto", "beneficiarios", "requisitos", "actuaciones", "cuantia", "plazos"],
}
SYSTEM = """Eres analista de ayudas públicas de Ullswater Investments. Recibes el texto oficial de una convocatoria de subvenciones española
(puede estar en castellano, catalán, euskera, gallego o valenciano) y rellenas la herramienta "ficha" en CASTELLANO.
Reglas: usa SOLO información del texto; si un dato no aparece, déjalo vacío o null, nunca lo inventes ni lo deduzcas de otras convocatorias.
Importes en euros como números (sin símbolos), porcentajes como números, fechas AAAA-MM-DD. Viñetas breves (máx. 30 palabras), sin repetir
el mismo dato en varios campos. Si el texto remite a las bases reguladoras para un dato, indícalo así ("según las bases reguladoras")."""


def pick_doc(docs):
    def score(d):
        t = (d.get("desc", "") + " " + d.get("name", "")).lower()
        s = 0
        if "convocatoria" in t or "convocat" in t: s += 4
        if "castellano" in t or "_es" in t or "-es" in t: s += 3
        if "extracto" in t: s -= 1
        if "otra lengua" in t: s -= 2
        if "bases" in t: s += 1
        if "anexo" in t or "modelo" in t or "formulario" in t: s -= 3
        return s
    docs = [d for d in docs or [] if d.get("id")]
    return max(docs, key=score) if docs else None


def pdf_text(doc_id):
    DOCS.mkdir(parents=True, exist_ok=True)
    f = DOCS / f"{doc_id}.pdf"
    if not f.exists():
        req = urllib.request.Request(API + str(doc_id), headers=UA)
        f.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    from pypdf import PdfReader
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(f.read_bytes())).pages)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def request_body(text, call, model):
    meta = f"Título: {call['title']}\nOrganismo: {call.get('body')}\nRegión: {call.get('region')}\nCódigo BDNS: {call['id']}\n"
    return {"model": model, "max_tokens": 6000,
            "system": [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            "tools": [{"name": "ficha", "description": "Ficha estructurada de la convocatoria", "input_schema": SCHEMA}],
            "tool_choice": {"type": "tool", "name": "ficha"},
            "messages": [{"role": "user", "content": meta + "\nTEXTO OFICIAL:\n" + text[:MAX_CHARS]}]}


def api(key, path, body=None, raw=False):
    req = urllib.request.Request(ANTHROPIC + path, data=json.dumps(body).encode() if body is not None else None,
                                 method="POST" if body is not None else "GET",
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = r.read()
            return data if raw else json.loads(data)
        except urllib.error.HTTPError as ex:
            if ex.code < 500 and ex.code != 429 or attempt == 3:
                raise RuntimeError(f"{ex.code} {ex.read()[:300]!r}")
        except Exception:
            if attempt == 3:
                raise
        time.sleep(10 * (attempt + 1))


def load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def collect(key, state, store, live):
    """Fetch the results of every ended batch in `state`; returns token usage."""
    tin = tout = got = 0
    for b in list(state["batches"]):
        info = api(key, f"/v1/messages/batches/{b['id']}")
        if info.get("processing_status") != "ended":
            continue
        for line in api(key, f"/v1/messages/batches/{b['id']}/results", raw=True).decode("utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            item = b["items"].get(r["custom_id"])
            res = r.get("result") or {}
            if not item:
                continue
            if res.get("type") != "succeeded":
                print(f"  ! {item['call']}: {res.get('type')} {str(res.get('error'))[:160]}")
                continue
            msg = res["message"]
            data = next((blk["input"] for blk in msg.get("content", []) if blk.get("type") == "tool_use"), None)
            if data is None or item["call"] not in live:
                continue
            store[item["call"]] = {"doc": item["doc"], "docName": item.get("docName"), "model": msg.get("model") or b.get("model"),
                                   "extracted": date.today().isoformat(), "data": data}
            u = msg.get("usage") or {}
            tin += u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
            tout += u.get("output_tokens", 0)
            got += 1
        state["batches"].remove(b)
        state.setdefault("done", []).append(b["id"])
        state["done"] = state["done"][-50:]
    if got:
        print(f"  collected {got} factsheets from batches (tokens in {tin}, out {tout}; billed at batch price, 50 % off)")
    return got


def recover(key, state):
    """Ended batches submitted by a run whose state file was not committed (push runs): re-adopt them via their custom ids."""
    known = {b["id"] for b in state["batches"]} | set(state.get("done", []))
    try:
        lst = api(key, "/v1/messages/batches?limit=20").get("data", [])
    except Exception as ex:
        print(f"  batch listing skipped: {ex}")
        return
    for info in lst:
        if info["id"] in known or info.get("processing_status") == "canceling":
            continue
        try:
            first = api(key, f"/v1/messages/batches/{info['id']}/results", raw=True).decode().splitlines() if info.get("processing_status") == "ended" else []
        except Exception:
            continue
        items = {}
        for line in first:
            cid = json.loads(line)["custom_id"]
            m = re.match(r"bdns-(\w+)-d(\d+)$", cid)
            if m:
                items[cid] = {"call": m.group(1), "doc": int(m.group(2))}
        if items:
            state["batches"].append({"id": info["id"], "items": items, "submitted": info.get("created_at", "")[:10]})
            print(f"  recovered batch {info['id']} ({len(items)} requests)")


def main():
    args = sys.argv[1:]
    force = "--force" in args
    only = {a for a in args if not a.startswith("--")}
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    model = os.environ.get("CLAUDE_EXTRACT_MODEL") or "claude-haiku-5-5"
    limit = int(os.environ.get("EXTRACT_MAX", "400"))
    wait_min = float(os.environ.get("EXTRACT_WAIT_MIN", "20"))
    submit = os.environ.get("EXTRACT_SUBMIT", "true").lower() not in ("false", "0", "no")
    if not key:
        print("  ANTHROPIC_API_KEY not set: Spanish factsheets keep the basic BDNS layout.")
        return
    calls = json.loads(SPAIN.read_text(encoding="utf-8")).get("calls", [])
    live = {c["id"] for c in calls}
    store = {k: v for k, v in load(OUT, {}).items() if k in live}  # drop calls that are no longer published
    state = load(STATE, {"batches": [], "done": []})

    recover(key, state)
    collect(key, state, store, live)
    save(OUT, store)
    save(STATE, state)

    pending = {it["call"] + ":" + str(it["doc"]) for b in state["batches"] for it in b["items"].values()}
    todo = []
    for c in calls:
        if only and c["id"] not in only:
            continue
        doc = pick_doc((c.get("detail") or {}).get("docs"))
        if not doc:
            continue
        if not force and store.get(c["id"], {}).get("doc") == doc["id"]:
            continue
        if f"{c['id']}:{doc['id']}" in pending:
            continue
        todo.append((c, doc))
    print(f"  Spanish calls: {len(store)} with full factsheet, {len(pending)} in batches being processed, {len(todo)} to extract")
    if not todo or not submit:
        return

    requests, items = [], {}
    for c, doc in todo:
        if len(requests) >= limit:
            print(f"  batch limited to {limit} calls; the rest go in the next run")
            break
        try:
            text = pdf_text(doc["id"])
        except Exception as ex:
            print(f"  ! {c['id']}: document {doc['id']}: {ex}")
            continue
        if len(text) < 800:
            print(f"  {c['id']}: document without usable text ({len(text)} chars), skipped")
            continue
        cid = f"bdns-{c['id']}-d{doc['id']}"[:64]
        requests.append({"custom_id": cid, "params": request_body(text, c, model)})
        items[cid] = {"call": c["id"], "doc": doc["id"], "docName": doc.get("desc") or doc.get("name")}
    if not requests:
        return
    b = api(key, "/v1/messages/batches", {"requests": requests})
    state["batches"].append({"id": b["id"], "model": model, "submitted": date.today().isoformat(), "items": items})
    save(STATE, state)
    print(f"  submitted batch {b['id']}: {len(requests)} calls with {model}")

    deadline = time.time() + wait_min * 60
    while time.time() < deadline:
        time.sleep(30)
        if api(key, f"/v1/messages/batches/{b['id']}").get("processing_status") == "ended":
            break
    collect(key, state, store, live)
    save(OUT, store)
    save(STATE, state)
    if state["batches"]:
        print(f"  {len(state['batches'])} batch(es) still running: collected in the next run")


if __name__ == "__main__":
    main()
