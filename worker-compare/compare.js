// POST {model, messages, max_tokens} with header x-key -> {result: <Workers AI output>}. Deployed only during a comparison run.
export default {
  async fetch(req, env) {
    if (req.method !== "POST" || !env.KEY || req.headers.get("x-key") !== env.KEY) return new Response("forbidden", { status: 403 });
    const b = await req.json();
    try {
      const r = await env.AI.run(b.model, { messages: b.messages, max_tokens: b.max_tokens || 16000, temperature: 0.1 });
      return Response.json({ result: r });
    } catch (e) {
      return Response.json({ error: String(e && e.message || e) }, { status: 502 });
    }
  },
};
