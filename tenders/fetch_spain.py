#!/usr/bin/env python3
"""Spanish public tenders (licitaciones) for tenders.ullswaterinvestments.com/es/espana/, by level of government.

Source: Plataforma de Contratación del Sector Público (PLACSP, Ministerio de Hacienda), open syndication (Atom + CODICE):
  sindicacion_643   licitacionesPerfilesContratanteCompleto3.atom  every contracting profile hosted on PLACSP
                    (Administración General del Estado, many regions, diputaciones, comarcas and ayuntamientos)
  sindicacion_1044  PlataformasAgregadasSinMenores.atom            the regional platforms that publish on their own
                    and aggregate into PLACSP (Cataluña, País Vasco, Madrid, Galicia, Andalucía, Navarra, La Rioja…)
Minor contracts (contratos menores) are left out: they are not open competitions.

Each feed is a chain of Atom pages, newest update first (rel="next" goes back in time); one entry = the latest state of
one tender (ContractFolderStatus). We keep tenders whose status is PUB (open for bids) and whose deadline is today or later.

Incremental: .cache/tenders/placsp_<feed>.json holds every tender seen with its latest state and the newest <updated>
time read. Each run walks back only to that time (minus an overlap); without a cache it walks back DAYS_BACK days.

Writes site-tenders/data/es/:
  spain.json    every open tender (compact records, see rec())
  stats.json    counts by level, region and province, closing in 7/30 days
"""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site-tenders" / "data" / "es"
CACHE = ROOT / ".cache" / "tenders"
UA = "UllswaterTendersBot/1.0 (+https://tenders.ullswaterinvestments.com/es/espana/)"
FEEDS = {
    "placsp": "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom",
    "agregadas": "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_1044/PlataformasAgregadasSinMenores.atom",
}
DAYS_BACK = int(os.environ.get("SPAIN_DAYS_BACK", "75"))     # first run: how far back to read
MAX_PAGES = int(os.environ.get("SPAIN_MAX_PAGES", "4000"))   # per feed and run
TIME_BUDGET = int(os.environ.get("SPAIN_TIME_BUDGET", "2400"))  # seconds per feed and run
OVERLAP = timedelta(hours=6)
PROBE = os.environ.get("SPAIN_PROBE") == "1"
PROBE_NO_ZIP = os.environ.get("SPAIN_NO_ZIP") == "1"

# CODICE code lists (PLACSP)
NATURE = {"1": "supplies", "2": "services", "3": "works", "21": "services", "22": "services", "31": "works", "32": "services",
          "40": "services", "7": "services", "8": "services", "50": "other", "999": "other"}
PROC = {"1": "Abierto", "2": "Restringido", "3": "Negociado con publicidad", "4": "Negociado sin publicidad", "5": "Diálogo competitivo",
        "6": "Concurso de proyectos", "7": "Abierto simplificado", "8": "Asociación para la innovación", "9": "Basado en acuerdo marco",
        "10": "Licitación con negociación", "11": "Licitación con negociación", "100": "Normas internas", "999": "Otros"}
OPEN = {"PUB"}  # PRE = anuncio previo, EV = en evaluación, ADJ/RES = adjudicada/resuelta, ANUL = anulada

REGIONS = ["Andalucía", "Aragón", "Asturias", "Canarias", "Cantabria", "Castilla y León", "Castilla-La Mancha", "Cataluña", "Ceuta",
           "Comunidad de Madrid", "Comunitat Valenciana", "Extremadura", "Galicia", "Illes Balears", "La Rioja", "Melilla", "Navarra",
           "País Vasco", "Región de Murcia"]
