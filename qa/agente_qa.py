"""Agente de pruebas del Asistente de ayudas de Ullswater.
Hace las preguntas pendientes de questions.json al chat de www (igual que el widget de la portada /es/ o /),
guarda la respuesta tal cual (Markdown con enlaces), las fuentes que muestra el widget, el motor, el tiempo,
y comprueba que los enlaces responden. Resultados en results.json (acumulativo).

Uso: python3 agente_qa.py --max 18 [--ids Q0001,Q0002] [--pausa 3]
"""
import argparse, json, re, time, urllib.request, urllib.error, concurrent.futures as cf, datetime, os

API = "https://ullswater-ai.emilio-mulet-b52.workers.dev/ask"
ORIGIN = "https://www.ullswaterinvestments.com"
HERE = os.path.dirname(os.path.abspath(__file__))
QA_KEY = os.environ.get("QA_KEY", "")  # GitHub secret QA_KEY (same value as the Worker secret)
LINK_MD = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)")
LINK_RAW = re.compile(r"(?<!\()https?://[^\s)\]>\"']+")

def ask(q, lang, topic):
    page = {"host": "www.ullswaterinvestments.com", "path": "/es/" if lang == "es" else "/",
            "title": "Ullswater Investments", "lang": "es" if lang == "es" else "en", "site": "www"}
    body = {"q": q, "history": [], "stream": True, "page": page}
    if topic: body["topic"] = 1
    req = urllib.request.Request(API, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Origin": ORIGIN, "User-Agent": "Ullswater-QA-agent/1.0",
                                          **({"X-QA-Key": QA_KEY} if QA_KEY else {})})
    t0 = time.time(); txt, done, err, status = "", None, None, None
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            status = r.status
            if "event-stream" not in r.headers.get("Content-Type", ""):
                d = json.loads(r.read()); return d.get("answer", ""), d, d.get("error"), status, time.time() - t0
            buf = ""
            for raw in r:
                buf += raw.decode("utf-8", "replace").replace("\r", "")
                while "\n\n" in buf:
                    ev, buf = buf.split("\n\n", 1)
                    for line in ev.split("\n"):
                        if not line.startswith("data:"): continue
                        try: e = json.loads(line[5:].strip())
                        except Exception: continue
                        if e.get("type") == "delta": txt += e.get("text", "")
                        elif e.get("type") == "done": done = e
                        elif e.get("type") == "error": err = e.get("text")
    except urllib.error.HTTPError as e:
        status = e.code
        try: err = json.loads(e.read()).get("error")
        except Exception: err = str(e)
    except Exception as e:
        err = str(e)
    return txt, done or {}, err, status, time.time() - t0

def links_of(text, sources):
    out = []
    for t, u in LINK_MD.findall(text): out.append(("respuesta", t, u))
    stripped = LINK_MD.sub("", text)
    for u in LINK_RAW.findall(stripped): out.append(("respuesta (URL suelta)", u, u.rstrip(".,;:")))
    for s in sources or []:
        if s.get("url"): out.append(("fuente", s.get("title") or s.get("id") or "", s["url"]))
    return out

_cache = {}
def check(url):
    if url in _cache: return _cache[url]
    code = None
    for m in ("HEAD", "GET"):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, method=m, headers={"User-Agent": "Mozilla/5.0 (Ullswater QA)"}), timeout=20)
            code = r.status; break
        except urllib.error.HTTPError as e:
            code = e.code
            if code not in (403, 405, 400): break
        except Exception as e:
            code = "error: " + type(e).__name__
    _cache[url] = code; return code

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--max", type=int, default=18); ap.add_argument("--ids", default="")
    ap.add_argument("--pausa", type=float, default=2); a = ap.parse_args()
    Q = json.load(open(os.path.join(HERE, "questions.json")))
    rp = os.path.join(HERE, "results.json")
    R = json.load(open(rp)) if os.path.exists(rp) else {}
    todo = [q for q in Q if (q["id"] in a.ids.split(",")) ] if a.ids else [q for q in Q if q["id"] not in R or R[q["id"]].get("estado") == "error"]
    for q in todo[: a.max]:
        txt, done, err, status, secs = ask(q["pregunta"], q["idioma"], q["tipo"] == "etiqueta")
        if status == 429:
            print("Límite de preguntas por hora/día alcanzado; paro aquí."); break
        L = links_of(txt, done.get("sources"))
        with cf.ThreadPoolExecutor(8) as ex: codes = list(ex.map(check, [u for _, _, u in L]))
        bad = [f"{u} → {c}" for (_, _, u), c in zip(L, codes) if not (isinstance(c, int) and c < 400)]
        R[q["id"]] = dict(estado="error" if (err or not txt) else "respondida",
                          fecha=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), motor=done.get("engine"),
                          segundos=round(secs, 1), respuesta=txt.strip(), error=err,
                          enlaces=[dict(donde=d, texto=t, url=u, http=c) for (d, t, u), c in zip(L, codes)],
                          enlaces_rotos=bad, palabras=len(txt.split()), etiquetas=done.get("suggest") or [])
        json.dump(R, open(rp, "w"), ensure_ascii=False, indent=1)
        print(q["id"], R[q["id"]]["estado"], done.get("engine"), f"{secs:.1f}s", len(L), "enlaces", ("ROTOS: " + "; ".join(bad)) if bad else "")
        time.sleep(a.pausa)

if __name__ == "__main__":
    main()
