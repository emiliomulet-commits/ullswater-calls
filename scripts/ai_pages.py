"""AI pre-check page and the 'Ask EU Funding' chat widget (both call the ullswater-ai Worker)."""

AI_API = "https://ullswater-ai.emilio-mulet-b52.workers.dev"


def review_html(calls):
    opts = "".join(f'<option value="{c["id"]}">{c["id"]} – {c["title"][:90]}</option>' for c in calls if c["kind"] == "topic")
    return f"""<main><section class="hero"><div class="wrap"><div class="crumbs"><a href="/">All calls</a> › AI pre-check</div><p class="kicker">AI pre-check · free</p>
<h1>Check your project idea against an EU call</h1><p class="lead">Paste your idea and choose the call. In about 20 seconds you get a preliminary fit assessment, indicative scores on the three Horizon Europe criteria, the gaps to close and the partners you are missing. Then our experts can review it properly.</p></div></section>
<div class="wrap"><style>
.rv{{border:1px solid var(--line);border-radius:12px;padding:22px;background:#fff;margin:22px 0}}.rv label{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);display:flex;flex-direction:column;gap:4px;margin-bottom:12px}}
.rv input,.rv select,.rv textarea{{font:inherit;font-size:15px;border:1px solid var(--line);border-radius:8px;padding:10px;width:100%;background:#fff}}.rv textarea{{min-height:170px}}
.rvg{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:12px}}.sc{{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0;padding:0;list-style:none}}.sc li{{background:var(--bg);border-radius:8px;padding:10px 16px;font-size:14px;color:var(--muted)}}.sc strong{{display:block;font-size:24px;color:var(--navy)}}
.fit{{display:inline-block;padding:4px 12px;border-radius:999px;font-weight:700;font-size:13px;text-transform:uppercase;letter-spacing:.05em}}.fit.strong{{background:#e7f6ec;color:#05603a}}.fit.partial{{background:#fff4d6;color:#7a5600}}.fit.weak{{background:#fdecea;color:#912018}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.cols h3{{font-size:16px;color:var(--navy);margin:14px 0 4px}}.spin{{display:inline-block;width:16px;height:16px;border:2px solid var(--line);border-top-color:var(--navy);border-radius:50%;animation:sp 1s linear infinite;vertical-align:-3px}}@keyframes sp{{to{{transform:rotate(360deg)}}}}
@media(max-width:860px){{.rvg,.cols{{grid-template-columns:1fr}}}}</style>
<form class="rv" onsubmit="return false">
<div class="rvg"><label>Call<input id="rv-call" list="rv-list" placeholder="Type a topic ID or keyword"><datalist id="rv-list">{opts}</datalist></label>
<label>Organisation type<select id="rv-org"><option>SME</option><option>Large company</option><option>University</option><option>Research organisation</option><option>Public body</option><option>NGO / association</option></select></label>
<label>Maturity<select id="rv-trl"><option>TRL 1–4 (research)</option><option selected>TRL 5–7 (prototype / pilot)</option><option>TRL 8–9 (close to market)</option></select></label></div>
<label>Your project idea (at least 25 words; do not include confidential information)<textarea id="rv-idea" maxlength="4000" placeholder="Objectives, what is new, who benefits, expected results, partners you already have…"></textarea></label>
<div class="actions"><button class="btn" id="rv-go" type="button">Run the AI pre-check</button><span id="rv-msg" class="note" style="align-self:center"></span></div>
<p class="disc">Preliminary, automated assessment generated with an AI model (Llama 3.3 on Cloudflare Workers AI) from the official topic text. It is not an evaluation by the European Commission. Your text is processed to produce the answer and is not stored by Ullswater Investments. If you later use AI-generated text in a proposal, Horizon Europe requires you to declare it.</p></form>
<div id="rv-out"></div></div></main>
<script>(function(){{var $=function(s){{return document.querySelector(s)}},u=new URLSearchParams(location.search);if(u.get('call'))$('#rv-call').value=u.get('call');
function esc(s){{return String(s==null?'':s).replace(/[&<>"]/g,function(c){{return{{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]}})}}
function li(a){{return (a||[]).map(function(x){{return '<li>'+esc(x)+'</li>'}}).join('')}}
$('#rv-go').onclick=function(){{var call=$('#rv-call').value.trim().split(' ')[0],idea=$('#rv-idea').value.trim();
if(!call){{$('#rv-msg').textContent='Choose a call.';return}}if(idea.split(/\\s+/).length<25){{$('#rv-msg').textContent='Please write at least 25 words.';return}}
$('#rv-go').disabled=true;$('#rv-msg').innerHTML='<span class="spin"></span> Analysing your idea against the call…';
fetch('{AI_API}/review',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{call:call,idea:idea,org:$('#rv-org').value,trl:$('#rv-trl').value}})}})
.then(function(r){{return r.json()}}).then(function(d){{$('#rv-go').disabled=false;if(d.error){{$('#rv-msg').textContent=d.error;return}}$('#rv-msg').textContent='';var r=d.result,s=r.scores||{{}};
var tot=(+s.excellence||0)+(+s.impact||0)+(+s.implementation||0);
var mail='mailto:eufunding@ullswaterinvestments.com?subject='+encodeURIComponent('Expert review – '+d.call.id)+'&body='+encodeURIComponent('Call: '+d.call.id+' – '+d.call.title+'\\n\\nIdea:\\n'+idea+'\\n\\nAI pre-check: fit '+r.fit+', scores '+s.excellence+'/'+s.impact+'/'+s.implementation+'\\n\\nOrganisation and contact:\\n');
$('#rv-out').innerHTML='<section class="rv"><div class="meta"><span class="fit '+esc(r.fit)+'">'+esc(r.fit)+' fit</span><a class="code" href="/call/'+d.call.id.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')+'/">'+esc(d.call.id)+'</a></div>'+
'<h2 style="margin:10px 0 4px">'+esc(d.call.title)+'</h2><p>'+esc(r.fit_reason)+'</p>'+
'<ul class="sc"><li><strong>'+esc(s.excellence)+'/5</strong>Excellence</li><li><strong>'+esc(s.impact)+'/5</strong>Impact</li><li><strong>'+esc(s.implementation)+'/5</strong>Implementation</li><li><strong>'+tot+'/15</strong>indicative total (threshold usually 10)</li></ul>'+
'<div class="cols"><div><h3>Strengths</h3><ul>'+li(r.strengths)+'</ul><h3>Partners you may need</h3><ul>'+li(r.consortium)+'</ul></div><div><h3>Gaps to close</h3><ul>'+li(r.gaps)+'</ul><h3>Next steps</h3><ul>'+li(r.next_steps)+'</ul></div></div>'+
'<p class="note"><strong>Maturity:</strong> '+esc(r.trl_note)+'</p></section>'+
'<div class="cta"><div><strong>Turn this into a fundable proposal</strong><p>Our experts review your idea against the full call, the evaluation criteria and past winners, and help you build the consortium.</p></div><a class="btn" href="'+mail+'">Request an expert review</a></div>';
$('#rv-out').scrollIntoView({{behavior:'smooth'}})}}).catch(function(){{$('#rv-go').disabled=false;$('#rv-msg').textContent='The service is busy. Please try again in a minute.'}})}};}})();</script>"""


