#!/usr/bin/env node
/* Automatic check of a diagnosis rule sheet: node tenders/diagnostico/check.js <id> [<id>…] (no ids = every ficha).
 * Fails (exit 1) when the sheet cannot be right; warns when it needs a human look. Run by build_spain before publishing. */
const fs = require("fs"), path = require("path");
const dir = path.join(__dirname, "..", "fichas");
const ids = process.argv.slice(2).length ? process.argv.slice(2) : fs.readdirSync(dir).filter(i => fs.existsSync(path.join(dir, i, "reglas.json")));
const D = require("./engine.js");
let bad = 0;
for (const id of ids) {
  const errs = [], warns = [];
  let R;
  try { R = JSON.parse(fs.readFileSync(path.join(dir, id, "reglas.json"), "utf8")); } catch (e) { console.log(id + ": ERROR reglas.json no se puede leer: " + e.message); bad++; continue; }
  const pts = (R.criteria || []).reduce((s, c) => s + (c.pts || 0), 0);
  if (Math.abs(pts - 100) > 0.01) errs.push("los criterios suman " + pts + " puntos, no 100");
  if (!(R.criteria || []).some(c => c.kind === "price")) errs.push("falta el criterio de precio");
  if (!R.abnormal || !R.abnormal.kind) errs.push("falta la regla de baja anormal");
  if (!(R.lots || []).length || R.lots.some(l => !(l.budget > 0))) errs.push("algún lote no tiene presupuesto");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(R.deadline || "")) errs.push("fecha de cierre no válida");
  if (R.questions_until && R.questions_until > R.deadline) errs.push("el plazo de preguntas es posterior al cierre");
  const jp = (R.criteria || []).filter(c => c.kind === "judgement").reduce((s, c) => s + c.pts, 0);
  if (jp !== (R.judgement_pts || 0)) warns.push("judgement_pts (" + R.judgement_pts + ") no coincide con los criterios de juicio de valor (" + jp + ")");
  for (const x of [...(R.requirements || []), ...(R.criteria || [])]) if (!x.cite) warns.push("sin cita: " + (x.label || x.name || x.id));
  for (const c of (R.criteria || []).filter(c => c.kind === "role_excess")) if (!(R.roles || []).some(r => r.id === c.role)) errs.push("el criterio " + c.id + " usa un técnico que no está en roles");
  const fp = path.join(dir, id, "ficha.json");
  if (fs.existsSync(fp)) { const f = JSON.parse(fs.readFileSync(fp, "utf8")); if (f.deadline && f.deadline !== R.deadline) errs.push("el cierre no coincide con la ficha (" + f.deadline + ")"); }
  if ((R.known_issues || []).length) warns.push((R.known_issues || []).length + " contradicción(es) entre documentos: revisar");
  try { // the calculator must run with a neutral answer set
    const a = { lots: [R.lots[0].n], roles: {}, choices: {}, judgement: {}, rebaja: 10, prep_hours: 30 };
    for (const q of R.requirements) a[q.id] = q.kind === "yesno" ? true : q.kind === "number_min" ? q.min : R.lots[0].budget * 2;
    for (const r of R.roles || []) a.roles[r.id] = R.lots[0].works ? R.lots[0].works * 2 : R.lots[0].budget * 2;
    for (const c of (R.criteria || []).filter(c => c.kind === "choice")) a.choices[c.id] = 0;
    const r = D.analyze(R, a, null, R.reviewed || new Date().toISOString().slice(0, 10));
    if (!(r.prob.central >= 0 && r.prob.central <= 1)) errs.push("la calculadora no da una probabilidad válida");
  } catch (e) { errs.push("la calculadora falla: " + e.message); }
  console.log(id + ": " + (errs.length ? "ERROR " + errs.join("; ") : "OK") + (warns.length ? " · revisar: " + warns.join("; ") : ""));
  if (errs.length) bad++;
}
process.exit(bad ? 1 : 0);
