/**
 * Ullswater AI — Cloudflare Worker (Workers AI binding "AI").
 *   POST /review  {call, idea, org, trl}  -> preliminary assessment of a project idea against an EU call
 *   POST /ask     {q}                     -> "Ask EU Funding" assistant grounded on calls, Spain and events data
 * Data comes from the public JSON files of calls.ullswaterinvestments.com.
 */
const SITE = "https://calls.ullswaterinvestments.com";
const EVENTS = "https://events.ullswaterinvestments.com/events.json";
const MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast";
const ORIGINS = ["https://calls.ullswaterinvestments.com", "https://www.ullswaterinvestments.com", "https://ullswaterinvestments.com"];
const HITS = new Map(); // best-effort per-isolate rate limit

function cors(req) {
  const o = req.headers.get("Origin") || "";
  return {
    "Access-Control-Allow-Origin": ORIGINS.includes(o) ? o : ORIGINS[0],
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin",
  };
}
function json(data, req, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json; charset=utf-8", ...cors(req) } });
}
async function getJSON(url, ttl = 3600) {
  const r = await fetch(url, { cf: { cacheTtl: ttl, cacheEverything: true } });
  if (!r.ok) throw new Error("fetch " + url + " " + r.status);
  return r.json();
}
function slug(s) { return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); }
function norm(s) { return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, ""); }
function limited(req, max) {
  const ip = req.headers.get("CF-Connecting-IP") || "x", now = Date.now(), h = (HITS.get(ip) || []).filter(t => now - t < 3600e3);
  h.push(now); HITS.set(ip, h);
  return h.length > max;
}
async function llm(env, system, user, maxTokens) {
  const r = await env.AI.run(MODEL, { messages: [{ role: "system", content: system }, { role: "user", content: user }], max_tokens: maxTokens, temperature: 0.2 });
  return (r && (r.response || r.result || "")).toString();
}
function parseJSON(text) {
  const m = text.match(/\{[\s\S]*\}/);
  try { return m ? JSON.parse(m[0]) : null; } catch (e) { return null; }
}

async function review(req, env) {
  const b = await req.json().catch(() => ({}));
  const idea = String(b.idea || "").slice(0, 4000).trim(), callId = String(b.call || "").trim();
  if (idea.split(/\s+/).length < 25) return json({ error: "Please describe your idea in at least 25 words." }, req, 400);
  let t;
  try { t = await getJSON(`${SITE}/data/t/${slug(callId)}.json`); } catch (e) { return json({ error: "Unknown call ID. Choose a call from calls.ullswaterinvestments.com." }, req, 404); }
  const system = "You are a senior EU funding evaluator for Horizon Europe and other EU programmes, working for Ullswater Investments. " +
    "Assess a project idea against ONE call topic, strictly based on the topic text provided. Be honest, specific and constructive; do not invent facts about the call. " +
    "Score each evaluation criterion from 0 to 5 (Horizon Europe scale) for the idea as described, as a preliminary indication only. " +
    "Answer ONLY with a JSON object with keys: fit (one of: strong, partial, weak), fit_reason (2 sentences), " +
    "scores {excellence, impact, implementation} (numbers 0-5), strengths (array of max 4 short strings), gaps (array of max 5 short strings: what is missing versus the expected outcomes and scope), " +
    "consortium (array of max 4 short strings: partner profiles or countries/types needed), trl_note (1 sentence), next_steps (array of max 4 short strings). Write in the same language as the idea.";
  const user = `CALL TOPIC ${t.id} – ${t.title}\nType of action: ${(t.actions || []).join(", ")}\nDeadline: ${t.deadline || "n/a"}\n\nTOPIC TEXT:\n${String(t.text).slice(0, 9000)}\n\n` +
    `APPLICANT: organisation type ${String(b.org || "n/a").slice(0, 40)}, maturity ${String(b.trl || "n/a").slice(0, 40)}\n\nPROJECT IDEA:\n${idea}`;
  const out = await llm(env, system, user, 900);
  const data = parseJSON(out);
  if (!data) return json({ error: "The assessment could not be generated. Please try again." }, req, 502);
  return json({ call: { id: t.id, title: t.title, url: t.url, deadline: t.deadline }, result: data }, req);
}

