// POST {model, messages, max_tokens} with header x-key -> the Workers AI answer streamed as server-sent events
// (streaming avoids the 3046 timeout on long documents). Deployed only during a comparison run.
export default {
  async fetch(req, env) {
    if (req.method !== "POST" || !env.KEY || req.headers.get("x-key") !== env.KEY) return new Response("forbidden", { status: 403 });
    const b = await req.json();
    try {
      const s = await env.AI.run(b.model, { messages: b.messages, max_tokens: b.max_tokens || 16000, temperature: 0.1, stream: true });
      return new Response(s, { headers: { "content-type": "text/event-stream" } });
    } catch (e) {
      return Response.json({ error: String(e && e.message || e) }, { status: 502 });
    }
  },
};
