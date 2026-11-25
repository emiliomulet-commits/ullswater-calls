# Agente de pruebas del Asistente de ayudas

Pregunta al chat de la web (Worker `ullswater-ai`) igual que lo hace el widget de la portada, guarda las respuestas tal cual (con sus enlaces y etiquetas de seguimiento) y las comprueba.

## Automático: `.github/workflows/qa-chat.yml`
- Cuándo: después de cada despliegue del chat, cada lunes a las 06:23 UTC y con «Run workflow».
- Qué: 15 preguntas fijas de regresión (fallos ya corregidos y casos delicados, lista `REGRESION` en `muestra.py`) + 2 al azar de cada uno de los 16 bloques ≈ 47 preguntas, unos 6 minutos.
- Resultado: informe en el resumen de la ejecución y como artefacto (`informe.md` + `muestra.json`, 90 días). Si hay fallos graves, la ejecución sale en rojo y se abre una incidencia (issue).
- Fallos graves: sin respuesta, motor de respaldo, enlace roto, respuesta cortada, código de convocatoria que no coincide con su enlace, sin etiquetas de seguimiento, idioma cambiado.
- Necesita el secret de GitHub `QA_KEY` (Settings → Secrets and variables → Actions), con el mismo valor que el secret `QA_KEY` del Worker en Cloudflare. Con esa clave el chat no aplica el límite por IP ni gasta el tope diario de los visitantes, y registra las preguntas como `claude-qa`.

## Archivos
- `questions.json`: banco de 1000 preguntas (16 bloques; 870 en español, 124 en inglés, 6 en otros idiomas).
- `gen_questions.py`: genera el banco (usa `content.py` del repo ullswater-www para las 20 etiquetas de la portada).
- `agente_qa.py`: hace todas las preguntas pendientes y guarda `results.json` (uso local: `QA_KEY=... python3 qa/agente_qa.py --max 100`).
- `muestra.py`: la prueba de regresión (`QA_KEY=... python3 qa/muestra.py --por-bloque 2`).
- `observaciones.py`: comprobaciones automáticas de cada respuesta.

La hoja de validación con las 1000 respuestas está en Claude Sheets: https://claude.ai/artifact/RtkvM5nmUaRbkHwYHhFQkm