async function ask(req, env) {
  const b = await req.json().catch(() => ({}));
  const q = String(b.q || "").slice(0, 600).trim();
  if (q.length < 5) return json({ error: "Please write a question." }, req, 400);
  const [finder, spain, events] = await Promise.all([
    getJSON(`${SITE}/data/finder.json`), getJSON(`${SITE}/data/spain.json`).catch(() => ({ calls: [] })), getJSON(EVENTS).catch(() => ({ events: [] }))]);
  const words = norm(q).match(/[a-z0-9][a-z0-9\-]{2,}/g) || [];
  const score = (text, w) => words.reduce((s, x) => s + (norm(text).includes(x) ? 1 : 0) + (w && w[x] ? w[x] * 3 : 0), 0);
  const calls = finder.map(c => ({ c, s: score(c.t + " " + c.id + " " + Object.keys(c.w).join(" "), c.w) })).filter(x => x.s > 0).sort((a, b) => b.s - a.s).slice(0, 8);
  const es = (spain.calls || []).map(c => ({ c, s: score(c.title + " " + c.body + " " + c.region) })).filter(x => x.s > 1).sort((a, b) => b.s - a.s).slice(0, 4);
  const ev = (events.events || []).map(e => ({ e, s: score(e.title + " " + e.summary + " " + e.programme) })).filter(x => x.s > 0).sort((a, b) => b.s - a.s).slice(0, 3);
  let ctx = "EU CALLS (open or forthcoming):\n" + (calls.map(({ c }) =>
    `- ${c.id} | ${c.t} | ${c.s === "open" ? "open" : "forthcoming"} | deadline ${c.d || "n/a"} | ${SITE}/call/${slug(c.id)}/`).join("\n") || "- none matched");
  if (es.length) ctx += "\n\nSPANISH NATIONAL/REGIONAL CALLS:\n" + es.map(({ c }) => `- ${c.title.slice(0, 160)} | ${c.body} | until ${c.end || "n/a"} | ${c.bdns}`).join("\n");
  if (ev.length) ctx += "\n\nEVENTS:\n" + ev.map(({ e }) => `- ${e.start} | ${e.title} | ${e.url}`).join("\n");
  ctx += `\n\nUSEFUL PAGES: Fund Finder ${SITE}/finder/ · Partner board ${SITE}/partners/ · Tools (budget, consortium) ${SITE}/tools/ · AI pre-check ${SITE}/review/ · Alerts ${SITE}/alerts/ · Spain ${SITE}/spain/ · Expert help https://www.ullswaterinvestments.com/eu-fund-matching`;
  const system = "You are 'Ask EU Funding', the assistant of Ullswater Investments (EU funding advisors, Madrid). " +
    "Answer briefly (max 150 words) in the user's language, using ONLY the context below for any call, date or link. Never invent call IDs, dates, budgets or URLs. " +
    "Mention the 1–4 most relevant items with their links. If the context does not answer the question, say so and point to the Fund Finder or to an expert consultation. " +
    "General explanations of how EU funding works are fine if you are sure. Use plain text, with short bullet lines starting with '- '.\n\nCONTEXT:\n" + ctx;
  const answer = await llm(env, system, q, 500);
  return json({ answer, sources: calls.slice(0, 4).map(({ c }) => ({ id: c.id, title: c.t, url: `${SITE}/call/${slug(c.id)}/` })) }, req);
}

export default {
  async fetch(req, env) {
    if (req.method === "OPTIONS") return new Response(null, { headers: cors(req) });
    const path = new URL(req.url).pathname;
    if (req.method === "GET" && path === "/") return json({ service: "Ullswater AI", endpoints: ["/review", "/ask"] }, req);
    if (req.method !== "POST") return json({ error: "Not found" }, req, 404);
    if (limited(req, path === "/review" ? 10 : 40)) return json({ error: "Too many requests. Please try again later." }, req, 429);
    try {
      if (path === "/review") return await review(req, env);
      if (path === "/ask") return await ask(req, env);
    } catch (e) {
      return json({ error: "Service temporarily unavailable." }, req, 500);
    }
    return json({ error: "Not found" }, req, 404);
  },
};
