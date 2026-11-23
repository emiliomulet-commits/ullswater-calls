#!/usr/bin/env python3
"""Reads the official text of each Spanish call (BDNS) and extracts the content of its PDF factsheet.

For every call in site/data/spain.json:
  1. picks the official call document published in the BDNS (Spanish text preferred; texts in Catalan,
     Basque, Galician or Valencian are translated by the model),
  2. downloads it (cached in .cache/bdns/docs/) and extracts the text with pypdf,
  3. asks Claude for a structured summary (object, beneficiaries, requirements, eligible costs, amounts and aid
     intensity, deadlines, evaluation criteria, payment, documentation...) — strictly from the text.

Output: site/data/spain_x.json  {bdns id: {"doc", "docName", "model", "extracted", "data": {...}}}
Each call is extracted once per document (re-extracted only if the BDNS publishes a new document or with --force).
Needs ANTHROPIC_API_KEY (optional CLAUDE_MODEL, default claude-sonnet-5-5; EXTRACT_MAX new extractions per run).
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
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPAIN = ROOT / "site" / "data" / "spain.json"
OUT = ROOT / "site" / "data" / "spain_x.json"
DOCS = ROOT / ".cache" / "bdns" / "docs"
API = "https://www.infosubvenciones.es/bdnstrans/api/convocatorias/documentos?idDocumento="
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


def claude(text, call, key, model):
    meta = f"Título: {call['title']}\nOrganismo: {call.get('body')}\nRegión: {call.get('region')}\nCódigo BDNS: {call['id']}\n"
    body = {"model": model, "max_tokens": 6000, "system": SYSTEM, "tools": [{"name": "ficha", "description": "Ficha estructurada de la convocatoria", "input_schema": SCHEMA}],
            "tool_choice": {"type": "tool", "name": "ficha"},
            "messages": [{"role": "user", "content": meta + "\nTEXTO OFICIAL:\n" + text[:MAX_CHARS]}]}
    base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    req = urllib.request.Request(base + "/v1/messages", data=json.dumps(body).encode(), method="POST",
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    for attempt in range(3):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=300))
            for blk in r.get("content", []):
                if blk.get("type") == "tool_use":
                    return blk["input"], r.get("usage", {})
            raise ValueError("no tool_use in response")
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  retry {call['id']}: {e}")
            time.sleep(10 * (attempt + 1))


def main():
    args = sys.argv[1:]
    force = "--force" in args
    only = {a for a in args if not a.startswith("--")}
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
    limit = int(os.environ.get("EXTRACT_MAX", "60"))
    if not key:
        print("  ANTHROPIC_API_KEY not set: Spanish factsheets keep the basic BDNS layout.")
        return
    calls = json.loads(SPAIN.read_text(encoding="utf-8")).get("calls", [])
    store = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    live = {c["id"] for c in calls}
    store = {k: v for k, v in store.items() if k in live}  # drop calls that are no longer published
    done, tin, tout = 0, 0, 0
    for c in calls:
        if only and c["id"] not in only:
            continue
        doc = pick_doc((c.get("detail") or {}).get("docs"))
        if not doc:
            continue
        if not force and store.get(c["id"], {}).get("doc") == doc["id"]:
            continue
        if done >= limit:
            print(f"  limit of {limit} extractions reached; the rest go in the next run")
            break
        try:
            text = pdf_text(doc["id"])
            if len(text) < 800:
                print(f"  {c['id']}: document without usable text ({len(text)} chars), skipped")
                continue
            data, usage = claude(text, c, key, model)
        except Exception as e:
            print(f"  ! {c['id']}: {e}")
            continue
        store[c["id"]] = {"doc": doc["id"], "docName": doc.get("desc") or doc.get("name"), "model": model,
                          "extracted": date.today().isoformat(), "data": data}
        tin += usage.get("input_tokens", 0)
        tout += usage.get("output_tokens", 0)
        done += 1
        OUT.write_text(json.dumps(store, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    OUT.write_text(json.dumps(store, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  Spanish calls with full factsheet content: {len(store)} ({done} new; tokens in {tin}, out {tout})")


if __name__ == "__main__":
    main()