PROV = {  # INE province code (first 2 digits of the postal code) → (province, region)
    "01": ("Araba/Álava", "País Vasco"), "02": ("Albacete", "Castilla-La Mancha"), "03": ("Alicante", "Comunitat Valenciana"),
    "04": ("Almería", "Andalucía"), "05": ("Ávila", "Castilla y León"), "06": ("Badajoz", "Extremadura"), "07": ("Illes Balears", "Illes Balears"),
    "08": ("Barcelona", "Cataluña"), "09": ("Burgos", "Castilla y León"), "10": ("Cáceres", "Extremadura"), "11": ("Cádiz", "Andalucía"),
    "12": ("Castellón", "Comunitat Valenciana"), "13": ("Ciudad Real", "Castilla-La Mancha"), "14": ("Córdoba", "Andalucía"),
    "15": ("A Coruña", "Galicia"), "16": ("Cuenca", "Castilla-La Mancha"), "17": ("Girona", "Cataluña"), "18": ("Granada", "Andalucía"),
    "19": ("Guadalajara", "Castilla-La Mancha"), "20": ("Gipuzkoa", "País Vasco"), "21": ("Huelva", "Andalucía"), "22": ("Huesca", "Aragón"),
    "23": ("Jaén", "Andalucía"), "24": ("León", "Castilla y León"), "25": ("Lleida", "Cataluña"), "26": ("La Rioja", "La Rioja"),
    "27": ("Lugo", "Galicia"), "28": ("Madrid", "Comunidad de Madrid"), "29": ("Málaga", "Andalucía"), "30": ("Murcia", "Región de Murcia"),
    "31": ("Navarra", "Navarra"), "32": ("Ourense", "Galicia"), "33": ("Asturias", "Asturias"), "34": ("Palencia", "Castilla y León"),
    "35": ("Las Palmas", "Canarias"), "36": ("Pontevedra", "Galicia"), "37": ("Salamanca", "Castilla y León"),
    "38": ("Santa Cruz de Tenerife", "Canarias"), "39": ("Cantabria", "Cantabria"), "40": ("Segovia", "Castilla y León"),
    "41": ("Sevilla", "Andalucía"), "42": ("Soria", "Castilla y León"), "43": ("Tarragona", "Cataluña"), "44": ("Teruel", "Aragón"),
    "45": ("Toledo", "Castilla-La Mancha"), "46": ("Valencia", "Comunitat Valenciana"), "47": ("Valladolid", "Castilla y León"),
    "48": ("Bizkaia", "País Vasco"), "49": ("Zamora", "Castilla y León"), "50": ("Zaragoza", "Aragón"), "51": ("Ceuta", "Ceuta"),
    "52": ("Melilla", "Melilla"),
}
NUTS2 = {"ES11": "Galicia", "ES12": "Asturias", "ES13": "Cantabria", "ES21": "País Vasco", "ES22": "Navarra", "ES23": "La Rioja",
         "ES24": "Aragón", "ES30": "Comunidad de Madrid", "ES41": "Castilla y León", "ES42": "Castilla-La Mancha", "ES43": "Extremadura",
         "ES51": "Cataluña", "ES52": "Comunitat Valenciana", "ES53": "Illes Balears", "ES61": "Andalucía", "ES62": "Región de Murcia",
         "ES63": "Ceuta", "ES64": "Melilla", "ES70": "Canarias"}
# words in a buyer or parent name that give its region (aggregated platforms often send no address)
REGION_WORDS = [
    ("Cataluña", r"catalu|catalunya|generalitat de catalunya|\bics\b|barcelona|girona|lleida|tarragona"),
    ("País Vasco", r"euskadi|pais vasco|eusko|osakidetza|bizkaia|gipuzkoa|araba|alava|\budala\b|bilbao|donostia|vitoria"),
    ("Galicia", r"galicia|xunta|sergas|concello|a coruna|lugo|ourense|pontevedra|vigo"),
    ("Andalucía", r"andaluc|sevilla|malaga|cordoba|granada|almeria|huelva|jaen|cadiz"),
    ("Navarra", r"navarra|nafarroa|pamplona|iruna"),
    ("Comunidad de Madrid", r"comunidad de madrid|madrid|canal de isabel ii"),
    ("Comunitat Valenciana", r"valencian|generalitat valenciana|alicante|alacant|castell[oó]n|valencia"),
    ("Illes Balears", r"balear|mallorca|menorca|eivissa|ibiza|formentera"),
    ("Canarias", r"canari|tenerife|las palmas|gran canaria|lanzarote|fuerteventura|la palma|la gomera|el hierro"),
    ("La Rioja", r"la rioja|logrono"),
    ("Región de Murcia", r"murcia|cartagena"),
    ("Aragón", r"arag[oó]n|zaragoza|huesca|teruel"),
    ("Asturias", r"asturias|oviedo|gijon"),
    ("Cantabria", r"cantabria|santander"),
    ("Castilla y León", r"castilla y leon|valladolid|burgos|leon|salamanca|segovia|soria|zamora|palencia|avila"),
    ("Castilla-La Mancha", r"castilla-la mancha|castilla la mancha|toledo|albacete|cuenca|guadalajara|ciudad real"),
    ("Extremadura", r"extremadura|badajoz|caceres"),
    ("Ceuta", r"ceuta"), ("Melilla", r"melilla"),
]

