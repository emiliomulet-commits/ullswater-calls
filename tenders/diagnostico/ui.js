/* Ullswater · free tender diagnosis: the step-by-step questions, the result and the full report.
 * Reads window.UDIAG_CFG = {rules, comp, ficha, book, api, privacy} written by tenders/diagnostico/build.py. */
(function () {
  "use strict";
  const C = window.UDIAG_CFG, R = C.rules, D = window.UDiag;
  const root = document.getElementById("udiag");
  if (!root || !C || !D) return;
  const today = new Date().toISOString().slice(0, 10);
  const KEY = "udiag-" + R.id;
  let A = load() || { lots: [], roles: {}, choices: {}, judgement: {}, prep_hours: 30 };
  let step = 0, res = null, profile = null;

  const e = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const eur = D.eur, pct = p => Math.round(p * 100) + " %";
  const cite = c => c ? ' <span class="ud-cite">' + e(c) + "</span>" : "";
  const dot = s => '<span class="ud-dot ud-' + s + '"></span>';
  const STATE = { green: "Cumple", amber: "Por confirmar", red: "No cumple" };
  function save() { try { localStorage.setItem(KEY, JSON.stringify(A)); } catch (x) { /* private mode */ } }
  function load() { try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch (x) { return null; } }
  const numIn = v => { const s = String(v || "").replace(/\./g, "").replace(",", ".").replace(/[^\d.]/g, ""); return s === "" ? null : +s; };
  const fmtN = v => v == null ? "" : Math.round(v).toLocaleString("es-ES");

  // ---------- steps, built from the rule sheet ----------
  const numReqs = R.requirements.filter(r => r.kind === "number_vs_lot" || r.kind === "number_min");
  const ynReqs = R.requirements.filter(r => r.kind === "yesno");
  const choices = R.criteria.filter(c => c.kind === "choice"), judg = R.criteria.filter(c => c.kind === "judgement");
  const STEPS = [
    { id: "company", title: "Tu empresa" },
    R.lots.length > 1 ? { id: "lots", title: "Lotes" } : null,
    numReqs.length ? { id: "figures", title: "Cifras de solvencia" } : null,
    R.roles && R.roles.length ? { id: "team", title: "Tu equipo" } : null,
    ynReqs.filter(r => r.id !== "team").length ? { id: "checks", title: "Otros requisitos" } : null,
    choices.length || judg.length ? { id: "commit", title: "Compromisos" } : null,
    { id: "price", title: "Precio" }
  ].filter(Boolean);

  function render() {
    if (step >= STEPS.length) return renderResult();
    const s = STEPS[step];
    const bar = '<div class="ud-prog"><div style="width:' + Math.round(step / STEPS.length * 100) + '%"></div></div>'
      + '<p class="ud-stepn">Paso ' + (step + 1) + " de " + STEPS.length + " · " + e(s.title) + "</p>";
    root.innerHTML = '<div class="ud-card">' + bar + '<form id="ud-f" novalidate>' + STEP_HTML[s.id]() + '<p class="ud-err" id="ud-err" role="alert"></p><div class="ud-nav">'
      + (step ? '<button type="button" class="ud-btn ghost" id="ud-back">← Atrás</button>' : "<span></span>")
      + '<button type="submit" class="ud-btn">' + (step === STEPS.length - 1 ? "Ver mi diagnóstico" : "Siguiente →") + "</button></div></form></div>";
    const f = document.getElementById("ud-f");
    f.addEventListener("submit", ev => { ev.preventDefault(); const err = STEP_READ[s.id](f); if (err) { document.getElementById("ud-err").textContent = err; return; } save(); step++; render(); root.scrollIntoView({ behavior: "smooth", block: "start" }); });
    const b = document.getElementById("ud-back"); if (b) b.addEventListener("click", () => { STEP_READ[s.id](f, true); step--; render(); });
    if (STEP_INIT[s.id]) STEP_INIT[s.id](f);
  }

  const yn = (name, v) => '<div class="ud-yn">' + [["si", "Sí", true], ["no", "No", false], ["ns", "No lo sé", null]].map(([k, l, val]) =>
    '<label><input type="radio" name="' + name + '" value="' + k + '"' + (v === val && (v !== null || A["_" + name] === "ns") ? " checked" : "") + "> " + l + "</label>").join("") + "</div>";
  const ynRead = (f, name) => { const x = f.querySelector('input[name="' + name + '"]:checked'); A["_" + name] = x ? x.value : ""; return x ? (x.value === "si" ? true : x.value === "no" ? false : null) : undefined; };
  const money = (name, v, ph) => '<div class="ud-money"><input inputmode="numeric" name="' + name + '" value="' + e(fmtN(v)) + '" placeholder="' + e(ph || "0") + '" autocomplete="off"><span>€</span></div>';

  const STEP_HTML = {
    company: () => '<h2>Empecemos por tu empresa</h2><p class="ud-lead">Con tu CIF buscamos los contratos públicos que ya has ganado en los datos abiertos de la ' + e(R.platform) + '. Así te preguntamos menos. Es opcional.</p>'
      + '<label class="ud-l" for="ud-cif">CIF o NIF de la empresa</label><div class="ud-row"><input id="ud-cif" name="cif" maxlength="12" autocomplete="off" placeholder="B12345678" value="' + e(A.cif || "") + '"><button type="button" class="ud-btn ghost" id="ud-look">Buscar</button></div>'
      + '<div id="ud-prof" aria-live="polite">' + profHtml() + "</div>"
      + '<fieldset class="ud-q"><legend>¿Has ganado algún contrato público en los últimos 5 años?</legend>' + yn("won", A.first_time == null ? undefined : !A.first_time) + "</fieldset>"
      + '<p class="ud-note">Información sobre tus datos: consultamos solo fuentes públicas (adjudicaciones de la ' + e(R.platform) + ') y únicamente para este diagnóstico. Puedes corregir lo que encontremos o no dar el CIF. Más detalles en la <a href="' + e(C.privacy) + '" target="_blank" rel="noopener">política de privacidad</a>.</p>',
    lots: () => '<h2>¿A qué lotes quieres presentarte?</h2><p class="ud-lead">' + e(R.lots_rule || "") + " Puedes elegir hasta " + R.max_lots_per_team + " lotes con el mismo equipo." + cite(R.lots_rule_cite) + "</p>"
      + '<div class="ud-lots">' + R.lots.map(l => '<label class="ud-lot"><input type="checkbox" name="lot" value="' + l.n + '"' + (A.lots.includes(l.n) ? " checked" : "") + '><b>Lote ' + l.n + "</b><span>" + eur(l.budget) + " sin IVA" + (l.works ? " · " + eur(l.works) + " de obra" : "") + "</span><small>" + e(l.label) + "</small></label>").join("") + "</div>",
    figures: () => '<h2>Cifras de solvencia</h2><p class="ud-lead">Lo que pide el pliego para poder presentarte. Si no lo sabes exacto, pon una cifra aproximada.</p>'
      + numReqs.map(r => '<div class="ud-q"><label class="ud-l" for="ud-' + r.id + '">' + e(r.question) + "</label>" + (r.unit === "€" ? money(r.id, A[r.id]) : '<input id="ud-' + r.id + '" name="' + r.id + '" inputmode="numeric" value="' + e(A[r.id] == null ? "" : A[r.id]) + '">')
        + '<p class="ud-hint">' + e(r.rule) + cite(r.cite) + "</p></div>").join(""),
    team: () => {
      const t = R.requirements.find(r => r.id === "team");
      return '<h2>Tu equipo</h2>' + (t ? '<fieldset class="ud-q"><legend>' + e(t.question) + "</legend>" + yn("team", A.team) + '<p class="ud-hint">' + e(t.rule) + cite(t.cite) + "</p></fieldset>" : "")
        + '<div class="ud-q"><p class="ud-l">' + e(R.roles_question) + '</p><p class="ud-hint">Solo cifras: no necesitamos nombres.</p>'
        + R.roles.map(r => '<label class="ud-sub" for="ud-r-' + r.id + '">' + e(r.label) + "</label>" + money("role_" + r.id, A.roles[r.id])).join("") + "</div>";
    },
    checks: () => '<h2>Otros requisitos</h2>' + ynReqs.filter(r => r.id !== "team").map(r => '<fieldset class="ud-q"><legend>' + e(r.question) + "</legend>" + yn(r.id, A[r.id]) + '<p class="ud-hint">' + e(r.rule) + cite(r.cite) + "</p></fieldset>").join(""),
    commit: () => '<h2>Compromisos que puntúan</h2><p class="ud-lead">Elige lo que de verdad puedes cumplir: si no lo cumples, hay penalidades.</p>'
      + choices.map(c => '<fieldset class="ud-q"><legend>' + e(c.question) + ' <span class="ud-pts">hasta ' + c.pts + " puntos</span></legend>" + c.options.map((o, i) =>
        '<label class="ud-opt"><input type="radio" name="' + c.id + '" value="' + i + '"' + (A.choices[c.id] === i ? " checked" : "") + "> " + e(o.label) + " <b>" + o.pts + " pts</b></label>").join("") + '<p class="ud-hint">' + cite(c.cite) + "</p></fieldset>").join("")
      + judg.map(c => '<fieldset class="ud-q"><legend>' + e(c.name) + ' <span class="ud-pts">hasta ' + c.pts + " puntos, juicio de valor</span></legend><p class=\"ud-hint\">¿Has preparado memorias técnicas parecidas que hayan puntuado bien?</p>"
        + [["bajo", "No, o pocas"], ["medio", "Algunas, con resultados normales"], ["alto", "Sí, varias y bien puntuadas"]].map(([k, l]) => '<label class="ud-opt"><input type="radio" name="j_' + c.id + '" value="' + k + '"' + ((A.judgement[c.id] || "") === k ? " checked" : "") + "> " + l + "</label>").join("") + "</fieldset>").join(""),
    price: () => '<h2>Precio</h2><p class="ud-lead">Con esto calculamos tus puntos de precio, tus perspectivas de éxito y la rebaja que más te conviene.</p>'
      + '<div class="ud-q"><label class="ud-l" for="ud-reb">¿Qué rebaja sobre el presupuesto te plantearías?</label><div class="ud-money"><input id="ud-reb" name="rebaja" inputmode="decimal" value="' + e(A.rebaja == null ? "" : A.rebaja) + '" placeholder="10"><span>%</span></div></div>'
      + '<div class="ud-q"><label class="ud-l" for="ud-rate">¿Cuánto te cuesta una hora de trabajo de tu equipo? <span class="ud-pts">opcional</span></label><div class="ud-money"><input id="ud-rate" name="rate" inputmode="decimal" value="' + e(A.rate == null ? "" : A.rate) + '" placeholder="35"><span>€/h</span></div><p class="ud-hint">Sirve para saber si te sale a cuenta y cuál es la rebaja que más te conviene en euros.</p></div>'
      + '<div class="ud-q"><label class="ud-l" for="ud-prep">¿Cuántas horas te lleva preparar una oferta así?</label><div class="ud-money"><input id="ud-prep" name="prep_hours" inputmode="numeric" value="' + e(A.prep_hours == null ? 30 : A.prep_hours) + '"><span>h</span></div><p class="ud-hint">Por defecto, 30 horas el primer lote y 8 más por cada lote adicional.</p></div>'
  };

  const STEP_READ = {
    company: (f, soft) => { A.cif = (f.cif.value || "").toUpperCase().replace(/[^0-9A-Z]/g, ""); const w = ynRead(f, "won"); A.first_time = w === undefined || w === null ? (profile && profile.n ? false : null) : !w; return null; },
    lots: (f, soft) => { A.lots = [...f.querySelectorAll('input[name="lot"]:checked')].map(x => +x.value); if (soft) return null; if (!A.lots.length) return "Elige al menos un lote."; if (A.lots.length > R.max_lots_per_team) return "Con un mismo equipo puedes ir como máximo a " + R.max_lots_per_team + " lotes."; return null; },
    figures: (f, soft) => { for (const r of numReqs) A[r.id] = numIn(f[r.id].value); if (soft) return null; return numReqs.some(r => A[r.id] == null) ? "Pon una cifra en cada pregunta (aproximada vale)." : null; },
    team: (f, soft) => { if (f.querySelector('input[name="team"]')) { const v = ynRead(f, "team"); A.team = v === undefined ? null : v; } for (const r of R.roles) A.roles[r.id] = numIn(f["role_" + r.id].value); return null; },
    checks: (f) => { for (const r of ynReqs.filter(r => r.id !== "team")) { const v = ynRead(f, r.id); A[r.id] = v === undefined ? null : v; } return null; },
    commit: (f, soft) => { for (const c of choices) { const x = f.querySelector('input[name="' + c.id + '"]:checked'); A.choices[c.id] = x ? +x.value : null; }
      for (const c of judg) { const x = f.querySelector('input[name="j_' + c.id + '"]:checked'); A.judgement[c.id] = x ? x.value : "medio"; }
      if (soft) return null; return choices.some(c => A.choices[c.id] == null) ? "Elige una opción en cada compromiso." : null; },
    price: (f, soft) => { A.rebaja = numIn(f.rebaja.value); A.rate = numIn(f.rate.value); A.prep_hours = numIn(f.prep_hours.value) || 30; if (soft) return null;
      if (A.rebaja == null || A.rebaja < 0 || A.rebaja > 60) return "Indica una rebaja entre 0 y 60 %."; return null; }
  };

  const STEP_INIT = {
    company: f => {
      document.getElementById("ud-look").addEventListener("click", () => lookup(f.cif.value));
      f.querySelectorAll(".ud-money input").forEach(moneyFmt);
    },
    figures: f => f.querySelectorAll(".ud-money input").forEach(moneyFmt),
    team: f => f.querySelectorAll(".ud-money input").forEach(moneyFmt)
  };
  function moneyFmt(i) { if (i.closest(".ud-money").querySelector("span").textContent !== "€") return; i.addEventListener("blur", () => { const v = numIn(i.value); i.value = v == null ? "" : fmtN(v); }); }

  // ---------- company profile from PLACSP awards (hashed CIF shards) ----------
  async function sha256(s) { const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)); return [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, "0")).join(""); }
  async function lookup(raw) {
    const cif = String(raw || "").toUpperCase().replace(/[^0-9A-Z]/g, ""); const box = document.getElementById("ud-prof");
    if (!/^[0-9A-Z]{8,10}$/.test(cif)) { box.innerHTML = '<p class="ud-err">Revisa el CIF: deben ser 9 caracteres, por ejemplo B12345678.</p>'; return; }
    A.cif = cif; box.innerHTML = '<p class="ud-note">Buscando…</p>';
    try {
      const h = await sha256("ES" + cif); const r = await fetch("/data/es/adjudicatarios/" + h.slice(0, 2) + ".json", { cache: "force-cache" });
      const meta = await fetch("/data/es/adjudicatarios/meta.json").then(x => x.ok ? x.json() : null).catch(() => null);
      const shard = r.ok ? await r.json() : {}; const p = shard[h.slice(0, 16)];
      profile = p ? Object.assign({ found: true }, p, { meta }) : { found: false, meta };
    } catch (x) { profile = { found: false, error: true }; }
    if (profile.found && A.first_time == null) A.first_time = false;
    box.innerHTML = profHtml(); save();
  }
  function profHtml() {
    if (!profile) return "";
    const span = profile.meta && profile.meta.from ? " (adjudicaciones publicadas desde " + D.fmtDate(profile.meta.from) + " " + profile.meta.from.slice(0, 4) + ")" : "";
    if (profile.error) return '<p class="ud-note">No hemos podido consultar los datos ahora. Sigue sin problema: te preguntamos lo necesario.</p>';
    if (!profile.found) return '<div class="ud-prof"><b>No hemos encontrado contratos ganados con este CIF' + span + ".</b><span>Si has ganado alguno, dínoslo abajo: puede que se publicara en una plataforma autonómica que aún no leemos completa.</span></div>";
    return '<div class="ud-prof ok"><b>Hemos encontrado ' + profile.n + " contrato" + (profile.n === 1 ? "" : "s") + " público" + (profile.n === 1 ? "" : "s") + " ganado" + (profile.n === 1 ? "" : "s") + span + ".</b>"
      + "<span>Importe total " + eur(profile.total) + "; el mayor, " + eur(profile.max) + ". Organismos: " + e((profile.buyers || []).slice(0, 3).join(", ")) + (profile.rebaja != null ? ". Rebaja media con la que ganaste: " + pct(profile.rebaja) : "") + ".</span><span>¿Es correcto? Si no, corrígelo abajo.</span></div>";
  }

  // ---------- result: short version, then the form, then the full report ----------
  function compute() { res = D.analyze(R, A, C.comp, today); return res; }

  function renderResult() {
    compute();
    const d = res.decision, p = res.prob;
    root.innerHTML = '<div class="ud-card ud-res">'
      + '<div class="ud-verdict ud-v-' + d.state + '"><div><p class="ud-k">Tu diagnóstico</p><h2>' + e(d.verdict) + (d.blocked ? "" : " · " + d.total + "/100") + "</h2>"
      + "<p>" + (d.blocked ? "Ahora mismo no cumples algún requisito. Te explicamos cómo resolverlo." : "Con tu " + Math.round(A.rebaja) + " % de rebaja ganarías " + e(p.mineWords) + " veces. Con la rebaja recomendada, " + e(p.words) + " por lote.") + "</p></div>"
      + (d.blocked ? "" : '<div class="ud-pct"><b>' + pct(p.central) + '</b><span>por lote, entre ' + pct(p.low) + " y " + pct(p.high) + "<br>confianza: " + e(p.conf.level) + "</span></div>") + "</div>"
      + '<h3>Requisitos</h3><ul class="ud-reqs">' + res.reqs.map(r => "<li>" + dot(r.state) + "<b>" + e(r.label) + "</b> " + STATE[r.state] + "</li>").join("") + "</ul>"
      + '<div class="ud-gate"><h3>Recibe el informe completo y tu hoja de ruta</h3><p>Gratis: puntuación por lote, perspectivas con cada rebaja, las brechas que más puntos te dan, la lista de lo que excluye una oferta y un calendario con todas las fechas hasta el cierre.</p>'
      + '<form id="ud-gate" novalidate><div class="ud-g2"><label>Nombre<input name="name" autocomplete="name" required maxlength="80" value="' + e(A.name || "") + '"></label><label>Empresa<input name="org" autocomplete="organization" required maxlength="120" value="' + e(A.org || "") + '"></label></div>'
      + '<label>Email<input name="email" type="email" autocomplete="email" required maxlength="120" value="' + e(A.email || "") + '"></label>'
      + '<label class="ud-chk"><input type="checkbox" name="consent"><span>Acepto que Ullswater Investments trate estos datos y mis respuestas para preparar el diagnóstico, la hoja de ruta y sus avisos, y para ofrecerme una reunión. <a href="' + e(C.privacy) + '" target="_blank" rel="noopener">Privacidad</a>.</span></label>'
      + '<label class="ud-chk"><input type="checkbox" name="marketing"><span>Quiero recibir novedades y alertas de licitaciones que encajen con mi empresa (opcional).</span></label>'
      + '<label class="ud-chk"><input type="checkbox" name="save_profile"><span>Guarda el perfil de mi empresa (24 meses) para hacer otros diagnósticos con un clic y recibir cada semana las licitaciones que encajan (opcional).</span></label>'
      + '<p class="ud-err" id="ud-gerr" role="alert"></p><div class="ud-nav"><button type="button" class="ud-btn ghost" id="ud-edit">← Cambiar respuestas</button><button class="ud-btn" type="submit">Ver el informe completo</button></div></form></div></div>';
    document.getElementById("ud-edit").addEventListener("click", () => { step = STEPS.length - 1; render(); });
    document.getElementById("ud-gate").addEventListener("submit", ev => {
      ev.preventDefault(); const f = ev.target, err = document.getElementById("ud-gerr");
      A.name = f.name.value.trim(); A.org = f.org.value.trim(); A.email = f.email.value.trim();
      if (A.name.length < 2 || A.org.length < 2 || !/^[^@\s]+@[^@\s]+\.[a-z]{2,}$/i.test(A.email)) { err.textContent = "Escribe tu nombre, tu empresa y un email válido."; return; }
      if (!f.consent.checked) { err.textContent = "Necesitamos tu permiso para preparar el informe."; return; }
      A.marketing = f.marketing.checked; A.save_profile = f.save_profile.checked; save(); send("diagnostico"); renderReport();
    });
  }

  function send(event) {
    if (!C.api || !res) return;
    const p = res.prob, d = res.decision;
    const body = { event, tender: R.id, ref: R.ref, title: R.title, name: A.name, org: A.org, email: A.email, cif: A.cif || "", consent: true,
      marketing: !!A.marketing, save_profile: !!A.save_profile, lang: "es", page: location.href.slice(0, 300),
      result: { score: d.blocked ? 0 : d.total, verdict: d.verdict, prob: Math.round(p.central * 100), low: Math.round(p.low * 100), high: Math.round(p.high * 100), conf: p.conf.level,
        lots: A.lots, rec: res.perLot.map(l => Math.round(l.rec.b * 100)), mine: A.rebaja, gaps: res.gaps.map(g => g.title) },
      answers: { lots: A.lots, turnover: A.turnover, similar: A.similar, roles: A.roles, choices: A.choices, rebaja: A.rebaja, rate: A.rate, first_time: A.first_time } };
    try { fetch(C.api, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), keepalive: true }).catch(() => null); } catch (x) { /* never block the report */ }
  }
  // a click on any booking link tells the team (once per visit) that this company wants a meeting
  let booked = false;
  root.addEventListener("click", ev => { const a = ev.target.closest && ev.target.closest("a"); if (a && a.href === C.book && A.email && !booked) { booked = true; send("reserva"); } });

  function renderReport() {
    const r = res, d = r.decision, p = r.prob, R2 = R;
    const mineB = Math.round(A.rebaja), recs = r.perLot.map(l => Math.round(l.rec.b * 100));
    const recTxt = Math.min(...recs) === Math.max(...recs) ? recs[0] + " %" : Math.min(...recs) + "–" + Math.max(...recs) + " %";
    const cta = t => '<a class="ud-mini" href="' + e(C.book) + '" target="_blank" rel="noopener">' + e(t) + " →</a>";
    const price = R2.criteria.find(c => c.kind === "price");
    let h = '<div class="ud-report" id="ud-report">'
      + '<div class="ud-tools no-print"><button class="ud-btn" id="ud-print">Descargar PDF</button><button class="ud-btn ghost" id="ud-ics">Añadir las fechas a mi calendario</button><a class="ud-btn ghost" href="' + e(C.book) + '" target="_blank" rel="noopener">Reservar 30 minutos</a></div>'
      + '<header class="ud-cover"><p class="ud-k">Diagnóstico gratuito · ¿puedes ganar esta licitación?</p><h2>' + e(R2.title) + "</h2>"
      + "<p>" + e(R2.buyer) + " · Expediente " + e(R2.ref) + " · cierre " + D.fmtDate(R2.deadline) + " " + R2.deadline.slice(0, 4) + ", " + e(R2.deadline_time) + ' <span class="ud-urg">' + (r.daysLeft > 0 ? "Quedan " + r.daysLeft + " días" : r.daysLeft === 0 ? "Cierra hoy" : "Cerrada") + "</span></p>"
      + "<p>Preparado para <b>" + e(A.org) + "</b> · " + D.fmtDate(today) + " " + today.slice(0, 4) + " · lotes " + r.lots.join(" y ") + "</p>"
      + '<div class="ud-verdict ud-v-' + d.state + '"><div><h3>' + e(d.verdict) + (d.blocked ? "" : " · " + d.total + "/100") + "</h3><p>"
      + (d.blocked ? "Ahora mismo no cumples algún requisito: abajo tienes cómo resolverlo." : "Con tu " + mineB + " % de rebaja ganarías " + e(p.mineWords) + " veces por lote. Con un " + recTxt + ", " + e(p.words) + ".") + "</p></div>"
      + (d.blocked ? "" : '<div class="ud-pct"><b>' + pct(p.central) + "</b><span>por lote, entre " + pct(p.low) + " y " + pct(p.high) + "<br>confianza: " + e(p.conf.level) + "</span></div>") + "</div></header>";

    h += '<h3>Resumen</h3><div class="ud-cards">'
      + card("Decisión", dot(d.state) + (d.blocked ? "No" : d.total + " / 100"), e(d.verdict))
      + card("Perspectivas por lote", dot(p.central >= 0.35 ? "green" : p.central >= 0.15 ? "amber" : "red") + pct(p.central), "Entre " + pct(p.low) + " y " + pct(p.high) + " con la rebaja recomendada. Confianza " + e(p.conf.level) + ".")
      + (r.lots.length > 1 ? card("Ganar al menos un lote", "≈ " + pct(Math.round(p.atLeastOne * 20) / 20), "Presentándote a los lotes " + r.lots.join(" y ") + ".") : "")
      + card("Con tu " + mineB + " %", dot(p.mine >= 0.35 ? "green" : p.mine >= 0.15 ? "amber" : "red") + pct(Math.round(p.mine * 20) / 20), e(cap(p.mineWords)) + " por lote.")
      + card("Rebaja recomendada", recTxt, "Mejor equilibrio entre probabilidad y beneficio, lejos de la línea de baja anormal.")
      + (r.evNet != null ? card("Valor esperado", "≈ " + eur(Math.round(r.evNet / 100) * 100), "Ya descontados " + eur(r.offerCost) + " de preparar la oferta.") : "")
      + "</div>";

    h += '<div class="ud-crit"><b>Riesgo crítico: la línea de baja anormal.</b> Una oferta es anormal si rebaja ' + (R2.abnormal.pp || 15) + " puntos más que la media de todas las ofertas" + cite(R2.abnormal.cite)
      + ". Con la competencia habitual (rebaja media del " + pct(r.comp.mu) + "), la línea está en torno al " + pct(r.line) + ". Si la pasas, tendrás que justificar tu precio (art. 149 LCSP); si no convence, tu oferta queda excluida"
      + (R2.guarantee && R2.guarantee.abnormal_extra_pct ? ", y si se acepta depositas un " + R2.guarantee.abnormal_extra_pct + " % más de garantía" : "") + ". " + e(R2.abnormal.note || "") + "</div>";

    if (r.gaps.length) h += '<h3>Las ' + r.gaps.length + " brechas principales</h3>" + r.gaps.map((g, i) => '<div class="ud-gap"><b>' + (i + 1) + ". " + e(g.title) + ".</b> " + e(g.text) + cite(g.cite) + "<br>" + cta(g.cta) + "</div>").join("");

    if (profile && (profile.found || profile.meta)) {
      h += "<h3>Tu perfil de licitador</h3>" + (profile.found
        ? '<div class="ud-cards">' + card("Madurez como licitador", profile.n > 5 ? "Experta" : "Ocasional", profile.n + " contratos públicos ganados en los datos disponibles.")
          + (r.sizeRatio != null ? card("Tamaño del contrato", dot(r.sizeRatio <= 0.3 ? "green" : r.sizeRatio <= 0.5 ? "amber" : "red") + pct(r.sizeRatio), "El lote frente a tu facturación.") : "")
          + card("Contrato mayor ganado", eur(profile.max), "Organismos: " + e((profile.buyers || []).slice(0, 3).join(", ")) + ".") + "</div>"
          + (profile.rebaja != null ? "<p>Ganaste con una rebaja media del " + pct(profile.rebaja) + (profile.rebaja > A.rebaja / 100 + 0.02 ? ": tu " + mineB + " % está por debajo de tu propia costumbre." : ".") + "</p>" : "")
        : "<p>No hemos encontrado contratos ganados con tu CIF en los datos disponibles. Si es tu primera licitación, revisa con especial cuidado la documentación: los errores de forma son un riesgo frecuente.</p>")
        + '<p class="ud-note">Fuente: adjudicaciones publicadas en la ' + e(R2.platform) + (profile.meta && profile.meta.from ? " desde " + D.fmtDate(profile.meta.from) + " " + profile.meta.from.slice(0, 4) : "") + ". Algunas comunidades publican en su propia plataforma y pueden faltar contratos.</p>";
    }

    h += "<h3>Requisitos, uno por uno</h3><table class=\"ud-t\"><tr><th>Requisito</th><th>Qué pide el pliego</th><th>Qué declaras</th><th>Estado</th></tr>"
      + r.reqs.map(q => "<tr><td>" + e(q.label) + "</td><td>" + e(q.rule) + cite(q.cite) + "</td><td>" + reqVal(q) + "</td><td>" + dot(q.state) + STATE[q.state] + "</td></tr>").join("") + "</table>"
      + '<p class="ud-note">Lo que declaras se acredita después: ' + e(R2.requirements.map(q => q.proof).filter(Boolean).slice(0, 3).join("; ").toLowerCase()) + ".</p>";

    h += "<h3>Puntuación estimada por lote</h3><table class=\"ud-t\"><tr><th>Criterio</th><th class=\"n\">Máx.</th>" + r.perLot.map(l => '<th class="n">Lote ' + l.n + "</th>").join("") + "</tr>"
      + (price ? "<tr><td>" + e(price.name) + " (tu " + mineB + " %, competencia media)</td><td class=\"n\">" + price.pts + "</td>" + r.perLot.map(l => '<td class="n">' + fmt1(l.scenarios[1].pts) + "</td>").join("") + "</tr>" : "")
      + r.perLot[0].tech.rows.map((row, i) => "<tr><td>" + e(row.name) + "</td><td class=\"n\">" + row.max + "</td>" + r.perLot.map(l => '<td class="n">' + fmt1(l.tech.rows[i].pts) + "</td>").join("") + "</tr>").join("")
      + '<tr class="tot"><td>Total</td><td class="n">' + R2.criteria.reduce((s, c) => s + c.pts, 0) + "</td>" + r.perLot.map(l => '<td class="n">' + fmt1(l.tech.total + (price ? l.scenarios[1].pts : 0)) + "</td>").join("") + "</tr></table>"
      + '<p class="ud-note">' + (R2.judgement_pts ? "Incluye " + R2.judgement_pts + " puntos de juicio de valor estimados con tu autoevaluación." : "Juicio de valor: ninguno, todos los puntos son con fórmula.") + "</p>";

    if (price) {
      h += "<h3>Precio: puntos y riesgo según la rebaja</h3><p>" + e(price.how) + "." + cite(price.cite) + " Como no sabemos cuánto rebajarán los demás, usamos tres escenarios.</p>"
        + '<table class="ud-t"><tr><th>Tu rebaja</th>' + r.perLot.map(l => "<th>Oferta lote " + l.n + "</th>").join("") + '<th class="n">Competencia 5 %</th><th class="n">10 %</th><th class="n">15 %</th></tr>'
        + rebRows(r).map(b => { const sc = scen(b); return "<tr" + (recs.includes(Math.round(b * 100)) ? ' class="best"' : "") + "><td>" + Math.round(b * 100) + " %" + (Math.round(b * 100) === mineB ? " (tu idea)" : "") + "</td>"
          + r.perLot.map(l => "<td>" + eur(l.lot.budget * (1 - b)) + "</td>").join("") + sc.map(s => '<td class="n">' + fmt1(s.pts) + " pts " + dot(s.state) + "</td>").join("") + "</tr>"; }).join("") + "</table>"
        + '<p class="ud-note">' + dot("green") + "más de 3 puntos de margen hasta la línea de baja anormal · " + dot("amber") + "entre 0 y 3 · " + dot("red") + "oferta anormal.</p>";
    }

    h += "<h3>Perspectivas de éxito según la rebaja</h3><p>Simulamos el concurso miles de veces con la competencia habitual para este tipo de contrato y aplicamos las fórmulas exactas del pliego. Cifras redondeadas a 5 puntos; horquilla de ±" + p.conf.half + " puntos."
      + (r.perLot[0].cost != null ? " «Ganarías» es el precio menos tu coste de presencia." : "") + "</p>"
      + '<table class="ud-t"><tr><th>Tu rebaja</th>' + r.perLot.map(l => '<th class="n">Lote ' + l.n + ": probabilidad</th>" + (l.cost != null ? '<th class="n">Lote ' + l.n + ": ganarías</th>" : "")).join("") + "</tr>"
      + rebRows(r).map(b => { const k = Math.round(b * 100); return "<tr" + (recs.includes(k) ? ' class="best"' : "") + "><td>" + k + " %" + (k === mineB ? " (tu idea)" : "") + (b > r.line - 0.03 ? ' <span class="ud-warn">(cerca de la línea)</span>' : "") + "</td>"
        + r.perLot.map(l => { const g = l.grid[k] || l.mine; return '<td class="n">' + pct(Math.round(g.prob * 20) / 20) + "</td>" + (l.cost != null ? '<td class="n">' + eur(g.margin) + "</td>" : ""); }).join("") + "</tr>"; }).join("") + "</table>"
      + '<p class="ud-note"><b>Confianza: ' + e(p.conf.level) + ".</b> " + e(r.comp.source || "") + (r.comp.level === "ilustrativo" ? "" : " Comparables: " + r.comp.samples + " adjudicaciones.") + " Cobertura: muchas adjudicaciones antiguas no traen número de ofertas ni rebaja, y algunas comunidades publican en su propia plataforma.</p>";

    if (r.perLot[0].effort && r.perLot[0].cost != null) {
      const l = r.perLot[0];
      h += "<h3>¿Te sale a cuenta?</h3><p>En el lote " + l.n + ", con " + (l.lot.buildings || 1) + " edificio" + ((l.lot.buildings || 1) > 1 ? "s" : "") + " y " + l.effort.hours_week + " horas semanales de presencia por edificio, son unas " + fmtN(l.effort.hours) + " horas. "
        + "Con la rebaja recomendada (" + Math.round(l.rec.b * 100) + " %) cobras " + eur(l.lot.budget * (1 - l.rec.b)) + ": <b>unos " + Math.round(l.lot.budget * (1 - l.rec.b) / l.effort.hours) + " € por hora</b>, frente a tu coste de " + e(A.rate) + " €. " + e(R2.effort.note || "")
        + (R2.risk_flags || []).filter(x => x.id === "milestones").map(x => " " + x.label + cite(x.cite) + ".").join("") + "</p>";
    }

    h += "<h3>Decisión: ¿merece la pena presentarse?</h3><table class=\"ud-t\"><tr><th>Componente</th><th class=\"n\">Puntos</th><th>Por qué</th></tr>"
      + d.parts.map(x => "<tr><td>" + e(x.name) + '</td><td class="n">' + e(x.pts) + (typeof x.max === "number" ? " / " + x.max : "") + "</td><td>" + e(x.why) + "</td></tr>").join("")
      + '<tr class="tot"><td>Total</td><td class="n">' + (d.blocked ? "—" : d.total + " / 100") + "</td><td>" + e(d.verdict) + " (70 o más: preséntate; de 50 a 69: si cierras las brechas)</td></tr></table>"
      + (R2.max_lots_award ? '<p class="ud-note">Estrategia de lotes: puedes ganar como máximo ' + R2.max_lots_award + " y cada equipo solo puede ir a " + R2.max_lots_per_team + "." + cite(R2.lots_rule_cite) + (r.lots.length > 1 ? " Con los lotes " + r.lots.join(" y ") + ", la probabilidad de ganar al menos uno es " + e(D.inWords(p.atLeastOne)) + "." : "") + "</p>" : "");

    h += '<h3 class="pb">Tu hoja de ruta</h3><p>Fechas calculadas hacia atrás desde el cierre. Añádelas a tu calendario con el botón de arriba.</p><table class="ud-t"><tr><th>Fecha</th><th>Tarea</th><th>Lo que te damos hecho</th></tr>'
      + r.roadmap.map(x => "<tr><td>" + D.fmtDate(x.date) + "</td><td>" + (x.warn ? '<span class="ud-warn">' : "") + e(x.task) + (x.warn ? "</span>" : "") + cite(x.cite) + "</td><td>" + e(x.help) + "</td></tr>").join("") + "</table>";

    h += "<h3>Antes de presentar: lo que excluye una oferta</h3><ul class=\"ud-checks\">" + r.checks.map(c => "<li>" + e(c.text) + cite(c.cite) + "</li>").join("") + "</ul>"
      + '<p class="ud-note">Si te faltara solvencia, la ley permite completarla con medios de otra empresa (art. 75 LCSP), presentarte en UTE (art. 69) o subcontratar parte del trabajo dentro de los límites del pliego (art. 215).'
      + (R2.solvency_paths && R2.solvency_paths.integration_note ? " En esta licitación: " + e(R2.solvency_paths.integration_note) + "." + cite(R2.solvency_paths.cite) : "") + "</p>";

    h += '<div class="ud-ctab"><h3>¿Preparamos juntos la oferta?</h3><p>' + (r.daysLeft > 0 ? "Quedan " + r.daysLeft + " días. " : "") + "Un consultor de Ullswater revisa contigo este diagnóstico en 30 minutos, sin coste: los lotes, la rebaja y los compromisos que más te convienen.</p>"
      + '<a class="ud-btn gold" href="' + e(C.book) + '" target="_blank" rel="noopener">Reservar 30 minutos</a></div>';

    h += '<h3>Anexo: tus respuestas y supuestos</h3><table class="ud-t">' + answersRows().map(([q, v]) => "<tr><td>" + e(q) + "</td><td>" + e(v) + "</td></tr>").join("") + "</table>"
      + '<p class="ud-note"><b>Supuestos.</b> Competencia: ' + e(r.comp.source || "") + " Entre " + Math.min(...r.comp.n_offers) + " y " + Math.max(...r.comp.n_offers) + " ofertas por lote, rebaja media del " + pct(r.comp.mu)
      + ". Los competidores suelen comprometer lo máximo en lo que es fácil y tienen experiencia variada; las ofertas anormales se aceptan la mitad de las veces." + (R2.effort && R2.effort.note ? " " + e(R2.effort.note) + "." : "") + "</p>"
      + '<p class="ud-disc"><b>Aviso. Diagnóstico orientativo: no es asesoramiento jurídico ni una garantía de adjudicación.</b> Lo elabora un sistema automático con ayuda de inteligencia artificial a partir de tus respuestas, de datos públicos y de los pliegos publicados (revisados el ' + D.fmtDate(R2.reviewed) + " " + R2.reviewed.slice(0, 4) + "). "
      + "Las probabilidades son estimaciones con el margen indicado y dependen de supuestos sobre otros licitadores, de los que solo usamos datos agregados. Prevalecen siempre los pliegos, sus aclaraciones y el anuncio oficial. "
      + "La decisión de presentarse, el contenido de la oferta y la veracidad de lo declarado (incluido el DEUC, que es una declaración responsable: art. 140 LCSP) corresponden únicamente a tu empresa. "
      + "Ullswater Investments no responde de las decisiones tomadas con este informe ni del resultado de la licitación. Tus datos se conservan 12 meses y puedes pedir su corrección o borrado (<a href=\"" + e(C.privacy) + "\">privacidad</a>). "
      + 'Citas: PCAP = pliego administrativo, PPT = pliego técnico, ANX = anexos al PCAP. <a href="' + e(C.ficha) + '">Volver a la ficha</a>.</p></div>';

    root.innerHTML = h;
    document.getElementById("ud-print").addEventListener("click", () => window.print());
    document.getElementById("ud-ics").addEventListener("click", () => {
      const blob = new Blob([D.ics(r, location.href.split("#")[0])], { type: "text/calendar" }), a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = "licitacion-" + R2.id + ".ics"; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
    });
    root.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function card(lbl, val, txt) { return '<div class="ud-c"><div class="ud-cl">' + e(lbl) + '</div><div class="ud-cv">' + val + "</div><div>" + txt + "</div></div>"; }
  const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
  const fmt1 = v => (Math.round(v * 10) / 10).toLocaleString("es-ES");
  function reqVal(q) {
    if (q.per && q.id === "team_works") return R.roles.map(ro => e(ro.short) + ": " + eur(A.roles[ro.id])).join("<br>");
    if (q.value === true) return "Sí"; if (q.value === false) return "No"; if (q.value == null) return "No lo sé";
    return q.unit === "€" ? eur(q.value) : e(q.value);
  }
  function rebRows(r) { const s = new Set([Math.round(A.rebaja)]); r.perLot.forEach(l => s.add(Math.round(l.rec.b * 100))); [Math.round(A.rebaja) + 4, Math.round(r.line * 100) - 2].forEach(x => { if (x >= 0 && x <= 30) s.add(x); }); return [...s].sort((a, b) => a - b).map(x => x / 100); }
  function scen(b) { return D.analyze ? (function () { const c = R.criteria.find(x => x.kind === "price"); return [0.05, 0.10, 0.15].map(m => { const pts = D.pricePts(c, b, [b, m, m, m, m, m]); const gap = (m + (R.abnormal.pp || 15) / 100 - b) * 100; return { pts, state: gap < 0 ? "red" : gap <= 3 ? "amber" : "green" }; }); })() : []; }
  function answersRows() {
    const out = [["CIF", A.cif ? A.cif + (profile && profile.found ? " (datos públicos confirmados)" : "") : "No indicado"], ["Contratos públicos en 5 años", A.first_time === true ? "Ninguno" : A.first_time === false ? "Sí" : "No lo sé"], ["Lotes", (A.lots || []).join(" y ")]];
    for (const q of numReqs) out.push([q.question, q.unit === "€" ? eur(A[q.id]) : String(A[q.id])]);
    if (R.roles) for (const ro of R.roles) out.push(["Obra dirigida: " + ro.short, eur(A.roles[ro.id])]);
    for (const q of ynReqs) out.push([q.label, A[q.id] === true ? "Sí" : A[q.id] === false ? "No" : "No lo sé"]);
    for (const c of choices) out.push([c.name, A.choices[c.id] != null ? c.options[A.choices[c.id]].label : "—"]);
    out.push(["Rebaja prevista", A.rebaja + " %"], ["Coste por hora", A.rate ? A.rate + " €/h" : "No indicado"], ["Horas para preparar la oferta", A.prep_hours + " h"]);
    return out;
  }

  render();
})();
