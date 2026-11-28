import { WorkerEntrypoint } from "cloudflare:workers";
/**
 * ullswater-fichas — email-verified download of the PDF factsheets ("fichas") of calls.ullswaterinvestments.com
 *
 * Flow
 *   1. POST /request {email, id, lang, privacy, marketing, page, hp}  (from a page of the Ullswater sites)
 *      -> stores a one-time link (hash only) and emails it with Resend.
 *   2. GET  /verify?t=<one-time token>   (link in the email, valid 24 h, single use)
 *      -> marks the email as verified and redirects to the call page with an access token in the URL fragment
 *         (#ficha=<access>&fid=<id>). The page keeps it in localStorage, so later downloads need no new email.
 *   3. GET  /pdf?id=<call id>&a=<access> -> decrypts site/fichas/<slug>.bin (AES-256-GCM) and returns the PDF.
 *   Also: GET /status?a=  (is the access token still valid), GET /unsubscribe?l=&s= (withdraw marketing consent).
 *
 * Bindings / secrets
 *   DB             D1 database (same "ullswater-ai" database; tables ficha_* are created on first use)
 *   FICHAS_KEY     secret, 32 bytes base64 — same value as the GitHub secret used by scripts/fichas.py
 *   RESEND_API_KEY secret, Resend API key (domain ullswaterinvestments.com verified in Resend)
 *   MAIL_FROM      var, default "Ullswater Investments <fichas@ullswaterinvestments.com>"
 *   TURNSTILE_SECRET optional secret: if set, /request also requires a Cloudflare Turnstile token (field "ts")
 *
 * Personal data kept: email, consent timestamps (privacy policy version, optional marketing consent), language,
 * which factsheets were downloaded and when. No IP addresses (rate limiting uses a daily hash). One-time links are
 * purged after 7 days. Deletion on request to eufunding@ullswaterinvestments.com.
 */
const SITE = "https://calls.ullswaterinvestments.com";
const ORIGINS = ["https://calls.ullswaterinvestments.com", "https://www.ullswaterinvestments.com", "https://ullswaterinvestments.com"];
const PRIVACY_URL = "https://www.ullswaterinvestments.com/privacy/";
const PRIVACY_VERSION = "2026-11";
const LINK_HOURS = 24;
const ACCESS_DAYS = 180;
const LIMITS = { ip: { hour: 8, day: 30 }, email: { hour: 3, day: 8 }, pdf: { day: 80 } };