LEVELS = ["nacional", "autonomico", "diputacion", "comarca", "ayuntamiento", "otros"]
RX = {
    "diputacion": re.compile(r"diputaci|empresa provincial|organismo provincial|instituto provincial|patronato provincial|foru aldundi|\bcabildo|consell insular|consell de (mallorca|menorca|eivissa|formentera)"),
    "comarca": re.compile(r"consell comarcal|consejo comarcal|^(presiden\w* de la )?comarca (de|del|d')|^comarcas$|mancomunida|mancomunitat|cuadrilla d|comunidad de villa y tierra"),
    "ayuntamiento": re.compile(r"ayuntamiento|ajuntament|concello|\budala\b|udalerri|alcald|junta de gobierno local|entidad local menor|junta vecinal|"
                               r"\bconcejo\b|consistori|\bmunicipal|ayto\.?\b|\bconcellos?\b"),
    "autonomico": re.compile(r"comunidades y ciudades autonomas|comunidades autonomas|comunidad autonoma|corts valencianes|conseller|consejer|generalitat|xunta|junta de andalucia|junta de castilla|"
                             r"junta de extremadura|junta de comunidades|gobierno de (aragon|canarias|cantabria|la rioja|navarra)|gobierno vasco|"
                             r"eusko jaurlaritza|principado de asturias|comunidad de madrid|region de murcia|govern de les illes|govern balear|"
                             r"servicio (andaluz|madrileno|gallego|canario|murciano|riojano|navarro|aragones|extremeno|cantabro|de salud de)|osakidetza|"
                             r"sergas|institut catala|departament d|departamento de|ciudad autonoma|parlament|parlamento de|"
                             r"agencia (andaluza|vasca|gallega|valenciana|catalana)|^axencia|xunta de galicia|eusko trenbide|euskal trenbide|nasuvinsa|"
                             r"transformacion de la rioja|ferrocarrils de la generalitat|metro de madrid|canal de isabel ii|servei catala|institut catala"),
    "nacional": re.compile(r"administracion general del estado|estatales$|ministerio|secretaria de estado|secretaria general de|agencia estatal|"
                           r"guardia civil|policia nacional|ejercito|armada espanola|\barmada\b|estado mayor|adif|aena|renfe|puertos del estado|"
                           r"autoridad portuaria|confederacion hidrografica|tesoreria general|instituto nacional|servicio publico de empleo estatal|"
                           r"sociedad estatal|correos|paradores|consejo superior de investigaciones|seguridad social|delegacion del gobierno|"
                           r"subdelegacion del gobierno|jefatura central|mutualidad general|fabrica nacional|senado|congreso de los diputados|"
                           r"tribunal (supremo|constitucional|de cuentas)|consejo general del poder judicial|ineco|tragsa|sepes|enaire|"
                           r"direccion general de (trafico|la guardia|la policia)|organismo autonomo parques nacionales|loterias"),
}


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def local(tag):
    return tag.rsplit("}", 1)[-1]


def kids(el, name):
    return [c for c in el if local(c.tag) == name] if el is not None else []


def kid(el, *path):
    for name in path:
        if el is None:
            return None
        el = next((c for c in el if local(c.tag) == name), None)
    return el


def txt(el, *path):
    e = kid(el, *path)
    return (e.text or "").strip() if e is not None and e.text else ""


def deep(el, name):
    """Every descendant called name (any namespace)."""
    return [e for e in el.iter() if local(e.tag) == name] if el is not None else []


def parent_chain(party_el):
    """LocatedContractingParty → [nearest parent name, …, top name] from the nested ParentLocatedParty elements."""
    out, p = [], kid(party_el, "ParentLocatedParty")
    while p is not None:
        n = txt(p, "PartyName", "Name")
        if n:
            out.append(n)
        p = kid(p, "ParentLocatedParty")
    return out


