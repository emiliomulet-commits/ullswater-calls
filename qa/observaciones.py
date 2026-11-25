"""Comprobaciones automáticas del agente sobre cada respuesta (columna «Observaciones del agente»)."""
import re
LINK_MD_RE = re.compile(r"\[[^\]\n]+\]\(https?://[^\s)]+\)")

ID_RE = re.compile(r"\b((?:HORIZON|DIGITAL|ERASMUS|CREA|EDF|CERV|EUBA|EURATOM|ISF|SMP|JTM|CEF|LIFE|EU4H|I3|EMFAF|JUST|HUMA|PPPA|NDICI)-[A-Z0-9-]{4,})\b")
BOOKING = "outlook.office.com/bookwithme"
# sites that answer 403/417/429 to robots but work for people: not counted as broken links
BOT_BLOCKED = ("outlook.office.com/bookwithme", "acelerapyme.gob.es", "linkedin.com")
ES_WORDS = {"que", "para", "las", "los", "una", "convocatoria", "ayudas", "puedes", "está"}
EN_WORDS = {"the", "and", "for", "you", "calls", "funding", "which", "your", "can"}

def lang_of(t):
    w = re.findall(r"[a-záéíóúñ]+", t.lower())
    es = sum(x in ES_WORDS for x in w); en = sum(x in EN_WORDS for x in w)
    return "es" if es > en else "en" if en > es else "?"

def observe(q, r):
    notes = []
    if r.get("estado") != "respondida":
        return ["No hubo respuesta: " + str(r.get("error"))]
    txt = r["respuesta"]
    if r.get("motor") and r["motor"] not in ("claude", "cache"):
        notes.append(f"Respondió el motor de respaldo ({r['motor']}), no Claude.")
    real_bad = [e for e in r["enlaces"] if not (isinstance(e["http"], int) and e["http"] < 400) and not any(x in e["url"] for x in BOT_BLOCKED)]
    for e in real_bad:
        notes.append(f"Enlace que no responde ({e['http']}): {e['url']}")
    # ID de convocatoria escrito en el texto que no coincide con el enlace que lo acompaña
    for m in re.finditer(r"\]\((https?://calls\.ullswaterinvestments\.com/call/([a-z0-9-]+)/)\)\**\s*\(\**([A-Z][A-Z0-9]+-[A-Z0-9-]{6,})\**", txt):
        slug, cid = m.group(2), m.group(3)
        if cid.lower() != slug:
            notes.append(f"El código {cid} no coincide con el enlace (/call/{slug}/).")
    if q["idioma"] in ("es", "en") and len(txt) > 60:
        lg = lang_of(re.sub(r"\[[^\]]*\]\([^)]*\)|\*\*[^*]+\*\*", " ", txt))
        if lg != "?" and lg != q["idioma"]:
            notes.append(f"Pregunta en {q['idioma']} pero la respuesta parece en {lg}.")
    if r["palabras"] > 160:
        notes.append(f"Respuesta larga ({r["palabras"]} palabras; objetivo máx. 150).")
    if q["bloque"].startswith(("07", "08")) and not r["enlaces"]:
        notes.append("Pregunta sobre una convocatoria concreta sin ningún enlace.")
    if q["bloque"].startswith("07") and q["subtema"] not in txt:
        notes.append(f"No menciona el código {q['subtema']}.")
    if re.search(r"(?<!\()https?://[^\s)\]]+", LINK_MD_RE.sub("", txt)):
        notes.append("Tiene direcciones web sueltas en lugar de enlaces con texto.")
    if txt.rstrip()[-1:] not in ".!?)»*" and r["palabras"] > 30 and not re.search(r"https?://\S+$", txt.rstrip()):
        notes.append("La respuesta parece cortada al final.")
    return notes