// ---------------------------------------------------------------- helpers
const enc = new TextEncoder();
function cors(req) {
  const o = req.headers.get("Origin") || "";
  return { "Access-Control-Allow-Origin": ORIGINS.includes(o) ? o : ORIGINS[0], "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type", "Vary": "Origin" };
}
function json(data, req, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...cors(req) } });
}
function b64url(bytes) {
  let s = ""; for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function fromB64url(s) {
  s = s.replace(/-/g, "+").replace(/_/g, "/"); while (s.length % 4) s += "=";
  return Uint8Array.from(atob(s), c => c.charCodeAt(0));
}
function fromB64(s) { return Uint8Array.from(atob(s), c => c.charCodeAt(0)); }
async function sha256(s) { return b64url(new Uint8Array(await crypto.subtle.digest("SHA-256", enc.encode(s)))); }
function now() { return Math.floor(Date.now() / 1000); }
function slug(s) { return String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); }
function esc(s) { return String(s || "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]); }
const EMAIL_RE = /^[^\s@<>()[\]\\,;:"]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;

let hmacKey = null;
async function hmac(env) {
  if (!hmacKey) {
    const raw = await crypto.subtle.digest("SHA-256", enc.encode("ullswater-fichas|hmac|" + env.FICHAS_KEY));
    hmacKey = await crypto.subtle.importKey("raw", raw, { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
  }
  return hmacKey;
}
async function sign(env, payload) {
  const body = b64url(enc.encode(JSON.stringify(payload)));
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", await hmac(env), enc.encode(body)));
  return body + "." + b64url(sig);
}
async function unsign(env, token) {
  const [body, sig] = String(token || "").split(".");
  if (!body || !sig) return null;
  const ok = await crypto.subtle.verify("HMAC", await hmac(env), fromB64url(sig), enc.encode(body)).catch(() => false);
  if (!ok) return null;
  try { return JSON.parse(new TextDecoder().decode(fromB64url(body))); } catch { return null; }
}

let schemaReady = false;
async function schema(env) {
  if (schemaReady) return;
  await env.DB.batch([
    env.DB.prepare(`CREATE TABLE IF NOT EXISTS ficha_leads (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, created INTEGER NOT NULL,
      verified INTEGER, privacy_at INTEGER, privacy_ver TEXT, marketing INTEGER NOT NULL DEFAULT 0, marketing_at INTEGER, lang TEXT, last_seen INTEGER)`),
    env.DB.prepare(`CREATE TABLE IF NOT EXISTS ficha_tokens (h TEXT PRIMARY KEY, lead INTEGER NOT NULL, call TEXT NOT NULL, page TEXT,
      created INTEGER NOT NULL, expires INTEGER NOT NULL, used INTEGER)`),
    env.DB.prepare(`CREATE TABLE IF NOT EXISTS ficha_downloads (id INTEGER PRIMARY KEY AUTOINCREMENT, lead INTEGER NOT NULL, call TEXT NOT NULL, ts INTEGER NOT NULL)`),
    env.DB.prepare(`CREATE TABLE IF NOT EXISTS ficha_hits (k TEXT NOT NULL, ts INTEGER NOT NULL)`),
    env.DB.prepare(`CREATE INDEX IF NOT EXISTS ficha_hits_k ON ficha_hits (k, ts)`),
    env.DB.prepare(`CREATE INDEX IF NOT EXISTS ficha_downloads_lead ON ficha_downloads (lead, ts)`),
  ]);
  schemaReady = true;
}
async function overLimit(env, key, lim) {
  const t = now();
  const r = await env.DB.prepare("SELECT SUM(ts > ?1) AS h, COUNT(*) AS d FROM ficha_hits WHERE k = ?2 AND ts > ?3").bind(t - 3600, key, t - 86400).first();
  if ((lim.hour && (r?.h || 0) >= lim.hour) || (r?.d || 0) >= lim.day) return true;
  await env.DB.prepare("INSERT INTO ficha_hits (k, ts) VALUES (?1, ?2)").bind(key, t).run();
  return false;
}
async function ipKey(req) {
  const ip = req.headers.get("CF-Connecting-IP") || "x", day = new Date().toISOString().slice(0, 10);
  return "ip:" + (await sha256("ullswater-fichas|" + ip + "|" + day)).slice(0, 16);
}
async function fichaIndex(env) {
  const r = await fetch((env.FICHAS_BASE || SITE) + "/fichas/index.json", { cf: { cacheTtl: 600, cacheEverything: true } });
  if (!r.ok) throw new Error("index " + r.status);
  return (await r.json()).fichas || {};
}
function safePage(p) {
  try { const u = new URL(p); return ORIGINS.includes(u.origin) ? u.origin + u.pathname + u.search : SITE + "/"; } catch { return SITE + "/"; }
}

// ---------------------------------------------------------------- email
function mailBody(lang, link, title, unsub) {
  const es = lang === "es";
  const t = es
    ? { h: "Confirme su email para descargar la ficha", p: "Ha solicitado la ficha en PDF de:", b: "Confirmar y descargar la ficha", n: `El enlace es válido durante ${LINK_HOURS} horas y solo puede usarse una vez. Después podrá descargar cualquier otra ficha desde este navegador sin repetir la validación.`, i: "Si no ha solicitado esta ficha, ignore este mensaje: no guardaremos su dirección como verificada.", u: "Dejar de recibir novedades" }
    : { h: "Confirm your email to download the factsheet", p: "You requested the PDF factsheet of:", b: "Confirm and download the factsheet", n: `The link is valid for ${LINK_HOURS} hours and can be used once. Afterwards you can download any other factsheet from this browser without confirming again.`, i: "If you did not request this factsheet, ignore this message: your address will not be stored as verified.", u: "Stop receiving news" };
  return `<!doctype html><html><body style="margin:0;background:#f4f5f7;font-family:Arial,Helvetica,sans-serif;color:#1f2937">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:10px;overflow:hidden">
<tr><td style="background:#233567;padding:22px 28px;color:#ffffff;font-size:20px;font-weight:bold">Ullswater Investments<div style="color:#edbc6c;font-size:12px;font-weight:normal;letter-spacing:1px;margin-top:4px">EU FUNDING ADVISORS · MADRID &amp; BRUSSELS</div></td></tr>
<tr><td style="padding:28px"><h1 style="font-size:20px;color:#233567;margin:0 0 14px">${t.h}</h1>
<p style="margin:0 0 6px;font-size:14px">${t.p}</p><p style="margin:0 0 22px;font-size:15px;font-weight:bold">${esc(title)}</p>
<p style="margin:0 0 22px"><a href="${link}" style="display:inline-block;background:#c9a646;color:#ffffff;text-decoration:none;font-weight:bold;padding:13px 22px;border-radius:6px">${t.b}</a></p>
<p style="font-size:12px;color:#6b7280;margin:0 0 8px">${t.n}</p><p style="font-size:12px;color:#6b7280;margin:0">${t.i}</p>
<p style="font-size:11px;color:#9aa3b2;margin:16px 0 0;word-break:break-all">${link}</p></td></tr>
<tr><td style="border-top:3px solid #c9a646;padding:16px 28px;font-size:11px;color:#6b7280">Ullswater Investments S.L. · Calle Ramírez de Arellano 17, 28043 Madrid · Square de Meeûs 37, 1000 Brussels<br>
<a href="https://www.ullswaterinvestments.com" style="color:#233567">ullswaterinvestments.com</a> · <a href="${PRIVACY_URL}" style="color:#233567">${es ? "Privacidad" : "Privacy"}</a>${unsub ? ` · <a href="${unsub}" style="color:#233567">${t.u}</a>` : ""}</td></tr>
</table></td></tr></table></body></html>`;
}
async function sendMail(env, to, subject, html, opts = {}) {
  if (env.MAIL_DRY_RUN === "1") { console.log("DRY RUN mail to", to, html.match(/href="([^"]+verify[^"]+)"/)?.[1]); return; } // local tests only
  const r = await fetch("https://api.resend.com/emails", {
    method: "POST", headers: { "Authorization": "Bearer " + env.RESEND_API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ from: opts.from || env.MAIL_FROM || "Ullswater Investments <fichas@ullswaterinvestments.com>", to: [to], subject, html,
      reply_to: opts.replyTo || "eufunding@ullswaterinvestments.com" }),
  });
  if (!r.ok) throw new Error("Resend " + r.status + " " + (await r.text()).slice(0, 200));
}

// ---------------------------------------------------------------- handlers
async function request(req, env) {
  if (!ORIGINS.includes(req.headers.get("Origin") || "")) return json({ error: "not_allowed" }, req, 403);
  let b; try { b = await req.json(); } catch { return json({ error: "bad_request" }, req, 400); }
  if (b.hp) return json({ ok: true }, req); // honeypot filled: pretend success
  const email = String(b.email || "").trim().toLowerCase();
  const lang = b.lang === "es" ? "es" : "en";
  if (!EMAIL_RE.test(email) || email.length > 200) return json({ error: "email" }, req, 400);
  if (b.privacy !== true) return json({ error: "privacy" }, req, 400);
  if (env.TURNSTILE_SECRET) {
    const fd = new FormData(); fd.append("secret", env.TURNSTILE_SECRET); fd.append("response", String(b.ts || ""));
    const v = await (await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", { method: "POST", body: fd })).json().catch(() => ({}));
    if (!v.success) return json({ error: "captcha" }, req, 400);
  }
  const idx = await fichaIndex(env).catch(() => ({}));
  const f = idx[String(b.id || "")];
  if (!f || f.dl === 0) return json({ error: "unknown_ficha" }, req, 404);
  await schema(env);
  if (await overLimit(env, await ipKey(req), LIMITS.ip)) return json({ error: "rate" }, req, 429);
  if (await overLimit(env, "em:" + (await sha256(email)).slice(0, 16), LIMITS.email)) return json({ error: "rate" }, req, 429);

  const t = now();
  await env.DB.prepare(`INSERT INTO ficha_leads (email, created, privacy_at, privacy_ver, lang, last_seen) VALUES (?1, ?2, ?2, ?3, ?4, ?2)
    ON CONFLICT(email) DO UPDATE SET privacy_at = ?2, privacy_ver = ?3, lang = ?4, last_seen = ?2`).bind(email, t, PRIVACY_VERSION, lang).run();
  if (b.marketing === true) await env.DB.prepare("UPDATE ficha_leads SET marketing = 1, marketing_at = ?2 WHERE email = ?1").bind(email, t).run();
  const lead = await env.DB.prepare("SELECT id, marketing FROM ficha_leads WHERE email = ?1").bind(email).first();

  const raw = b64url(crypto.getRandomValues(new Uint8Array(32)));
  await env.DB.prepare("INSERT INTO ficha_tokens (h, lead, call, page, created, expires) VALUES (?1, ?2, ?3, ?4, ?5, ?6)")
    .bind(await sha256(raw), lead.id, String(b.id), safePage(b.page || SITE), t, t + LINK_HOURS * 3600).run();
  const self = new URL(req.url).origin;
  const link = `${self}/verify?t=${raw}`;
  const unsub = lead.marketing ? `${self}/unsubscribe?l=${lead.id}&s=${encodeURIComponent((await sign(env, { u: lead.id })).split(".")[1])}` : "";
  const title = String(b.title || b.id).slice(0, 220);
  try {
    await sendMail(env, email, lang === "es" ? "Confirme su email para descargar la ficha" : "Confirm your email to download the factsheet",
      mailBody(lang, link, title, unsub));
  } catch (e) {
    console.log("mail error", e.message);
    return json({ error: "mail" }, req, 502);
  }
  return json({ ok: true }, req);
}

function page(title, msg, lang = "es") {
  return new Response(`<!doctype html><html lang="${lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(title)}</title>
<style>body{font-family:Inter,Arial,sans-serif;background:#f4f5f7;color:#1f2937;display:grid;place-items:center;min-height:100vh;margin:0}div{background:#fff;max-width:480px;padding:32px;border-radius:12px;border-top:5px solid #c9a646}h1{color:#233567;font-size:20px}a{color:#233567;font-weight:600}</style></head>
<body><div><h1>${esc(title)}</h1><p>${msg}</p><p><a href="${SITE}/">calls.ullswaterinvestments.com →</a></p></div></body></html>`,
    { status: 200, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
}

async function verify(req, env) {
  const raw = new URL(req.url).searchParams.get("t") || "";
  await schema(env);
  const row = raw && await env.DB.prepare("SELECT * FROM ficha_tokens WHERE h = ?1").bind(await sha256(raw)).first();
  if (!row) return page("Enlace no válido · Invalid link", "Este enlace no es válido. Solicite de nuevo la ficha desde la web.<br><br>This link is not valid. Please request the factsheet again from the website.");
  if (row.used || row.expires < now()) return page("Enlace caducado · Link expired", "Este enlace ya se ha usado o ha caducado. Solicite de nuevo la ficha desde la web.<br><br>This link has already been used or has expired. Please request the factsheet again.");
  const t = now();
  await env.DB.batch([
    env.DB.prepare("UPDATE ficha_tokens SET used = ?2 WHERE h = ?1").bind(row.h, t),
    env.DB.prepare("UPDATE ficha_leads SET verified = COALESCE(verified, ?2), last_seen = ?2 WHERE id = ?1").bind(row.lead, t),
  ]);
  const access = await sign(env, { l: row.lead, x: t + ACCESS_DAYS * 86400 });
  const dest = safePage(row.page || SITE) + `#ficha=${encodeURIComponent(access)}&fid=${encodeURIComponent(row.call)}`;
  return Response.redirect(dest, 303);
}

async function access(env, a) {
  const p = await unsign(env, a);
  if (!p || !p.l || !p.x || p.x < now()) return null;
  await schema(env);
  return env.DB.prepare("SELECT id, email, verified FROM ficha_leads WHERE id = ?1 AND verified IS NOT NULL").bind(p.l).first();
}

async function status(req, env) {
  const lead = await access(env, new URL(req.url).searchParams.get("a"));
  if (!lead) return json({ valid: false }, req);
  const [u, d] = lead.email.split("@");
  return json({ valid: true, email: u.slice(0, 2) + "•••@" + d }, req);
}

async function pdf(req, env) {
  const q = new URL(req.url).searchParams, id = q.get("id") || "";
  const lead = await access(env, q.get("a"));
  if (!lead) return page("Validación necesaria · Verification needed", "Para descargar la ficha, introduzca su email en la página de la ayuda y confirme el enlace que le enviaremos.<br><br>To download the factsheet, enter your email on the call page and confirm the link we send you.");
  if (await overLimit(env, "dl:" + lead.id, LIMITS.pdf)) return page("Límite diario · Daily limit", "Ha alcanzado el número máximo de descargas por hoy. Inténtelo mañana.<br><br>You have reached today's download limit.");
  const f = (await fichaIndex(env))[id];
  if (!f || f.dl === 0) return page("Ficha no disponible · Not available", "Esta ficha ya no está disponible (la convocatoria puede haber cerrado).<br><br>This factsheet is no longer available (the call may have closed).");
  const r = await fetch(`${env.FICHAS_BASE || SITE}/fichas/${f.f}.bin`, { cf: { cacheTtl: 3600, cacheEverything: true } });
  if (!r.ok) return page("Error", "No se pudo recuperar la ficha. Inténtelo de nuevo en unos minutos.");
  const data = new Uint8Array(await r.arrayBuffer());
  const key = await crypto.subtle.importKey("raw", fromB64(env.FICHAS_KEY), "AES-GCM", false, ["decrypt"]);
  let plain;
  try { plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: data.slice(0, 12) }, key, data.slice(12)); }
  catch { return page("Error", "No se pudo descifrar la ficha (clave no coincidente)."); }
  const t = now();
  await env.DB.batch([
    env.DB.prepare("INSERT INTO ficha_downloads (lead, call, ts) VALUES (?1, ?2, ?3)").bind(lead.id, id, t),
    env.DB.prepare("UPDATE ficha_leads SET last_seen = ?2 WHERE id = ?1").bind(lead.id, t),
  ]);
  const name = (f.k === "es" ? "Ficha_Ullswater_" : "Factsheet_Ullswater_") + slug(id).slice(0, 80) + ".pdf";
  return new Response(plain, { headers: { "Content-Type": "application/pdf", "Content-Disposition": `attachment; filename="${name}"`, "Cache-Control": "private, no-store" } });
}

async function unsubscribe(req, env) {
  const q = new URL(req.url).searchParams, l = Number(q.get("l"));
  const tok = await sign(env, { u: l });
  if (!l || tok.split(".")[1] !== q.get("s")) return page("Enlace no válido", "El enlace de baja no es válido. Escríbanos a eufunding@ullswaterinvestments.com.");
  await schema(env);
  await env.DB.prepare("UPDATE ficha_leads SET marketing = 0, marketing_at = ?2 WHERE id = ?1").bind(l, now()).run();
  return page("Baja confirmada · Unsubscribed", "No volverá a recibir novedades de Ullswater Investments. Las fichas que ya ha descargado siguen disponibles.<br><br>You will not receive news from Ullswater Investments any more.");
}

// ---------------------------------------------------------------- free tender diagnosis notices
// Called only by the ullswater-ai Worker through a service binding (RPC entrypoint, not reachable from the internet):
// every diagnosis or booking request from tenders.ullswaterinvestments.com becomes an email to tenders@ (reply-to = the company).
const DIAG_TO = "tenders@ullswaterinvestments.com";
export class DiagMail extends WorkerEntrypoint {
  async send(d) {
    const r = d.result || {}, row = (k, v) => v === undefined || v === null || v === "" ? "" :
      `<tr><td style="padding:4px 14px 4px 0;color:#4b5563;vertical-align:top">${esc(k)}</td><td style="padding:4px 0"><b>${esc(v)}</b></td></tr>`;
    const prob = r.prob != null ? `${r.prob} % (entre ${r.low} y ${r.high} %, confianza ${r.conf || ""})` : "";
    const kind = d.event === "reserva" ? "Quiere reservar una cita" : "Nuevo diagnóstico gratuito";
    const html = `<div style="font-family:Arial,sans-serif;font-size:14px;color:#0b1f3a"><h2 style="color:#233567;margin:0 0 12px">${kind}</h2><table>`
      + row("Licitación", d.title || d.tender) + row("Expediente", d.ref) + row("Empresa", d.org + (d.cif ? " (" + d.cif + ")" : "")) + row("Persona", d.name)
      + row("Email", d.email) + row("Veredicto", r.verdict) + row("Puntuación de decisión", r.score != null ? r.score + " / 100" : "") + row("Probabilidad por lote", prob)
      + row("Lotes", (r.lots || []).join(", ")) + row("Rebaja prevista / recomendada", r.mine != null ? r.mine + " % / " + (r.rec || []).join(" y ") + " %" : "")
      + row("Brechas", (r.gaps || []).join(" · ")) + row("Acepta comunicaciones", d.marketing ? "sí" : "no") + row("Guardar perfil", d.save_profile ? "sí" : "no") + row("Página", d.page)
      + `</table><p style="font-size:12px;color:#4b5563;margin-top:16px">Responde a este email para contestar directamente a la empresa. Si otra empresa ya contrató el servicio de pago para esta licitación, solo podemos ofrecerle el diagnóstico gratuito.</p></div>`;
    const subject = `${kind}: ${d.org || ""} · ${d.ref || d.tender}${r.verdict ? " · " + r.verdict : ""}`.slice(0, 200);
    await sendMail(this.env, DIAG_TO, subject, html, { from: "Ullswater Licitaciones <diagnostico@ullswaterinvestments.com>", replyTo: EMAIL_RE.test(d.email || "") ? d.email : undefined });
    return true;
  }
}

export default {
  async scheduled(event, env) {
    await schema(env);
    const t = now();
    await env.DB.batch([
      env.DB.prepare("DELETE FROM ficha_tokens WHERE created < ?1").bind(t - 7 * 86400),
      env.DB.prepare("DELETE FROM ficha_hits WHERE ts < ?1").bind(t - 2 * 86400),
    ]);
  },
  async fetch(req, env) {
    const url = new URL(req.url);
    if (req.method === "OPTIONS") return new Response(null, { headers: cors(req) });
    if (url.pathname === "/") return json({ service: "ullswater-fichas", ok: true, configured: !!(env.FICHAS_KEY && env.RESEND_API_KEY) }, req);
    if (!env.FICHAS_KEY) return json({ error: "not_configured" }, req, 503);
    try {
      if (url.pathname === "/request" && req.method === "POST") return await request(req, env);
      if (url.pathname === "/verify") return await verify(req, env);
      if (url.pathname === "/pdf") return await pdf(req, env);
      if (url.pathname === "/status") return await status(req, env);
      if (url.pathname === "/unsubscribe") return await unsubscribe(req, env);
    } catch (e) {
      console.log("error", url.pathname, e.message);
      return json({ error: "server" }, req, 500);
    }
    return json({ error: "not_found" }, req, 404);
  },
};
