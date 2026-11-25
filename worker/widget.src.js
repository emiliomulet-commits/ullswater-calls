/* "Asistente de ayudas" chat widget for the Ullswater network. Served by the Worker at /widget.js.
   Embed: <script src="https://ullswater-ai.emilio-mulet-b52.workers.dev/widget.js" defer data-site="www"></script>
   data-site: www | calls | news | events | project (suggested questions); language from <html lang> or a /es/ path.
   No backtick strings or dollar-brace sequences in this file: it is embedded in the Worker as String.raw. */
(function () {
  if (window.__uaaLoaded) return; window.__uaaLoaded = 1;
  var me = document.currentScript || document.querySelector('script[src*="widget.js"]');
  var API = me ? me.src.replace(/\/widget\.js.*$/, '') : '';
  var site = (me && me.getAttribute('data-site')) || (/calls\./.test(location.host) ? 'calls' : /news\./.test(location.host) ? 'news' : /events\./.test(location.host) ? 'events' : /^www\.|^ullswater/.test(location.host) ? 'www' : 'project');
  var lang = ((document.documentElement.lang || '').slice(0, 2) === 'es' || /^\/es(\/|$)/.test(location.pathname)) ? 'es' : 'en';
  var BOOK = 'https://outlook.office.com/bookwithme/user/e458fce3fc324c73bf552650547cf141@ullswaterinvestments.com/meetingtype/nBIRMB9DAUGZ7TZQg15B-A2?anonymous';
  var T = {
    en: { name: 'Funding Assistant', open: 'Ask about funding', ai: 'You are chatting with an AI assistant.', ph: 'Your question…', send: 'Send', expert: 'Talk to an expert',
      hi: 'Hi! I can help you with EU calls, grants in Spain, our services, news and events. What are you looking for?',
      foot: 'AI answers can be wrong: always check the official source. Questions are stored anonymously for 12 months to improve the service; do not include personal data.',
      privacy: 'Privacy', rel: 'Related topics', fresh: 'New conversation', think: 'Thinking', busy: 'The assistant is busy. Please try again.', cut: 'The answer was interrupted. Please try again.', close: 'Close',
      q: { www: ['Which of your services fits a startup looking for EU funding?', 'How do you help with a Horizon Europe proposal?', 'Which European projects are open to new partners?'],
           calls: ['RIA calls in Cluster 4 on AI closing before April 2027', 'Calls open to SMEs on clean energy', 'EIC calls for deep-tech startups'],
           call: ['Explain this call in plain words', 'Can SMEs apply to this call?', 'Similar calls with a later deadline'],
           news: ['What are the latest EU funding news?', 'News about funding in Spain this month', 'What changes in the next EU budget (2028-2034)?'],
           article: ['Explain this news and what it means for a company', 'Which open calls are related to this?', 'What are the latest EU funding news?'],
           events: ['Which info days are coming up this month?', 'Brokerage events to find consortium partners', 'Is there a webinar on writing a proposal?'],
           event: ['Is this event worth attending for my organisation?', 'Which calls does this event cover?', 'Other events on the same programme'],
           project: ['What is this project about?', 'How can my organisation join the consortium?', 'Which other projects does Ullswater run?'] } },
    es: { name: 'Asistente de ayudas', open: 'Pregunta por ayudas', ai: 'Estás hablando con un asistente de IA.', ph: 'Tu pregunta…', send: 'Enviar', expert: 'Hablar con un experto',
      hi: '¡Hola! Te ayudo con convocatorias europeas, ayudas en España, nuestros servicios, noticias y eventos. ¿Qué estás buscando?',
      foot: 'Las respuestas de la IA pueden contener errores: comprueba siempre la fuente oficial. Las preguntas se guardan de forma anónima 12 meses para mejorar el servicio; no incluyas datos personales.',
      privacy: 'Privacidad', rel: 'Temas relacionados', fresh: 'Nueva conversación', think: 'Pensando', busy: 'El asistente está ocupado. Inténtalo de nuevo.', cut: 'La respuesta se interrumpió. Inténtalo de nuevo.', close: 'Cerrar',
      q: { www: ['Ayudas abiertas para pymes en mi comunidad', '¿Qué servicio vuestro encaja con una startup que busca fondos europeos?', '¿Qué proyectos europeos admiten nuevos socios?'],
           calls: ['Convocatorias RIA del Clúster 4 sobre IA que cierran antes de abril de 2027', 'Convocatorias abiertas a pymes sobre energía limpia', 'Convocatorias del EIC para startups deep-tech'],
           call: ['Explícame esta convocatoria en palabras sencillas', '¿Pueden presentarse pymes a esta convocatoria?', 'Convocatorias parecidas con plazo más tarde'],
           news: ['¿Cuáles son las últimas noticias de financiación europea?', 'Noticias de ayudas en España este mes', '¿Qué cambia en el próximo presupuesto de la UE (2028-2034)?'],
           article: ['Explícame esta noticia y qué supone para una empresa', '¿Qué convocatorias abiertas tienen relación con esto?', '¿Cuáles son las últimas noticias de financiación europea?'],
           events: ['¿Qué jornadas informativas hay este mes?', 'Eventos de brokerage para encontrar socios', '¿Hay algún webinar sobre cómo escribir una propuesta?'],
           event: ['¿Merece la pena este evento para mi organización?', '¿Qué convocatorias cubre este evento?', 'Otros eventos del mismo programa'],
           project: ['¿De qué trata este proyecto?', '¿Cómo puede mi organización unirse al consorcio?', '¿Qué otros proyectos tiene Ullswater?'] } }
  }[lang];
  // page context (grant pages of /es/ayudas/): {"tipo":"ayuda","id","titulo","sugeridas":[...]} in <script type="application/json" id="uaa-ctx">
  var CTX = null; try { var ce = document.getElementById('uaa-ctx'); if (ce) CTX = JSON.parse(ce.textContent); } catch (e) { CTX = null; }
  if (CTX && CTX.tipo === 'ayuda') T.hi = lang === 'es' ? 'Pregúntame lo que quieras sobre esta ayuda: quién puede pedirla, qué gastos cubre, cuánto puedes recibir o cómo se solicita. Respondo con sus documentos oficiales.'
    : 'Ask me anything about this grant: who can apply, eligible costs, amounts or how to apply. I answer from its official documents.';
  var PRIV = 'https://www.ullswaterinvestments.com/' + (lang === 'es' ? 'es/' : '') + 'privacy/';
  var css = '#uaa{position:fixed;right:18px;bottom:18px;z-index:2147483000;font:14px/1.5 Inter,system-ui,-apple-system,Segoe UI,sans-serif;color:#1f2937}' +
    '#uaa *{box-sizing:border-box}#uaa-b{background:#233567;color:#fff;border:0;border-radius:999px;padding:12px 18px;font:inherit;font-weight:700;box-shadow:0 6px 20px rgba(0,0,0,.22);cursor:pointer;display:flex;align-items:center;gap:8px}' +
    '#uaa-b:focus-visible,#uaa button:focus-visible,#uaa a:focus-visible,#uaa input:focus-visible{outline:3px solid #c9a646;outline-offset:2px}' +
    '#uaa-p{display:none;width:min(410px,94vw);height:min(620px,80vh);background:#fff;border:1px solid #e5e7eb;border-radius:14px;box-shadow:0 12px 40px rgba(0,0,0,.25);flex-direction:column;overflow:hidden}' +
    '#uaa-h{background:#233567;color:#fff;padding:12px 14px}#uaa-h strong{font-size:15px}#uaa-h small{display:block;color:#dfe5f3;font-size:12px}#uaa-h .r{float:right;display:flex;gap:6px;align-items:center}' +
    '#uaa-x{background:none;border:0;color:#fff;font-size:22px;line-height:1;cursor:pointer;padding:0 4px}' +
    '#uaa-e{background:#c9a646;color:#233567;border-radius:999px;padding:4px 10px;font-size:12px;font-weight:700;text-decoration:none;white-space:nowrap}' +
    '#uaa-m{flex:1;overflow:auto;padding:12px}#uaa-m .msg{margin-top:8px;border-radius:10px;padding:10px 12px;background:#f5f6f8;overflow-wrap:anywhere}#uaa-m .me{background:#233567;color:#fff;margin-left:34px}' +
    '#uaa-m a{color:#233567}#uaa-m .me a{color:#fff}#uaa-s{display:flex;flex-direction:column;gap:6px;margin-top:10px}#uaa-s button{text-align:left;background:#fff;border:1px solid #d7dbe6;border-radius:10px;padding:8px 10px;font:inherit;font-size:13px;color:#233567;cursor:pointer}' +
    '#uaa-s button:hover{border-color:#233567}.uaa-st{color:#6b7280;font-style:italic;font-size:13px}.uaa-src{margin-top:8px;display:flex;flex-wrap:wrap;gap:4px}.uaa-src a{font-size:11px;background:#fff;border:1px solid #e5e7eb;border-radius:999px;padding:2px 8px;text-decoration:none;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}' +
    '#uaa-f{display:flex;gap:6px;padding:10px;border-top:1px solid #e5e7eb}#uaa-i{flex:1;font:inherit;border:1px solid #d7dbe6;border-radius:8px;padding:9px;min-width:0}#uaa-f button{background:#c9a646;color:#233567;border:0;border-radius:8px;padding:0 14px;font:inherit;font-weight:700;cursor:pointer}' +
    '.uaa-sg{margin-top:10px}.uaa-sg small{display:block;color:#6b7280;font-size:11px;margin-bottom:4px}.uaa-sg button{background:#fff;border:1px solid #c9a646;border-radius:999px;padding:5px 11px;margin:0 6px 6px 0;font:inherit;font-size:12.5px;color:#233567;cursor:pointer;text-align:left}.uaa-sg button:hover{background:#fbf6e6}' +
    '#uaa-n{font-size:11px;color:#6b7280;padding:0 12px 8px}#uaa-n a{color:#6b7280}' +
    '#uaa.wide #uaa-p{width:min(640px,94vw);height:min(780px,86vh)}#uaa.wide #uaa-m{font-size:15px}' +
    '#uaa-p{transition:width .35s ease,height .35s ease}#uaa.big #uaa-p{width:min(533px,96vw);height:min(806px,92vh)}#uaa.big #uaa-m{font-size:15px}' +
    '#uaa.big.wide #uaa-p{width:min(832px,96vw);height:min(1014px,92vh)}#uaa.big.wide #uaa-m{font-size:16px}' +
    '.uaa-cur{display:inline-block;width:.5em;height:1.05em;margin-left:1px;vertical-align:-.15em;background:#233567;animation:uaab 1s steps(1) infinite}@keyframes uaab{50%{opacity:0}}' +
    '@media (prefers-reduced-motion:reduce){#uaa-p{transition:none}.uaa-cur{animation:none}}' +
    '@media (max-width:600px){#uaa{right:10px;bottom:10px}#uaa.o{inset:0}#uaa.o #uaa-p{width:100vw;height:100dvh;border-radius:0}}';
  var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
  var w = document.createElement('div'); w.id = 'uaa';
  w.innerHTML = '<button id="uaa-b" type="button" aria-expanded="false" aria-controls="uaa-p"><span aria-hidden="true">💬</span>' + T.open + '</button>' +
    '<div id="uaa-p" role="dialog" aria-label="' + T.name + '"><div id="uaa-h"><span class="r"><a id="uaa-e" target="_blank" rel="noopener" href="' + BOOK + '">' + T.expert + ' ↗</a>' +
    '<button id="uaa-x" type="button" aria-label="' + T.close + '">×</button></span><strong>' + T.name + ' <span style="color:#c9a646">· IA</span></strong><small>' + T.ai + '</small></div>' +
    '<div id="uaa-m" aria-live="polite"></div><form id="uaa-f"><label for="uaa-i" style="position:absolute;left:-9999px">' + T.ph + '</label><input id="uaa-i" maxlength="1000" autocomplete="off" placeholder="' + T.ph + '"><button type="submit">' + T.send + '</button></form>' +
    '<div id="uaa-n">' + T.foot + ' <a href="' + PRIV + '" target="_blank" rel="noopener">' + T.privacy + '</a></div></div>';
  if (lang === 'en') w.innerHTML = w.innerHTML.replace('· IA', '· AI');
  document.body.appendChild(w);
  var $ = function (id) { return document.getElementById(id); };
  var b = $('uaa-b'), p = $('uaa-p'), m = $('uaa-m'), f = $('uaa-f'), inp = $('uaa-i'), busy = 0, H = [];
  try { H = JSON.parse(sessionStorage.getItem('uaa-h') || '[]'); } catch (e) { H = []; }
  function save() { try { sessionStorage.setItem('uaa-h', JSON.stringify(H.slice(-12))); } catch (e) {} }
  var wide = 0, big = 0, topicQ = '';
  // big: the panel grows 30% once the assistant starts answering (easier reading); back to normal size when closed
  var RM = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function cls() { var open = p.style.display === 'flex'; w.className = (open ? 'o' : '') + (open && wide ? ' wide' : '') + (open && big ? ' big' : ''); }
  function toggle(open) { if (!open) big = 0; p.style.display = open ? 'flex' : 'none'; b.style.display = open ? 'none' : ''; cls(); b.setAttribute('aria-expanded', open ? 'true' : 'false'); if (open) inp.focus(); else b.focus(); }
  b.onclick = function () { toggle(true); }; $('uaa-x').onclick = function () { wide = 0; toggle(false); };
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && p.style.display === 'flex') toggle(false); });
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function ext(u) { return !/^https?:\/\/([a-z0-9-]+\.)*ullswaterinvestments\.com(\/|$)/i.test(u); }
  function link(u, t) { return '<a href="' + u + '"' + (ext(u) ? ' target="_blank" rel="noopener noreferrer"' : '') + '>' + t + (ext(u) ? ' ↗' : '') + '</a>'; }
  function fmt(s) {
    var L = [];
    return esc(s).replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g, function (_, t, u) { L.push(link(u, t)); return '\u0000' + (L.length - 1) + '\u0000'; })
      .replace(/^#{1,6}\s*(.+)$/gm, '<strong>$1</strong>').replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
      .replace(/(https?:\/\/[^\s)<\u0000]+[^\s)<.,;:\u0000])/g, function (u) { L.push(link(u, u)); return '\u0000' + (L.length - 1) + '\u0000'; })
      .replace(/\u0000(\d+)\u0000/g, function (_, n) { return L[n]; }).replace(/^[-*] /gm, '• ').replace(/\n{3,}/g, '\n\n').replace(/\n/g, '<br>');
  }
  function add(h, mine) { var d = document.createElement('div'); d.className = 'msg' + (mine ? ' me' : ''); d.innerHTML = h; m.appendChild(d); m.scrollTop = m.scrollHeight; return d; }
  function src(a) { if (!a || !a.length) return ''; return '<div class="uaa-src">' + a.map(function (x) { return '<a href="' + esc(x.url) + '" title="' + esc(x.title || x.id) + '"' + (ext(x.url) ? ' target="_blank" rel="noopener"' : '') + '>' + esc(x.id || x.title) + '</a>'; }).join('') + '</div>'; }
  // follow-up suggestions under the last answer: buttons that ask the question
  function sugg(box, a) {
    if (!a || !a.length) return;
    var s = document.createElement('div'); s.className = 'uaa-sg'; s.innerHTML = '<small>' + esc(T.rel) + '</small>';
    a.slice(0, 3).forEach(function (q) { var x = document.createElement('button'); x.type = 'button'; x.textContent = q; x.onclick = function () { if (busy) return; inp.value = q; ask(); }; s.appendChild(x); });
    box.appendChild(s);
  }
  function intro() {
    add(esc(T.hi));
    var s = document.createElement('div'); s.id = 'uaa-s';
    var path = location.pathname.replace(/^\/es\//, '/'), kind = site === 'calls' && /^\/call\//.test(path) ? 'call' : site === 'news' && /^\/\d{4}\/\d{2}\/[^/]+/.test(path) ? 'article' : site === 'events' && /^\/events\/[^/]+/.test(path) ? 'event' : site;
    var qs = CTX && CTX.sugeridas && CTX.sugeridas.length ? CTX.sugeridas.slice(0, 4) : (T.q[kind] || T.q[site] || T.q.www);
    qs.forEach(function (q) { var x = document.createElement('button'); x.type = 'button'; x.textContent = q; x.onclick = function () { inp.value = q; s.remove(); ask(); }; s.appendChild(x); });
    m.appendChild(s);
  }
  if (H.length) {
    H.forEach(function (x) { add(x.role === 'user' ? esc(x.content) : fmt(x.content), x.role === 'user'); });
    var c = document.createElement('button'); c.type = 'button'; c.textContent = T.fresh;
    c.style.cssText = 'margin-top:8px;background:none;border:0;color:#6b7280;font-size:12px;text-decoration:underline;cursor:pointer';
    c.onclick = function () { H = []; save(); m.innerHTML = ''; intro(); }; m.appendChild(c);
  } else intro();
  f.onsubmit = function (e) { e.preventDefault(); ask(); };
  // API for buttons on the page (e.g. «Pregunta a la IA sobre esta ayuda»): UAA.ask(question) opens the chat and asks it
  // UAA.ask(question, {wide: 1, topic: 1}): wide = larger panel (home hero); topic = one of the 20 key topics of the home page (answer may come from the Worker cache)
  window.UAA = { open: function () { toggle(true); }, ask: function (q, o) { o = o || {}; if (o.wide) wide = 1; toggle(true); inp.value = String(q || '').slice(0, 1000); topicQ = o.topic ? inp.value.trim() : ''; if (!busy) ask(); } };
  var pending = window.UAA_Q || []; window.UAA_Q = { push: function (x) { if (x && x.push) window.UAA.ask(x[0], x[1]); else window.UAA.ask(x); } };
  if (pending.length) setTimeout(function () { window.UAA_Q.push(pending[pending.length - 1]); }, 0);
  function ask() {
    var q = inp.value.trim(); if (!q || busy) return; busy = 1; inp.value = '';
    var sg = $('uaa-s'); if (sg) sg.remove();
    var old = m.querySelectorAll('.uaa-sg'); for (var i = 0; i < old.length; i++) old[i].remove();
    add(esc(q), 1);
    big = 1; cls();
    var box = add(''), body = document.createElement('div'), stx = document.createElement('div'), txt = '', raf = 0, shown = 0, done = null, last = 0;
    stx.className = 'uaa-st'; stx.textContent = T.think + '…'; box.appendChild(body); box.appendChild(stx);
    // typewriter: the received text (txt) is revealed progressively (shown chars), never cutting a link or bold mid-way
    var TOK = /\[[^\]\n]+\]\(https?:\/\/[^\s)]+\)|\*\*[^*\n]+\*\*|https?:\/\/[^\s)<]+/g;
    function cut(n) {
      var t, re = new RegExp(TOK.source, 'g');
      while ((t = re.exec(txt))) { var a = t.index, e = a + t[0].length; if (a >= n) break; if (n < e) return (e < txt.length || done) ? e : a; }
      var sl = txt.slice(0, n), ob = sl.lastIndexOf('['), cb = sl.lastIndexOf(')');
      if (!done && ob > cb && /\[[^\]\n]*(\]\(?[^\s)]*)?$/.test(sl.slice(ob))) return ob;
      if (!done && (sl.split('**').length % 2 === 0)) return sl.lastIndexOf('**');
      return n;
    }
    function paint() {
      raf = 0; var c = shown >= txt.length && done !== null;
      body.innerHTML = fmt(txt.slice(0, shown)) + (c ? '' : '<span class="uaa-cur" aria-hidden="true"></span>'); m.scrollTop = m.scrollHeight;
    }
    function tick(ts) {
      raf = 0; var dt = last ? Math.min(ts - last, 100) : 16; last = ts;
      var back = txt.length - shown, speed = Math.max(0.09, back / 1500);   // ~90 chars/s, faster when far behind
      if (RM) shown = txt.length; else if (back > 0) shown = Math.max(shown, cut(Math.min(txt.length, shown + Math.max(1, Math.round(speed * dt)))));
      paint();
      if (shown < txt.length) raf = requestAnimationFrame(tick); else { last = 0; if (done) end(); }
    }
    function kick() { if (!raf) raf = requestAnimationFrame(tick); }
    function status(s) { stx.textContent = s ? s + '…' : ''; stx.style.display = s ? '' : 'none'; m.scrollTop = m.scrollHeight; }
    function end() { var d = done; done = 0; if (!d) return; busy = 0; shown = txt.length; paint(); if (d.sources) box.insertAdjacentHTML('beforeend', src(d.sources)); sugg(box, d.suggest); H.push({ role: 'assistant', content: txt }); save(); m.scrollTop = m.scrollHeight; }
    function fin(d) { status(''); done = d || {}; if (shown >= txt.length) { if (raf) cancelAnimationFrame(raf); raf = 0; end(); } else kick(); }
    function fail(msg) { busy = 0; H.pop(); status(''); done = {}; if (raf) cancelAnimationFrame(raf); raf = 0; shown = txt.length; if (txt) { paint(); box.insertAdjacentHTML('beforeend', '<div style="color:#b91c1c;font-size:12px;margin-top:6px">' + esc(msg) + '</div>'); } else box.textContent = msg; }
    var hist = H.slice(-10); H.push({ role: 'user', content: q });
    var isTopic = q === topicQ; topicQ = '';
    fetch(API + '/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ q: q, history: hist, stream: true, topic: (isTopic && !hist.length) ? 1 : undefined, page: { host: location.host, path: location.pathname, title: document.title.slice(0, 160), lang: lang, site: site } }) })
      .then(function (r) {
        var ct = r.headers.get('Content-Type') || '';
        if (ct.indexOf('event-stream') < 0 || !r.body || !window.TextDecoder) return r.json().then(function (d) { if (d.error) return fail(d.error); txt = d.answer || ''; fin(d); });
        var rd = r.body.getReader(), dec = new TextDecoder(), buf = '', ended = 0;
        function pump() {
          return rd.read().then(function (x) {
            if (x.done) { if (!ended) { if (txt) fin(null); else fail(T.busy); } return; }
            buf += dec.decode(x.value, { stream: true }).replace(/\r/g, ''); var k;
            while ((k = buf.indexOf('\n\n')) >= 0) {
              var line = buf.slice(0, k); buf = buf.slice(k + 2); if (line.indexOf('data:') !== 0) continue; var ev;
              try { ev = JSON.parse(line.slice(5)); } catch (_) { continue; }
              if (ev.type === 'delta') { txt += ev.text; status(''); kick(); }
              else if (ev.type === 'status') status(lang === 'es' ? T.think : ev.text);
              else if (ev.type === 'done') { ended = 1; fin(ev); }
              else if (ev.type === 'error') { ended = 1; fail(lang === 'es' ? (txt ? T.cut : T.busy) : ev.text); }
            }
            return pump();
          });
        }
        return pump();
      }).catch(function () { fail(T.busy); });
  }
})();