def classify(buyer, parents, ptype):
    """Level of government of the buyer. Name first (most specific), then the PLACSP tree, then the party type code."""
    nb = norm(buyer)
    for lvl in ("diputacion", "comarca", "ayuntamiento"):
        if RX[lvl].search(nb):
            return lvl
    if RX["autonomico"].search(nb) and not RX["nacional"].search(nb):
        return "autonomico"
    if RX["nacional"].search(nb):
        return "nacional"
    for p in parents:
        np_ = norm(p)
        for lvl in ("diputacion", "comarca", "ayuntamiento"):
            if RX[lvl].search(np_):
                return lvl
        if RX["nacional"].search(np_):
            return "nacional"
        if RX["autonomico"].search(np_):
            return "autonomico"
        if "entidades locales" in np_:
            return "otros_local"
    return {"1": "nacional", "2": "autonomico", "3": "otros_local"}.get(ptype, "otros")


def region_of(pc, nuts, names):
    pc = re.sub(r"\D", "", pc or "")
    if len(pc) == 5 and pc[:2] in PROV:
        return PROV[pc[:2]]
    for n in nuts:
        if n[:4] in NUTS2:
            return "", NUTS2[n[:4]]
    blob = norm(" ".join(names))
    for reg, rx in REGION_WORDS:
        if re.search(rx, blob):
            return "", reg
    return "", ""


def amount(el, *names):
    for n in names:
        for e in deep(el, n):
            try:
                v = float(e.text)
                if v > 0:
                    return int(v)
            except (TypeError, ValueError):
                pass
    return None


CONCESSION = {"21", "22", "31", "32"}  # gestión de servicios públicos, concesión de servicios / de obras
RX_PRICE = re.compile(r"\b(precio|price|oferta econ|econ[oó]mic|import|coste|cost|baja|tarifa|canon)", re.I)
RX_NGEU = re.compile(r"next ?generation|nextgen|\bngeu\b|\bprtr\b|\bmrr\b|plan de recuperaci|mecanismo de recuperaci|recovery and resilience", re.I)
RX_EU = re.compile(r"\bfeder\b|\bfse\+?\b|\bfeader\b|\bfemp|\bfempa\b|fondos? europeos?|uni[oó]n europea|\bue\b|\beu\b|interreg|\bpoctep\b|cohesi[oó]n", re.I)


def lots_of(cfs):
    """Number of lots (0 = not split into lots)."""
    return len([e for e in deep(cfs, "ProcurementProjectLot")])


def award_of(cfs):
    """'price' when price/cost is the only award criterion, 'quality' when there are others, '' unknown.
    CODICE: AwardingCriteriaTypeCode OBJ (formula) / SUBJ (judgement); SubTypeCode 1 = price."""
    crit = deep(cfs, "AwardingCriteria")
    if not crit:
        return ""
    for c in crit:
        if txt(c, "AwardingCriteriaTypeCode").upper().startswith("SUBJ"):
            return "quality"
        sub = txt(c, "AwardingCriteriaSubTypeCode").lstrip("0")
        d = " ".join((e.text or "") for e in c.iter() if local(e.tag) in ("Description", "Name"))
        if sub != "1" and not (not sub and RX_PRICE.search(d)) and not (sub in ("", "99") and RX_PRICE.search(d)):
            return "quality"
    return "price"


def funds_of(cfs, text):
    """'ngeu' Next Generation EU / PRTR, 'eu' other EU funds, 'none'."""
    codes = [(e.text or "").strip().upper() for e in deep(cfs, "FundingProgramCode") if e.text]
    names = " ".join((e.text or "") for e in deep(cfs, "FundingProgram") if e.text)
    blob = " ".join(codes) + " " + names
    if RX_NGEU.search(blob) or RX_NGEU.search(text):
        return "ngeu"
    if any(c and c not in ("NO-EU", "NOEU", "NO") for c in codes) or RX_EU.search(names):
        return "eu"
    return "none"


