#!/usr/bin/env python3
"""Spanish national and regional R&D&I / industry calls from the BDNS
(Base de Datos Nacional de Subvenciones, public API of infosubvenciones.es).

Keeps only competitive calls (concurrencia competitiva) from State and regional
administrations, with purpose R&D&I or Industry & Energy, open or opening soon,
for companies or legal entities. Writes site/data/spain.json.
Source: Sistema Nacional de Publicidad de Subvenciones y Ayudas Públicas (IGAE).
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://www.infosubvenciones.es/bdnstrans/api"
CACHE = ROOT / ".cache" / "bdns" / "details.json"
OUT = ROOT / "site" / "data" / "spain.json"
FINALIDADES = {17: "R&D&I", 13: "Industry & energy"}
UA = {"User-Agent": "UllswaterCallsBot/1.0 (+https://calls.ullswaterinvestments.com)", "Accept": "application/json"}
LOOKBACK_DAYS = 240


def get(path, **params):
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.load(r)
        except Exception as e:
            if attempt == 3:
                raise
            time.sleep(4 * (attempt + 1))


def pdate(s):
    if not s or s == "None":
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            pass
    return None


def main():
    today = date.today()
    since = (today - timedelta(days=LOOKBACK_DAYS)).strftime("%d/%m/%Y")
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    listing = {}
    for fid in FINALIDADES:
        page = 0
        while True:
            d = get("convocatorias/busqueda", page=page, pageSize=200, order="fechaRecepcion", direccion="desc",
                    finalidad=fid, fechaDesde=since, vpd="GE")
            for c in d.get("content", []):
                if c.get("nivel1") in ("ESTADO", "AUTONOMICA"):
                    listing[c["numeroConvocatoria"]] = (c, fid)
            if d.get("last", True) or page > 20:
                break
            page += 1
            time.sleep(0.5)
    print(f"Listing: {len(listing)} State/regional calls (R&D&I + industry) since {since}")

    fetched = 0
    for num, (c, fid) in listing.items():
        cached = cache.get(num)
        # Re-fetch details if unknown, or if dates were still pending last time
        if cached and (cached.get("_final") or cached.get("_fetched") == today.isoformat()):
            continue
        try:
            det = get("convocatorias", numConv=num, vpd="GE")
        except Exception as e:
            print(f"  detail {num} failed: {e}", file=sys.stderr)
            continue
        det["_fetched"] = today.isoformat()
        end = pdate(det.get("fechaFinSolicitud")) or pdate(det.get("textFin"))
        det["_final"] = bool(end and end < today)
        cache[num] = det
        fetched += 1
        time.sleep(0.35)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    print(f"Fetched {fetched} new/updated details (cache {len(cache)})")

    out = []
    for num, (c, fid) in listing.items():
        d = cache.get(num)
        if not d:
            continue
        tipo = (d.get("tipoConvocatoria") or "").lower()
        if "concurrencia competitiva" not in tipo:
            continue
        bens = " ".join(b.get("descripcion", "") for b in (d.get("tiposBeneficiarios") or [])).upper()
        if not re.search(r"PYME|PERSONAS JUR[IÍ]DICAS|EMPRESA|ENTIDADES", bens):
            continue  # skip calls only for individuals
        start = pdate(d.get("fechaInicioSolicitud")) or pdate(d.get("textInicio"))
        end = pdate(d.get("fechaFinSolicitud")) or pdate(d.get("textFin"))
        if end and end < today:
            continue
        is_open = d.get("abierto") in (True, "true", "True") or bool(start and start <= today and (not end or end >= today))
        if not is_open and not (start and start > today) and not end:
            continue
        org = d.get("organo") or {}
        try:
            budget = int(float(d.get("presupuestoTotal") or 0)) or None
        except (TypeError, ValueError):
            budget = None
        out.append({
            "id": num, "title": (d.get("descripcion") or c.get("descripcion") or "").strip(),
            "level": "State" if org.get("nivel1") == "ESTADO" else "Regional",
            "region": org.get("nivel2", "").title() if org.get("nivel1") != "ESTADO" else "Spain",
            "body": (org.get("nivel3") or org.get("nivel2") or "").title(),
            "purpose": FINALIDADES[fid], "open": is_open,
            "start": start.isoformat() if start else None, "end": end.isoformat() if end else None,
            "budget": budget, "beneficiaries": [b.get("descripcion", "").capitalize() for b in (d.get("tiposBeneficiarios") or [])][:3],
            "funds": [f.get("descripcion", "") for f in (d.get("fondos") or [])][:2], "mrr": d.get("mrr") in (True, "true", "True"),
            "url": d.get("sedeElectronica") if d.get("sedeElectronica") not in (None, "None", "") else None,
            "bdns": f"https://www.infosubvenciones.es/bdnstrans/GE/es/convocatorias/{num}",
            "published": c.get("fechaRecepcion"),
        })
    out.sort(key=lambda x: (not x["open"], x["end"] or "9999"))
    OUT.write_text(json.dumps({"updated": today.isoformat(), "calls": out,
                               "source": "Sistema Nacional de Publicidad de Subvenciones y Ayudas Públicas (BDNS), IGAE"}, ensure_ascii=False), encoding="utf-8")
    print(f"Spain: {len(out)} competitive calls open or upcoming ({sum(1 for x in out if x['open'])} open)")


if __name__ == "__main__":
    main()
