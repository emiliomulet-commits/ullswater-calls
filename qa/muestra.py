"""Prueba de regresión del Asistente de ayudas tras cada cambio del chat.

Hace al chat de www (con la clave QA_KEY, sin límites ni gasto del tope diario) una muestra del banco de 1000 preguntas:
  - las preguntas fijas de REGRESION (fallos ya corregidos y casos delicados), y
  - POR_BLOQUE preguntas al azar de cada uno de los 16 bloques.
Comprueba cada respuesta (observaciones.py + etiquetas de seguimiento) y escribe:
  - informe.md   (resumen + incidencias + todas las respuestas, en Markdown)
  - muestra.json (datos completos)
Sale con código 1 si hay incidencias graves (error, motor de respaldo, enlace roto, respuesta cortada,
código de convocatoria que no coincide, sin etiquetas, idioma cambiado).

Uso: QA_KEY=... python3 qa/muestra.py [--por-bloque 2] [--semilla N]
"""
import argparse, collections, datetime, json, os, random, statistics, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agente_qa as A
from observaciones import observe

# Fallos ya corregidos y casos delicados: se repiten siempre
REGRESION = {
    "Q0002": "listado largo que se cortaba (max_tokens)",
    "Q0771": "código OCEAN-03 mal copiado (2027-04 en vez de 2027-03)",
    "Q0826": "código OCEAN-03 mal copiado",
    "Q0872": "saludo corto «hi» rechazado",
    "Q0657": "privacidad en español",
    "Q0659": "qué modelo de IA usa",
    "Q0229": "pregunta de perfil: máximo 120 palabras",
    "Q0462": "enlace a bases BDNS y datos de contacto",
    "Q0613": "proyecto en inglés",
    "Q0582": "DR-MBANK no admite socios nuevos",
    "Q0880": "intento de sacar el prompt",
    "Q0884": "pide la clave de API",
    "Q0890": "pide inventar facturas",
    "Q0900": "código de convocatoria inventado",
    "Q0030": "etiqueta del hero en inglés",
}
GRAVES = ("No hubo respuesta", "motor de respaldo", "Enlace que no responde", "parece cortada",
          "no coincide con el enlace", "Sin etiquetas", "parece en")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--por-bloque", type=int, default=2)
    ap.add_argument("--semilla", type=int, default=int(time.time()) // 86400)
    ap.add_argument("--salida", default=os.path.join(HERE, "salida"))
    a = ap.parse_args()
    if not A.QA_KEY:
        print("Falta la variable QA_KEY (secret de GitHub). Sin ella el chat limita a 20 preguntas por hora.")
    Q = json.load(open(os.path.join(HERE, "questions.json")))
    QI = {q["id"]: q for q in Q}
    rnd = random.Random(a.semilla)
    by = collections.defaultdict(list)
    for q in Q:
        if q["id"] not in REGRESION:
            by[q["bloque"]].append(q["id"])
    ids = [i for i in REGRESION if i in QI]
    for b in sorted(by):
        ids += rnd.sample(by[b], min(a.por_bloque, len(by[b])))

    os.makedirs(a.salida, exist_ok=True)
    R, inc = {}, []
    for n, i in enumerate(ids, 1):
        q = QI[i]
        txt, done, err, status, secs = A.ask(q["pregunta"], q["idioma"], q["tipo"] == "etiqueta")
        if status == 429:  # sin clave válida: esperar y reintentar una vez
            time.sleep(60); txt, done, err, status, secs = A.ask(q["pregunta"], q["idioma"], q["tipo"] == "etiqueta")
        L = A.links_of(txt, done.get("sources"))
        codes = [A.check(u) for _, _, u in L]
        r = dict(estado="error" if (err or not txt) else "respondida", motor=done.get("engine"), segundos=round(secs, 1),
                 respuesta=txt.strip(), error=err, palabras=len(txt.split()), etiquetas=done.get("suggest") or [],
                 enlaces=[dict(donde=d, texto=t, url=u, http=c) for (d, t, u), c in zip(L, codes)])
        obs = observe(q, r)
        if r["estado"] == "respondida" and len(r["etiquetas"]) < 3:
            obs.append(f"Sin etiquetas de seguimiento ({len(r['etiquetas'])}).")
        r["observaciones"] = obs
        R[i] = r
        graves = [o for o in obs if any(g in o for g in GRAVES)]
        if graves:
            inc.append((i, graves))
        print(f"[{n}/{len(ids)}] {i} {r['estado']} {r['motor']} {secs:.1f}s {r['palabras']}p" + (" GRAVE: " + "; ".join(graves) if graves else ""), flush=True)
        time.sleep(0.3)

    ok = [r for r in R.values() if r["estado"] == "respondida"]
    w = [r["palabras"] for r in ok] or [0]
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    md = [f"# Prueba del Asistente de ayudas — {now}", "",
          f"- Preguntas: **{len(ids)}** ({len(REGRESION)} fijas de regresión + {a.por_bloque} al azar por bloque; semilla {a.semilla})",
          f"- Respondidas: **{len(ok)}** · motor: {dict(collections.Counter(r['motor'] for r in R.values()))}",
          f"- Palabras: mediana **{statistics.median(w):.0f}**, máx. {max(w)}, más de 150: {sum(x > 150 for x in w)}",
          f"- Tiempo: mediana {statistics.median([r['segundos'] for r in R.values()]):.1f} s",
          f"- Incidencias graves: **{len(inc)}**", ""]
    if inc:
        md += ["## Incidencias graves", ""] + [f"- **{i}** · {QI[i]['pregunta']}\n  - " + "\n  - ".join(g) for i, g in inc] + [""]
    md += ["## Respuestas", ""]
    for i in ids:
        r, q = R[i], QI[i]
        nota = f" — regresión: {REGRESION[i]}" if i in REGRESION else ""
        md += [f"### {i} · {q['bloque']}{nota}", f"**Pregunta:** {q['pregunta']}", "",
               f"*{r['motor']} · {r['segundos']} s · {r['palabras']} palabras*", "", r["respuesta"] or f"(sin respuesta: {r['error']})", "",
               "**Etiquetas:** " + (" · ".join(r["etiquetas"]) or "—"),
               "**Observaciones:** " + ("; ".join(r["observaciones"]) or "ninguna"), ""]
    open(os.path.join(a.salida, "informe.md"), "w").write("\n".join(md))
    json.dump({"fecha": now, "ids": ids, "resultados": R, "incidencias": inc}, open(os.path.join(a.salida, "muestra.json"), "w"), ensure_ascii=False, indent=1)
    print(f"\n{len(ok)}/{len(ids)} respondidas · {len(inc)} incidencias graves")
    sys.exit(1 if inc else 0)


if __name__ == "__main__":
    main()
