# Hoja de reglas del diagnóstico (`tenders/fichas/<id>/reglas.json`)

Cada ficha con `reglas.json` tiene su diagnóstico gratuito en `/es/espana/licitacion/<id>/diagnostico/`.
La IA conversa y redacta, pero las cuentas las hace siempre `engine.js` con estas reglas: nada de lo que sale en el informe se inventa en el momento.

## Cómo se genera para una ficha nueva

1. Al hacer la ficha (leyendo todos los documentos oficiales), la IA rellena `reglas.json` con el esquema de abajo. **Cada dato lleva su cita** (`PCAP p.9`, `ANX p.22`…).
2. Revisión automática: `node tenders/diagnostico/check.js <id>` comprueba que suman los puntos, que hay un criterio de precio y una regla de baja anormal, que los importes de los lotes cuadran con la ficha y que las fechas son coherentes.
3. Revisión humana por muestreo: un consultor revisa **1 de cada 20** hojas (y todas las que el control marca como dudosas) antes de que pasen 48 h.

## Esquema (versión 1)

| Campo | Qué es |
|---|---|
| `id`, `title`, `buyer`, `buyer_key`, `province`, `cpv`, `ref`, `official_url` | Identificación. `buyer_key` = nombre del órgano tal como sale en la Plataforma (sirve para buscar su competencia histórica) |
| `deadline`, `deadline_time`, `questions_until`, `opening_days` | Fechas; con ellas se construye la hoja de ruta hacia atrás desde el cierre |
| `envelopes`, `judgement_pts` | Número de sobres y puntos de juicio de valor |
| `lots[]` | `n`, `label`, `budget` (sin IVA), y si aplica `works`, `buildings`, `months` |
| `max_lots_award`, `max_lots_per_team`, `lots_rule` | Límites de lotes |
| `requirements[]` | Requisitos de solvencia. `kind`: `number_vs_lot` (cifra ≥ `factor` × `basis` del lote), `number_min` (cifra ≥ `min`), `yesno`, `roles_vs_lot` (cada técnico ≥ `factor` × `basis`). Cada uno con `question`, `rule`, `proof`, `cite` |
| `roles[]`, `roles_question` | Técnicos que puntúan o se exigen (solo cifras, nunca nombres) |
| `criteria[]` | Criterios de adjudicación. `kind`: `price` (`formula`: `mean_k`, `proportional`, `linear_min`…), `role_excess` (`steps` [[exceso, puntos]]), `choice` (`options` con puntos), `judgement` (juicio de valor) |
| `abnormal` | Baja anormal: `kind` `below_mean_pp` (media + `pp` puntos), `single_pct` si hay una sola oferta, `accept_rate` supuesto de aceptación |
| `effort` | Para «¿te sale a cuenta?»: `presence` (semanas × horas) o `hours` fijas |
| `guarantee` | Garantía definitiva y complementaria (%) |
| `risk_flags[]` | Riesgos del contrato con `weight` (restan de los 15 puntos de riesgo) |
| `solvency_paths` | Integración de solvencia (art. 75), UTE (art. 69), subcontratación (art. 215) |
| `specific_checks[]` | Causas de exclusión propias de esta licitación (se suman a la lista general) |
| `docs_envelopes[]` | Tareas de la hoja de ruta: `when` = días antes del cierre |
| `known_issues[]` | Contradicciones entre documentos: se avisan y se sugiere preguntar |

## Prompt para generar la hoja

> Has leído todos los documentos oficiales de la licitación <id>. Rellena `reglas.json` siguiendo `tenders/diagnostico/REGLAS.md` y el ejemplo `tenders/fichas/20957771/reglas.json`.
> Reglas: copia los importes y porcentajes exactos del pliego; pon la cita (documento y página) de cada requisito, criterio y fecha; si un dato no está claro, ponlo en `known_issues` o en la `note` correspondiente en vez de suponer; usa lenguaje sencillo en `question`, `rule` y `how` (sin jerga, frases que entienda un gerente de pyme); no incluyas datos personales ni nombres de empresas.

## Datos de competencia

`tenders/awards_spain.py` lee las adjudicaciones de la Plataforma (meses en zip) y publica solo agregados: número de ofertas y rebaja media por órgano + tipo de servicio, provincia + tipo, o tipo en toda España. Con menos de 10 adjudicaciones comparables el diagnóstico usa datos ilustrativos y lo dice («confianza orientativa»). El perfil de cada empresa se busca por el CIF cifrado (sha256), nunca guardamos ni mostramos nombres de competidores.

## Envío al equipo

Cuando alguien pide el informe completo o pulsa «Reservar», la página avisa al Worker (`POST /diagnostico`), que lo guarda 12 meses y pide al Worker `ullswater-fichas` (enlace interno `MAILER`, el mismo que ya envía los emails de las fichas con Resend) que mande un email a **tenders@ullswaterinvestments.com** con respuesta directa a la empresa.