CHAT = """<div id="aeu" style="position:fixed;right:18px;bottom:18px;z-index:50;font-family:Inter,system-ui,sans-serif">
<button id="aeu-b" type="button" style="background:#233567;color:#fff;border:0;border-radius:999px;padding:12px 18px;font-weight:700;box-shadow:0 6px 20px rgba(0,0,0,.2);cursor:pointer">💬 Ask EU Funding</button>
<div id="aeu-p" style="display:none;width:min(400px,92vw);height:min(600px,78vh);background:#fff;border:1px solid #e5e7eb;border-radius:14px;box-shadow:0 12px 40px rgba(0,0,0,.25);flex-direction:column;overflow:hidden">
<div style="background:#233567;color:#fff;padding:12px 14px;display:flex;justify-content:space-between;align-items:center"><strong>Ask EU Funding <span style="color:#c9a646;font-weight:600">· AI</span></strong><button id="aeu-x" type="button" style="background:none;border:0;color:#fff;font-size:20px;cursor:pointer">×</button></div>
<div id="aeu-m" style="flex:1;overflow:auto;padding:12px;font-size:14px;line-height:1.5"><div style="background:#f5f6f8;border-radius:10px;padding:10px 12px">Hi! Ask me about open EU calls, Spanish grants, deadlines or how EU funding works. I can search, filter, read and compare calls. Try: “RIA calls in Cluster 4 on AI closing before April 2027, largest budget first” or “Can SMEs apply to this call?”.</div></div>
<form id="aeu-f" style="display:flex;gap:6px;padding:10px;border-top:1px solid #e5e7eb"><input id="aeu-i" maxlength="600" placeholder="Your question…" style="flex:1;font:inherit;font-size:14px;border:1px solid #e5e7eb;border-radius:8px;padding:9px"><button style="background:#c9a646;color:#233567;border:0;border-radius:8px;padding:0 14px;font-weight:700;cursor:pointer">Send</button></form>
<div style="font-size:11px;color:#6b7280;padding:0 12px 8px">AI answers can be wrong. Check the official call. Questions are stored anonymously to improve the service. Expert help: <a href="https://www.ullswaterinvestments.com/eu-fund-matching">Ullswater</a></div></div></div>
""" + r"""<script>(function(){var b=document.getElementById('aeu-b'),p=document.getElementById('aeu-p'),m=document.getElementById('aeu-m'),f=document.getElementById('aeu-f'),i=document.getElementById('aeu-i'),busy=0,H=[];
try{H=JSON.parse(sessionStorage.getItem('aeu-h')||'[]')}catch(e){H=[]}
function save(){try{sessionStorage.setItem('aeu-h',JSON.stringify(H.slice(-12)))}catch(e){}}
function t(){var o=p.style.display==='none';p.style.display=o?'flex':'none';b.style.display=o?'none':'';if(o)i.focus()}b.onclick=t;document.getElementById('aeu-x').onclick=t;
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function fmt(s){var L=[];return esc(s).replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g,function(_,t,u){L.push('<a href="'+u+'" style="color:#233567">'+t+'</a>');return'\u0000'+(L.length-1)+'\u0000'}).replace(/^#{1,6}\s*(.+)$/gm,'<strong>$1</strong>').replace(/\*\*([^*\n]+)\*\*/g,'<strong>$1</strong>').replace(/(https?:\/\/[^\s)<]+[^\s)<.,;:])/g,'<a href="$1" style="color:#233567;word-break:break-all">$1</a>').replace(/\u0000(\d+)\u0000/g,function(_,n){return L[n]}).replace(/^[-*] /gm,'• ').replace(/\n{3,}/g,'\n\n').replace(/\n/g,'<br>')}
function add(h,me){var d=document.createElement('div');d.style.cssText='margin-top:8px;border-radius:10px;padding:10px 12px;'+(me?'background:#233567;color:#fff;margin-left:30px':'background:#f5f6f8');d.innerHTML=h;m.appendChild(d);m.scrollTop=m.scrollHeight;return d}
function src(a){if(!a||!a.length)return'';return'<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:4px">'+a.map(function(x){return'<a href="'+esc(x.url)+'" title="'+esc(x.title)+'" style="font-size:11px;background:#fff;border:1px solid #e5e7eb;border-radius:999px;padding:2px 8px;color:#233567;text-decoration:none">'+esc(x.id)+'</a>'}).join('')+'</div>'}
H.forEach(function(x){add(x.role==='user'?esc(x.content):fmt(x.content),x.role==='user')});
if(H.length){var c=document.createElement('button');c.type='button';c.textContent='New conversation';c.style.cssText='margin-top:8px;background:none;border:0;color:#6b7280;font-size:12px;text-decoration:underline;cursor:pointer';c.onclick=function(){H=[];save();location.reload()};m.appendChild(c)}
f.onsubmit=function(e){e.preventDefault();var q=i.value.trim();if(!q||busy)return;busy=1;i.value='';add(esc(q),1);
var w=add(''),body=document.createElement('div'),st=document.createElement('div'),txt='',raf=0;st.style.cssText='color:#6b7280;font-style:italic;font-size:13px';st.textContent='Thinking…';w.appendChild(body);w.appendChild(st);
function paint(){raf=0;body.innerHTML=fmt(txt);m.scrollTop=m.scrollHeight}
function status(s){st.textContent=s?s+'…':'';st.style.display=s?'':'none';m.scrollTop=m.scrollHeight}
function fin(d){busy=0;status('');if(raf)cancelAnimationFrame(raf);paint();if(d&&d.sources)w.insertAdjacentHTML('beforeend',src(d.sources));H.push({role:'assistant',content:txt});save();m.scrollTop=m.scrollHeight}
function fail(msg){busy=0;H.pop();status('');if(txt){paint();w.insertAdjacentHTML('beforeend','<div style="color:#b91c1c;font-size:12px;margin-top:6px">'+esc(msg)+'</div>')}else w.textContent=msg}
var hist=H.slice(-10);H.push({role:'user',content:q});
fetch('AI_API/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q:q,history:hist,page:{path:location.pathname},stream:true})}).then(function(r){
var ct=r.headers.get('Content-Type')||'';
if(ct.indexOf('event-stream')<0||!r.body||!window.TextDecoder){return r.json().then(function(d){if(d.error)return fail(d.error);txt=d.answer||'';fin(d)})}
var rd=r.body.getReader(),dec=new TextDecoder(),buf='',ended=0;
function pump(){return rd.read().then(function(x){if(x.done){if(!ended){txt?fin(null):fail('The assistant is busy. Please try again.')}return}
buf+=dec.decode(x.value,{stream:true}).replace(/\r/g,'');var k;while((k=buf.indexOf('\n\n'))>=0){var line=buf.slice(0,k);buf=buf.slice(k+2);if(line.indexOf('data:')!==0)continue;var ev;try{ev=JSON.parse(line.slice(5))}catch(_){continue}
if(ev.type==='delta'){txt+=ev.text;status('');if(!raf)raf=requestAnimationFrame(paint)}else if(ev.type==='status'){status(ev.text)}else if(ev.type==='done'){ended=1;fin(ev)}else if(ev.type==='error'){ended=1;fail(ev.text)}}
return pump()})}
return pump()}).catch(function(){fail('The assistant is busy. Please try again.')})}})();</script>""".replace("AI_API", AI_API)