def rec(entry, today):
    """Atom entry → (id, updated, record or None if not open)."""
    A = lambda name: kid(entry, name)  # noqa: E731
    eid = (A("id").text or "").strip() if A("id") is not None else ""
    upd = (A("updated").text or "").strip() if A("updated") is not None else ""
    cfs = next((e for e in entry if local(e.tag) == "ContractFolderStatus"), None)
    if cfs is None:
        return eid, upd, None
    status = txt(cfs, "ContractFolderStatusCode")
    if status not in OPEN:
        return eid, upd, None
    tp = kid(cfs, "TenderingProcess")
    dl = txt(tp, "TenderSubmissionDeadlinePeriod", "EndDate")[:10]
    if not dl or dl < today:
        return eid, upd, None
    party = kid(cfs, "LocatedContractingParty")
    p = kid(party, "Party")
    buyer = txt(p, "PartyName", "Name")
    parents = parent_chain(party)
    ptype = txt(party, "ContractingPartyTypeCode")
    pp = kid(cfs, "ProcurementProject")
    title = txt(pp, "Name") or ((A("title").text or "").strip() if A("title") is not None else "")
    link = next((l.get("href") for l in kids(entry, "link") if l.get("href") and l.get("rel") in (None, "alternate")), "")
    cpvs = []
    for c in deep(pp, "ItemClassificationCode"):
        v = (c.text or "").strip()[:8]
        if v and v not in cpvs:
            cpvs.append(v)
    nuts = [(e.text or "").strip() for e in deep(pp, "CountrySubentityCode") + deep(p, "CountrySubentityCode") if e.text]
    city = txt(p, "PostalAddress", "CityName")
    pc = txt(p, "PostalAddress", "PostalZone")
    prov, reg = region_of(pc, nuts, [buyer] + parents + [city])
    lvl = classify(buyer, parents, ptype)
    if lvl == "otros_local":
        lvl = "otros"
    pubs = sorted(d.text[:10] for d in deep(cfs, "IssueDate") if d.text and re.match(r"\d{4}-\d{2}-\d{2}", d.text))
    summary = (kid(entry, "summary").text or "") if kid(entry, "summary") is not None else ""
    tcode = txt(pp, "TypeCode")
    r = {
        "id": eid.rsplit("/", 1)[-1],
        "ref": txt(cfs, "ContractFolderID")[:60],
        "title": re.sub(r"\s+", " ", title).strip()[:300],
        "buyer": re.sub(r"\s+", " ", buyer).strip()[:160],
        "level": lvl, "region": reg, "province": prov, "city": city[:60].title() if city.isupper() else city[:60],
        "nature": NATURE.get(txt(pp, "TypeCode"), ""),
        "procedure": PROC.get(txt(tp, "ProcedureCode"), ""),
        "cpv": cpvs[:3],
        "published": pubs[0] if pubs else (upd[:10] or None),
        "deadline": dl, "time": txt(tp, "TenderSubmissionDeadlinePeriod", "EndTime")[:5] or None,
        "value": amount(pp, "EstimatedOverallContractAmount", "TaxExclusiveAmount", "TotalAmount"),
        "url": link,
        "concession": tcode in CONCESSION,
        "lots": lots_of(cfs),
        "award": award_of(cfs),
        "funds": funds_of(cfs, title + " " + summary),
    }
    if PROBE:
        r["_ptype"], r["_parents"], r["_summary"] = ptype, parents, summary[:200]
    return eid, upd, r


