/* Ullswater · free tender diagnosis: the calculator.
 * Pure functions, no DOM. The same answers always give the same result (seeded simulation).
 * Inputs:
 *   rules    tenders/fichas/<id>/reglas.json (see tenders/diagnostico/REGLAS.md)
 *   answers  what the company told us (see UI): lots, turnover, similar, team, roles, energy, insurance, choices,
 *            judgement, rebaja (%), rate (€/h), prep_hours, first_time
 *   comp     competition model for this tender (built from PLACSP awards, or the illustrative default)
 *   today    "YYYY-MM-DD"
 */
(function (root) {
  "use strict";

  // ---------- small helpers ----------
  function mulberry32(a) { return function () { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  function hashStr(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
  function gauss(rng) { let u = 0, v = 0; while (u === 0) u = rng(); while (v === 0) v = rng(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const num = v => (v === null || v === undefined || v === "" || isNaN(+v)) ? null : +v;
  function addDays(iso, d) { const t = new Date(iso + "T12:00:00Z"); t.setUTCDate(t.getUTCDate() + d); return t.toISOString().slice(0, 10); }
  function daysBetween(a, b) { return Math.round((Date.parse(b + "T12:00:00Z") - Date.parse(a + "T12:00:00Z")) / 864e5); }

  const DEFAULT_COMP = { level: "ilustrativo", samples: 0, n_offers: [3, 4, 5, 5, 6, 6, 7, 8, 9], mu: 0.12, sd: 0.06,
    source: "Datos ilustrativos: aún no tenemos adjudicaciones comparables de este organismo y tipo de contrato." };
  const JUDGEMENT = { bajo: 0.4, medio: 0.65, alto: 0.85 };

  // ---------- requirements ----------
  function lotOf(rules, n) { return rules.lots.find(l => l.n === n); }

  function reqStatus(value, threshold) {
    if (value === null) return { state: "amber", margin: null, note: "Sin dato: lo damos por dudoso" };
    if (threshold <= 0) return { state: "green", margin: null };
    const m = value / threshold - 1;
    return { state: m >= 0.2 ? "green" : m >= 0 ? "amber" : "red", margin: m };
  }

  function requirements(rules, a, lots) {
    const out = [];
    for (const r of rules.requirements) {
      if (r.kind === "number_vs_lot") {
        const v = num(a[r.id]);
        const per = lots.map(n => { const th = lotOf(rules, n)[r.basis] * r.factor; return Object.assign({ lot: n, threshold: th }, reqStatus(v, th)); });
        out.push({ id: r.id, label: r.label, rule: r.rule, cite: r.cite, proof: r.proof, value: v, unit: r.unit, per, state: worst(per.map(p => p.state)) });
      } else if (r.kind === "roles_vs_lot") {
        const per = [];
        for (const n of lots) for (const role of rules.roles) {
          const v = num((a.roles || {})[role.id]); const th = lotOf(rules, n)[r.basis] * r.factor;
          per.push(Object.assign({ lot: n, role: role.id, roleLabel: role.label, threshold: th, value: v }, reqStatus(v, th)));
        }
        out.push({ id: r.id, label: r.label, rule: r.rule, cite: r.cite, proof: r.proof, per, state: worst(per.map(p => p.state)) });
      } else if (r.kind === "number_min") {
        const v = num(a[r.id]); const s = reqStatus(v, r.min);
        out.push({ id: r.id, label: r.label, rule: r.rule, cite: r.cite, proof: r.proof, value: v, unit: r.unit, state: s.state, margin: s.margin });
      } else { // yesno
        const v = a[r.id];
        out.push({ id: r.id, label: r.label, rule: r.rule, cite: r.cite, proof: r.proof, value: v, state: v === true ? "green" : v === false ? "red" : "amber" });
      }
    }
    return out;
  }
  function worst(states) { return states.includes("red") ? "red" : states.includes("amber") ? "amber" : "green"; }

  // ---------- points ----------
  function stepPts(steps, excess) { let p = 0; for (const [s, pts] of steps) if (excess >= s - 1e-9) p = pts; return p; }

  function ourTech(rules, a, lotN) {
    const lot = lotOf(rules, lotN); const rows = []; let total = 0;
    for (const c of rules.criteria) {
      if (c.kind === "price") continue;
      let pts = 0, detail = "";
      if (c.kind === "role_excess") {
        const v = num((a.roles || {})[c.role]); const base = lot[c.basis];
        if (v !== null && base) { const ex = v / base - 1; pts = stepPts(c.steps, ex); detail = (ex * 100).toFixed(1).replace(".", ",") + " % sobre el mínimo"; }
        else detail = "Sin dato";
      } else if (c.kind === "choice") {
        const i = num((a.choices || {})[c.id]); const o = i !== null ? c.options[i] : null; pts = o ? o.pts : 0; detail = o ? o.label : "Sin dato";
      } else if (c.kind === "judgement") {
        const lvl = (a.judgement || {})[c.id] || "medio"; pts = Math.round(c.pts * JUDGEMENT[lvl] * 10) / 10; detail = "Autoevaluación: " + lvl;
      }
      rows.push({ id: c.id, name: c.name, max: c.pts, pts, detail, cite: c.cite, kind: c.kind }); total += pts;
    }
    return { rows, total };
  }

  // price points of offer `b` (rebaja as a fraction) among valid rebates `all` (ours included)
  function pricePts(c, b, all) {
    const P = c.pts;
    if (c.formula === "mean_k") {
      let K;
      if (all.length === 1) K = (c.single_k_pct || 20) / 100;
      else { const mean = all.reduce((s, x) => s + x, 0) / all.length; K = 1 - (1 - mean) * (1 - c.k_pct / 100); }
      const lowest = Math.max.apply(null, all); if (lowest > K) K = lowest;
      return K <= 0 ? 0 : Math.min(P, b / K * P);
    }
    if (c.formula === "proportional_lowest") { const best = Math.max.apply(null, all); return (1 - best) / (1 - b) * P; }
    if (c.formula === "linear_max") { const best = Math.max.apply(null, all); return best <= 0 ? 0 : b / best * P; }
    return b * P; // unknown formula: crude linear estimate (flagged as qualitative in the report)
  }

  function competitorTech(rules, rng) {
    let t = 0;
    for (const c of rules.criteria) {
      if (c.kind === "price") continue;
      if (c.kind === "role_excess") { const opts = [0].concat(c.steps.map(s => s[1])); t += opts[Math.floor(rng() * opts.length)]; }
      else if (c.kind === "choice") { const mx = Math.max.apply(null, c.options.map(o => o.pts)); t += rng() < 0.85 ? mx : c.options[Math.floor(rng() * c.options.length)].pts; }
      else if (c.kind === "judgement") t += c.pts * (0.4 + rng() * 0.45);
    }
    return t;
  }

  // probability that we win one lot with rebate b, technical points tech
  function simulate(rules, comp, tech, b, seed, N) {
    const price = rules.criteria.find(c => c.kind === "price"); const ab = rules.abnormal || {};
    const rng = mulberry32(seed); let wins = 0;
    for (let i = 0; i < N; i++) {
      const n = comp.n_offers[Math.floor(rng() * comp.n_offers.length)]; const k = Math.max(1, n - 1);
      const offers = [{ b, t: tech, us: true }];
      for (let j = 0; j < k; j++) offers.push({ b: clamp(comp.mu + comp.sd * gauss(rng), 0, 0.5), t: competitorTech(rules, rng) });
      const mean = offers.reduce((s, o) => s + o.b, 0) / offers.length;
      const line = offers.length > 1 ? mean + (ab.pp || 15) / 100 : (ab.single_pct || 20) / 100;
      const valid = offers.filter(o => !(o.b > line && rng() > (ab.accept_rate == null ? 0.5 : ab.accept_rate)));
      if (!valid.some(o => o.us)) continue;
      const all = valid.map(o => o.b); let best = -1, ours = 0, ties = 0;
      for (const o of valid) { const s = o.t + (price ? pricePts(price, o.b, all) : 0); if (o.us) ours = s; if (s > best) best = s; }
      for (const o of valid) { const s = o.t + (price ? pricePts(price, o.b, all) : 0); if (!o.us && Math.abs(s - ours) < 1e-9) ties++; }
      if (ours >= best - 1e-9) wins += 1 / (1 + ties);
    }
    return wins / N;
  }

  // price points in the three simple scenarios (competition's mean rebate 5/10/15 %) — readable table
  function priceScenarios(rules, b) {
    const c = rules.criteria.find(x => x.kind === "price"); if (!c) return null;
    const ab = rules.abnormal || {};
    return [0.05, 0.10, 0.15].map(m => {
      // mean of all offers ≈ the others' mean (we are one offer among several)
      const pts = pricePts(c, b, [b, m, m, m, m, m]);
      const line = m + (ab.pp || 15) / 100, gap = (line - b) * 100;
      return { mean: m, pts, line, state: gap < 0 ? "red" : gap <= 3 ? "amber" : "green" };
    });
  }

  function confidence(comp) {
    const s = comp.samples || 0;
    if (comp.level !== "ilustrativo" && s >= 30) return { level: "alta", half: 5 };
    if (comp.level !== "ilustrativo" && s >= 10) return { level: "media", half: 10 };
    return { level: "orientativa", half: 15 };
  }

  function round5(p) { return Math.round(p * 20) / 20; }
  function inWords(p) {
    if (p >= 0.9) return "casi siempre"; if (p >= 0.7) return "aproximadamente 3 de cada 4"; if (p >= 0.6) return "aproximadamente 2 de cada 3";
    if (p >= 0.45) return "aproximadamente 1 de cada 2"; if (p >= 0.3) return "aproximadamente 1 de cada 3"; if (p >= 0.2) return "aproximadamente 1 de cada 4";
    if (p >= 0.12) return "aproximadamente 1 de cada 7"; if (p >= 0.07) return "aproximadamente 1 de cada 10"; if (p >= 0.03) return "menos de 1 de cada 15"; return "casi nunca";
  }

  function effort(rules, a, lotN) {
    const e = rules.effort || {}; const lot = lotOf(rules, lotN);
    if (e.kind !== "presence") return null;
    const hc = rules.criteria.find(c => c.kind === "choice" && c.options.some(o => o.hours_week));
    const i = hc ? num((a.choices || {})[hc.id]) : null; const hw = (hc && i !== null && hc.options[i].hours_week) || e.default_hours_week;
    return { hours: (lot.buildings || 1) * e.weeks_per_building * hw, hours_week: hw, base_hours: (lot.buildings || 1) * e.weeks_per_building * e.default_hours_week };
  }

  // ---------- the whole diagnosis ----------
  function analyze(rules, a, comp, today) {
    comp = comp && comp.n_offers && comp.n_offers.length ? comp : DEFAULT_COMP;
    const lots = (a.lots && a.lots.length ? a.lots : [rules.lots[0].n]).slice(0, rules.max_lots_per_team || 99);
    const seed = hashStr(JSON.stringify([rules.id, a, comp.mu, comp.sd, comp.n_offers]));
    const N = 4000, conf = confidence(comp), ab = rules.abnormal || {};
    const reqs = requirements(rules, a, lots);
    const blocked = reqs.some(r => r.state === "red");
    const rate = num(a.rate), myB = clamp((num(a.rebaja) || 0) / 100, 0, 0.6);
    const line = comp.mu + (ab.pp || 15) / 100; // abnormal line with the typical competition
    const maxSafe = Math.max(0, line - 0.03);

    const perLot = lots.map(n => {
      const lot = lotOf(rules, n), tech = ourTech(rules, a, n), eff = effort(rules, a, n);
      const cost = eff && rate ? eff.hours * rate : null;
      const grid = [];
      for (let p = 0; p <= 30; p++) {
        const b = p / 100, prob = simulate(rules, comp, tech.total, b, seed + n * 1000 + p, N);
        const margin = cost !== null ? lot.budget * (1 - b) - cost : null;
        grid.push({ b, prob, margin, ev: margin !== null ? prob * margin : null });
      }
      const atMine = grid[Math.round(myB * 100)] || { b: myB, prob: simulate(rules, comp, tech.total, myB, seed + n * 1000 + 99, N), margin: cost !== null ? lot.budget * (1 - myB) - cost : null };
      const safe = grid.filter(g => g.b <= maxSafe + 1e-9);
      let rec;
      if (cost !== null) rec = safe.reduce((x, g) => (g.ev > (x ? x.ev : -Infinity) ? g : x), null);
      else { const mx = Math.max.apply(null, safe.map(g => g.prob)); rec = safe.find(g => g.prob >= 0.9 * mx); }
      rec = rec || grid[0];
      return { n, lot, tech, effort: eff, cost, grid, mine: atMine, rec, scenarios: priceScenarios(rules, myB), scenariosRec: priceScenarios(rules, rec.b) };
    });

    const pRec = perLot.map(l => l.rec.prob), pMine = perLot.map(l => l.mine.prob);
    const atLeastOne = 1 - pRec.reduce((s, p) => s * (1 - p), 1);
    const central = round5(pRec.reduce((s, p) => s + p, 0) / pRec.length);
    const centralMine = pMine.reduce((s, p) => s + p, 0) / pMine.length;
    const prob = { central, low: Math.max(0, central - conf.half / 100), high: Math.min(1, central + conf.half / 100), words: inWords(central), conf,
      mine: centralMine, mineLow: Math.max(0, round5(centralMine) - conf.half / 100), mineHigh: Math.min(1, round5(centralMine) + conf.half / 100), mineWords: inWords(centralMine), atLeastOne };

    // cost of preparing the offer and expected value
    const prepH = num(a.prep_hours) || 30, extraLotH = 8;
    const offerCost = rate ? (prepH + extraLotH * (lots.length - 1)) * rate : null;
    const evGross = perLot.every(l => l.rec.ev !== null) ? perLot.reduce((s, l) => s + l.rec.ev, 0) : null;

    // decision score 0–100
    const daysLeft = daysBetween(today, rules.deadline);
    const prepDays = Math.ceil((prepH + extraLotH * (lots.length - 1)) / 6);
    const turnover = num(a.turnover), sizeRatio = turnover ? Math.max.apply(null, lots.map(n => lotOf(rules, n).budget)) / turnover : null;
    const sPersp = Math.round(40 * Math.min(central / 0.5, 1));
    let sRent = null;
    if (offerCost && evGross !== null) { const r = evGross / offerCost; sRent = r >= 3 ? 25 : r >= 2 ? 21 : r >= 1.5 ? 18 : r >= 1 ? 12 : r >= 0.5 ? 6 : 0; }
    const sTime = daysLeft >= 2 * prepDays ? 12 : daysLeft >= prepDays ? 8 : 0;
    const sSize = sizeRatio === null ? 5 : sizeRatio <= 0.3 ? 8 : sizeRatio <= 0.5 ? 5 : 2;
    let sRisk = 15; const riskNotes = [];
    const recMax = Math.max.apply(null, perLot.map(l => l.rec.b));
    if (line - recMax <= 0.03 + 1e-9) { sRisk -= 5; riskNotes.push("rebaja recomendada cerca de la línea de baja anormal"); }
    for (const f of rules.risk_flags || []) { sRisk -= f.weight || 0; riskNotes.push(f.label.split(":")[0].toLowerCase()); }
    if (a.first_time) { sRisk -= 3; riskNotes.push("primera licitación"); }
    sRisk = Math.max(0, sRisk);
    const total = blocked ? 0 : sPersp + (sRent === null ? 15 : sRent) + sTime + sSize + sRisk;
    const decision = { blocked, total, verdict: blocked ? "No te presentes así" : total >= 70 ? "Preséntate" : total >= 50 ? "Preséntate si cierras las brechas" : "Mejor no, por ahora",
      state: blocked ? "red" : total >= 70 ? "green" : total >= 50 ? "amber" : "red",
      parts: [
        { name: "Requisitos", pts: blocked ? "No" : "Sí", max: "llave", why: blocked ? "Falta al menos un requisito" : "Todos cumplidos o por confirmar" },
        { name: "Perspectivas de éxito", pts: sPersp, max: 40, why: Math.round(central * 100) + " % por lote con la rebaja recomendada" },
        { name: "Rentabilidad", pts: sRent === null ? 15 : sRent, max: 25, why: offerCost && evGross !== null ? "Valor esperado de " + eur(evGross) + " frente a " + eur(offerCost) + " de preparar la oferta" : "Sin tu coste por hora: puntuación neutra" },
        { name: "Capacidad y plazo", pts: sTime + sSize, max: 20, why: daysLeft + " días hasta el cierre para unos " + prepDays + " días de trabajo" + (sizeRatio !== null ? "; el lote es el " + Math.round(sizeRatio * 100) + " % de tu facturación" : "") },
        { name: "Riesgos", pts: sRisk, max: 15, why: riskNotes.length ? capital(riskNotes.join(", ")) : "Sin riesgos especiales" }
      ] };

    const gaps = buildGaps(rules, a, perLot, reqs, line);
    return { rules, answers: a, comp, conf, lots, perLot, reqs, prob, decision, gaps, line, maxSafe, offerCost, evGross,
      evNet: evGross !== null && offerCost !== null ? evGross - offerCost : null, daysLeft, sizeRatio,
      roadmap: roadmap(rules, a, perLot, today), checks: exclusionChecks(rules), today };
  }

  function capital(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
  function eur(v) { return v === null || v === undefined ? "—" : Math.round(v).toLocaleString("es-ES") + " €"; }

  function buildGaps(rules, a, perLot, reqs, line) {
    const g = [];
    for (const r of reqs) if (r.state === "red") {
      const sp = rules.solvency_paths || {};
      const ways = [sp.integration ? "apoyarte en la solvencia de otra empresa (art. 75 LCSP)" : null, sp.ute ? "presentarte en UTE (art. 69 LCSP)" : null].filter(Boolean);
      g.push({ rank: 1000, kind: "req", title: "Te falta un requisito: " + r.label.toLowerCase(), text: r.rule + "." + (ways.length ? " Puedes " + ways.join(" o ") + "." : ""), cite: r.cite, cta: "Te buscamos socio o solución" });
    }
    // price
    const worstLot = perLot.reduce((x, l) => (l.rec.prob - l.mine.prob > (x ? x.rec.prob - x.mine.prob : -1) ? l : x), null);
    if (worstLot && worstLot.rec.b - worstLot.mine.b >= 0.015) {
      const recs = perLot.map(l => Math.round(l.rec.b * 100));
      const rtxt = Math.min.apply(null, recs) === Math.max.apply(null, recs) ? recs[0] + " %" : Math.min.apply(null, recs) + "–" + Math.max.apply(null, recs) + " %";
      g.push({ rank: 500 + (worstLot.rec.prob - worstLot.mine.prob) * 100, kind: "price", title: "Sube la rebaja al " + rtxt,
        text: "Con tu " + Math.round(worstLot.mine.b * 100) + " % ganarías " + inWords(worstLot.mine.prob) + " veces; con la rebaja recomendada, " + inWords(worstLot.rec.prob) + ". Es la que mejor equilibra la probabilidad de ganar y lo que ganarías, sin acercarte a la línea de baja anormal.",
        cite: (rules.criteria.find(c => c.kind === "price") || {}).cite, cta: "Revisamos tu precio contigo" });
    }
    // experience steps and commitments
    for (const l of perLot) for (const c of rules.criteria) {
      if (c.kind === "role_excess") {
        const v = num((a.roles || {})[c.role]); const base = l.lot[c.basis]; if (v === null || !base) continue;
        const cur = stepPts(c.steps, v / base - 1); const next = c.steps.find(s => s[1] > cur); if (!next) continue;
        const need = base * (1 + next[0]) - v; const gain = next[1] - cur;
        const role = rules.roles.find(r => r.id === c.role);
        if (need <= base * 0.5) g.push({ rank: 100 + gain * 10 - need / base * 10, kind: "exp", lot: l.n, title: "Lote " + l.n + ": +" + gain + " puntos con más experiencia acreditada en " + role.short,
          text: "Te faltan unos " + eur(Math.ceil(need / 1000) * 1000) + " de obra acreditada para pasar de " + cur + " a " + next[1] + " puntos. Si los tienes (o designas a otra persona que los tenga), pide ya los certificados.", cite: c.cite, cta: "Te ayudamos a pedir los certificados" });
      } else if (c.kind === "choice") {
        const i = num((a.choices || {})[c.id]); if (i === null) continue; const mx = Math.max.apply(null, c.options.map(o => o.pts)); const cur = c.options[i].pts;
        if (cur < mx && l === perLot[0]) {
          const best = c.options.find(o => o.pts === mx); let extra = "";
          if (best.hours_week && c.options[i].hours_week && num(a.rate)) {
            const h = perLot.reduce((s, x) => s + (x.lot.buildings || 1) * rules.effort.weeks_per_building * (best.hours_week - c.options[i].hours_week), 0);
            extra = " Cuesta unas " + Math.round(h) + " horas más (" + eur(h * num(a.rate)) + " a tu coste).";
          }
          g.push({ rank: 80 + (mx - cur) * 5, kind: "choice", title: "+" + (mx - cur) + " puntos en «" + c.name.toLowerCase() + "»", text: "Comprometiendo «" + best.label + "»." + extra, cite: c.cite, cta: "Calculamos si te compensa" });
        }
      }
    }
    // the most expensive commitment the company already chose
    const hc = rules.criteria.find(c => c.kind === "choice" && c.options.some(o => o.hours_week));
    if (hc && num(a.rate)) {
      const i = num((a.choices || {})[hc.id]);
      if (i !== null && hc.options[i].hours_week > rules.effort.default_hours_week) {
        const h = perLot.reduce((s, x) => s + (x.lot.buildings || 1) * rules.effort.weeks_per_building * (hc.options[i].hours_week - rules.effort.default_hours_week), 0);
        g.push({ rank: 60, kind: "cost", title: "Revisa tu margen antes de comprometer horas extra",
          text: "«" + hc.name + "» te da " + hc.options[i].pts + " puntos pero supone unas " + Math.round(h) + " horas más en " + (perLot.length > 1 ? "tus lotes" : "el lote") + " (" + eur(h * num(a.rate)) + " a tu coste). " + (rules.effort.note || ""),
          cite: hc.cite, cta: "Calculamos tu margen real" });
      }
    }
    g.sort((x, y) => y.rank - x.rank);
    const seen = new Set(), out = [];
    for (const x of g) { const k = x.kind + (x.kind === "exp" ? x.title.slice(x.title.indexOf(":")) : ""); if (seen.has(k)) continue; seen.add(k); out.push(x); if (out.length === 3) break; }
    return out;
  }

  function roadmap(rules, a, perLot, today) {
    const dl = rules.deadline, items = [];
    const push = (date, task, help, cite, warn) => items.push({ date: date < today ? today : date, task, help: help || "", cite: cite || "", warn: !!warn });
    push(today, "Decide si te presentas y a qué lotes (" + perLot.map(l => l.n).join(" y ") + ")", "Este diagnóstico");
    if (rules.questions_until) {
      if (rules.questions_until < today) {
        const q = (rules.known_issues || [])[0];
        push(today, "Fuera de plazo: el último día para preguntar con respuesta garantizada fue el " + fmtDate(rules.questions_until) + "." + (q ? " Puedes preguntar igualmente («" + q.text + "»), pero no es seguro que respondan a tiempo." : ""), "Borrador de la pregunta", rules.questions_cite, true);
      } else push(rules.questions_until, "Último día para preguntar con respuesta garantizada" + ((rules.known_issues || [])[0] ? ": " + rules.known_issues[0].text : ""), "Borrador de la pregunta", rules.questions_cite);
    }
    if (rules.roles && rules.roles.length) push(addDays(today, 1), "Pide los certificados de las obras dirigidas por cada técnico (importe, fechas y nombramiento)", "Modelo de email para tus antiguos clientes");
    for (const r of rules.requirements) if (r.id === "insurance") push(addDays(dl, -6), "Comprueba las pólizas: " + r.rule.toLowerCase(), "Lista de comprobación", r.cite);
    for (const d of rules.docs_envelopes || []) push(addDays(dl, d.when), d.task, d.help, d.cite);
    push(addDays(dl, -2), "Prueba la firma electrónica y la herramienta de presentación de la " + (rules.platform || "plataforma"), "Guía paso a paso");
    push(dl, "Cierre a las " + (rules.deadline_time || "23:59") + ". Te recomendamos presentar antes de las 14:00", "Aviso el mismo día");
    if (rules.opening_days) push(addDays(dl, rules.opening_days), "Apertura de ofertas y, después, adjudicación (fecha aproximada)", "Aviso y, si no ganas, con qué rebaja y puntuación se ganó y cuántas ofertas hubo", rules.opening_cite);
    items.sort((x, y) => (x.date < y.date ? -1 : x.date > y.date ? 1 : (y.warn - x.warn)));
    return items;
  }

  function exclusionChecks(rules) {
    const g = rules.guarantee || {};
    const base = [
      { text: "No estás en ninguna prohibición de contratar (deudas con Hacienda o la Seguridad Social, sanciones, falsedad en declaraciones)", cite: "Art. 71 LCSP" },
      { text: "El sobre 1 no contiene nada del precio ni de los compromisos que se puntúan con fórmula", cite: "Mezclar sobres excluye la oferta" },
      { text: "Todos los documentos que lo piden van con firma electrónica válida", cite: "Presentación electrónica" },
      { text: "Si te piden justificar una baja anormal, respondes en plazo con el desglose de tus costes", cite: "Art. 149 LCSP" },
      { text: "Tienes preparada la garantía definitiva (" + (g.definitive_pct || 5) + " % del precio" + (g.abnormal_extra_pct ? ", y otro " + g.abnormal_extra_pct + " % si la oferta fue anormal" : "") + ") por si ganas", cite: g.cite || "" },
      { text: "Firmas el compromiso de adscripción de medios con el equipo que de verdad dedicarás", cite: "Art. 76.2 LCSP" }
    ];
    return base.concat(rules.specific_checks || []);
  }

  const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  function fmtDate(iso) { return Number(iso.slice(8, 10)) + " " + MESES[Number(iso.slice(5, 7)) - 1]; }

  function ics(res, url) {
    const esc = s => String(s).replace(/[\\;,]/g, m => "\\" + m).replace(/\n/g, "\\n");
    const stamp = new Date().toISOString().replace(/[-:]/g, "").slice(0, 15) + "Z";
    const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Ullswater Investments//Diagnostico licitacion//ES", "CALSCALE:GREGORIAN"];
    res.roadmap.forEach((it, i) => {
      const d = it.date.replace(/-/g, ""), d2 = addDays(it.date, 1).replace(/-/g, "");
      lines.push("BEGIN:VEVENT", "UID:" + res.rules.id + "-" + i + "-" + d + "@ullswaterinvestments.com", "DTSTAMP:" + stamp, "DTSTART;VALUE=DATE:" + d, "DTEND;VALUE=DATE:" + d2,
        "SUMMARY:" + esc("Licitación " + res.rules.ref + ": " + it.task.slice(0, 120)), "DESCRIPTION:" + esc(it.task + (it.cite ? " (" + it.cite + ")" : "") + "\n" + url),
        "BEGIN:VALARM", "TRIGGER:-PT9H", "ACTION:DISPLAY", "DESCRIPTION:" + esc(it.task.slice(0, 80)), "END:VALARM", "END:VEVENT");
    });
    lines.push("END:VCALENDAR");
    return lines.join("\r\n");
  }

  const api = { analyze, simulate, pricePts, ourTech, requirements, confidence, inWords, ics, fmtDate, eur, addDays, daysBetween, DEFAULT_COMP };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.UDiag = api;
})(this);