def get(url, retries=5):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/atom+xml,application/xml"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == retries - 1:
                raise
            print(f"  retry {url[-60:]}: {e}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))


def walk(name, url, today, stop_at, cache, gone):
    """Read pages newest → oldest until an entry older than stop_at. First sight of an id = its latest state.
    gone: ids already seen closed (and, when resuming a deep walk, every id read so far), never overwritten by an older state."""
    seen, pages, n_entries, t0 = set(), 0, 0, time.time()
    newest, oldest = None, None
    while url and pages < MAX_PAGES and time.time() - t0 < TIME_BUDGET:
        raw = get(url)
        pages += 1
        root = ET.fromstring(raw)
        if PROBE and pages == 1:
            print(f"--- {name} page 1: {len(raw):,} bytes")
            e0 = next((e for e in root if local(e.tag) == "entry"), None)
            if e0 is not None:
                print(ET.tostring(e0, encoding="unicode")[:6000])
        stop = False
        for el in root:
            tag = local(el.tag)
            if tag == "deleted-entry":
                ref = el.get("ref") or ""
                if ref and ref not in seen:
                    seen.add(ref)
                    cache.pop(ref, None)
                continue
            if tag != "entry":
                continue
            n_entries += 1
            eid, upd, r = rec(el, today)
            if upd:
                newest = max(newest or upd, upd)
                oldest = min(oldest or upd, upd)
            if upd and upd < stop_at:
                stop = True
                continue
            if not eid or eid in seen or eid in gone:
                continue
            seen.add(eid)
            if r:
                r["_upd"] = upd
                cache[eid] = r
            else:
                cache.pop(eid, None)
                gone.add(eid)
        nxt = next((l.get("href") for l in root if local(l.tag) == "link" and l.get("rel") == "next"), None)
        if pages % 25 == 0 or PROBE:
            print(f"  {name} page {pages}: {n_entries:,} entries, back to {oldest}, open kept {len(cache):,} ({time.time() - t0:.0f}s)")
        if stop or nxt == url:
            break
        url = nxt
        time.sleep(0.3)
    complete = stop or not url
    print(f"  {name}: {pages} pages, {n_entries:,} entries, {newest} → {oldest}, complete={complete}")
    return newest, complete, (None if complete else url)


def months_back(now, days):
    """['202609', '202610', '202611'] for the months that overlap the last `days` days, oldest first."""
    out, d = [], (now - timedelta(days=days)).date().replace(day=1)
    while d <= now.date():
        out.append(f"{d.year}{d.month:02d}")
        d = (d + timedelta(days=32)).replace(day=1)
    return out


def backfill(name, url, today, now):
    """Latest state of every tender updated in the last DAYS_BACK days, from the monthly zips of the feed
    (<feed>_YYYYMM.zip next to the .atom: every Atom page published that month)."""
    import tempfile
    import zipfile
    best, t0 = {}, time.time()
    for ym in months_back(now, DAYS_BACK):
        zurl = url.replace(".atom", f"_{ym}.zip")
        with tempfile.TemporaryFile() as tmp:
            req = urllib.request.Request(zurl, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=600) as r:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    tmp.write(chunk)
            size = tmp.tell()
            tmp.seek(0)
            zf = zipfile.ZipFile(tmp)
            members = [m for m in zf.namelist() if m.endswith(".atom")]
            n = 0
            for m in members:
                root = ET.fromstring(zf.read(m))
                for el in root:
                    tag = local(el.tag)
                    if tag == "deleted-entry":
                        ref, when = el.get("ref") or "", el.get("when") or ""
                        if ref and when >= best.get(ref, ("", None))[0]:
                            best[ref] = (when, None)
                        continue
                    if tag != "entry":
                        continue
                    n += 1
                    eid, upd, r = rec(el, today)
                    if eid and upd >= best.get(eid, ("", None))[0]:
                        best[eid] = (upd, r)
            print(f"  {name} {ym}: {size / 1e6:.0f} MB, {len(members)} pages, {n:,} entries ({time.time() - t0:.0f}s)")
    cache = {}
    for eid, (upd, r) in best.items():
        if r:
            r["_upd"] = upd
            cache[eid] = r
    newest = max((u for u, _ in best.values()), default=None)
    print(f"  {name} backfill: {len(best):,} tenders, {len(cache):,} open, newest {newest}")
    return cache, newest


def main():
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    allrecs = {}
    for name, url in FEEDS.items():
        cf = CACHE / f"spain2_{name}.json"  # v2: + lots, award, funds, concession
        st = json.loads(cf.read_text(encoding="utf-8")) if cf.exists() else {}
        cache = st.get("records", {})
        if not (st.get("complete") and st.get("newest")) and not PROBE_NO_ZIP:
            # first run (no cache): read the monthly zips of the last DAYS_BACK days, much faster than paging the feed
            try:
                cache, newest = backfill(name, url, today, now)
                st = {"records": cache, "newest": newest, "complete": True, "resume": None, "gone": []}
            except Exception as e:
                print(f"::warning::{name}: monthly zips failed ({e}); paging the feed instead")
        # resume an unfinished deep walk from where it stopped; otherwise walk back to the last newest entry read
        if st.get("complete") and st.get("newest"):
            stop_at = (datetime.fromisoformat(st["newest"]) - OVERLAP).isoformat()
            start = url
        else:
            stop_at = (now - timedelta(days=DAYS_BACK)).isoformat()
            start = st.get("resume") or url
        print(f"Fetching {name} (stop at {stop_at[:16]}, cached open {len(cache):,})…")
        try:
            was_complete = bool(st.get("complete"))
            # resuming a deep walk: ids read in earlier runs already hold a newer state
            gone = set(st.get("gone", [])) | (set(cache) if not was_complete and st.get("resume") else set())
            newest, complete, resume = walk(name, start, today, stop_at, cache, gone)
            complete = complete or was_complete
            st = {"records": cache, "newest": max(filter(None, [newest, st.get("newest")]), default=None),
                  "complete": complete, "resume": resume, "gone": [] if complete else sorted(gone)}
        except Exception as e:
            print(f"::warning::{name} feed failed ({e}); using the cache of the previous run")
        cache = {k: v for k, v in cache.items() if v.get("deadline", "") >= today}
        st["records"] = cache
        if not PROBE:
            cf.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
        for k, v in cache.items():
            v["src"] = name
            allrecs[k] = v
    # same tender on both feeds (a few platforms publish twice): keep one per buyer + reference
    out, dup = {}, 0
    for v in allrecs.values():
        key = (norm(v["buyer"]), v["ref"] or v["id"])
        if key in out:
            dup += 1
            continue
        out[key] = v
    recs = sorted(out.values(), key=lambda x: (x["deadline"], x["title"]))
    for v in recs:
        v.pop("_upd", None)
    week = (now.date() + timedelta(days=7)).isoformat()
    month = (now.date() + timedelta(days=30)).isoformat()
    lv = Counter(x["level"] for x in recs)
    stats = {
        "updated": now.isoformat(timespec="seconds"), "total": len(recs),
        "levels": {k: lv.get(k, 0) for k in LEVELS},
        "closingIn7Days": sum(1 for x in recs if x["deadline"] <= week),
        "closingIn30Days": sum(1 for x in recs if x["deadline"] <= month),
        "regions": dict(sorted(Counter(x["region"] for x in recs if x["region"] and x["level"] != "nacional").items())),
        "regionLevels": {r: dict(Counter(x["level"] for x in recs if x["region"] == r and x["level"] != "nacional")) for r in REGIONS},
        "provinces": dict(sorted(Counter(x["province"] for x in recs if x["province"]).items())),
        "nature": dict(Counter(x["nature"] or "other" for x in recs)),
        "funds": dict(Counter(x.get("funds") or "none" for x in recs)),
        "award": dict(Counter(x.get("award") or "unknown" for x in recs)),
        "splitIntoLots": sum(1 for x in recs if (x.get("lots") or 0) > 1),
        "concessions": sum(1 for x in recs if x.get("concession")),
        "duplicatesDropped": dup,
        "source": "Plataforma de Contratación del Sector Público (Ministerio de Hacienda), incl. plataformas autonómicas agregadas",
    }
    print(json.dumps({k: v for k, v in stats.items() if k not in ("provinces", "regionLevels")}, ensure_ascii=False, indent=1))
    if PROBE:
        for lvl in LEVELS:
            sample = [x for x in recs if x["level"] == lvl][:6]
            print(f"--- {lvl}: {lv.get(lvl, 0)}")
            for x in sample:
                print("   ", x["buyer"], "|", x["_parents"][:4], "| ptype", x["_ptype"], "|", x["region"], x["province"], "|", x["title"][:70])
        print("ptype×level", Counter((x["_ptype"], x["level"]) for x in recs).most_common(30))
        print("no region", sum(1 for x in recs if not x["region"]), [x["buyer"] for x in recs if not x["region"]][:20])
        print("top parents", Counter(" > ".join(reversed(x["_parents"][:3])) for x in recs).most_common(40))
        print("otros buyers", Counter(x["buyer"] for x in recs if x["level"] == "otros").most_common(40))
        print("no value", sum(1 for x in recs if not x["value"]), "no url", sum(1 for x in recs if not x["url"]), "no nature", sum(1 for x in recs if not x["nature"]))
        print(json.dumps(recs[:3], ensure_ascii=False, indent=1))
    for v in recs:
        for k in [k for k in v if k.startswith("_")]:
            v.pop(k)
        for k in [k for k, val in v.items() if val in (None, "", [])]:
            v.pop(k)
    (OUT / "spain.json").write_text(json.dumps(recs, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUT / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
