"""Fund Finder page (client-side matching on site/data/finder.json)."""


def finder_html(MAIN, form_alerts="/alerts/"):
    return f"""<main><section class="hero"><div class="wrap"><div class="crumbs"><a href="/">All calls</a> › Fund Finder</div><p class="kicker">Fund Finder</p>
<h1>Which EU call fits your project?</h1><p class="lead">Describe your project and your organisation. The Fund Finder compares it with every open and forthcoming EU call and returns a ranked shortlist with the reasons for each match. Nothing you type leaves your browser.</p></div></section>
<div class="wrap"><style>
.ff{{border:1px solid var(--line);border-radius:12px;padding:22px;background:#fff;margin:22px 0}}.ffg{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:12px}}
.ff label{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);display:flex;flex-direction:column;gap:4px}}
.ff textarea,.ff select{{font:inherit;font-size:15px;border:1px solid var(--line);border-radius:8px;padding:10px;width:100%;background:#fff}}.ff textarea{{min-height:120px;resize:vertical}}
.hit{{border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:0 0 12px;background:#fff}}.hit h3{{margin:6px 0 4px;font-size:17px}}.hit h3 a{{text-decoration:none}}
.score{{display:inline-block;min-width:46px;text-align:center;background:var(--navy);color:#fff;border-radius:6px;padding:2px 8px;font-weight:700;font-size:13px}}
.why{{font-size:14px;color:var(--muted);margin:6px 0 0}}.why b{{color:var(--ink)}}
@media(max-width:860px){{.ffg{{grid-template-columns:1fr 1fr}}}}
</style>
<form class="ff" id="ff" onsubmit="return false">
<label>Your project in a few sentences<textarea id="ff-q" placeholder="e.g. We develop an AI platform that predicts failures in wind turbines using federated sensor data from several operators. We want to pilot it with two utilities."></textarea></label>
<div class="ffg">
<label>Organisation type<select id="ff-org"><option value="sme">SME / start-up</option><option value="large">Large company</option><option value="uni">University</option><option value="rto">Research organisation</option><option value="pub">Public body</option><option value="ngo">Association / NGO</option></select></label>
<label>Maturity (TRL)<select id="ff-trl"><option value="low">Research (TRL 1–4)</option><option value="mid" selected>Prototype / pilot (TRL 5–7)</option><option value="high">Close to market (TRL 8–9)</option></select></label>
<label>How do you want to apply?<select id="ff-cons"><option value="any">Either way</option><option value="cons">In a consortium</option><option value="alone">On our own</option></select></label>
<label>Deadline<select id="ff-dl"><option value="">Any</option><option value="60">Within 2 months</option><option value="120">Within 4 months</option><option value="240">Within 8 months</option></select></label>
</div>
<div class="actions"><button class="btn" id="ff-go" type="button">Find matching calls</button><span id="ff-msg" class="note" style="align-self:center"></span></div>
</form>
<div id="ff-out"></div>
<div class="cta" id="ff-cta" hidden><div><strong>Want an expert opinion on your shortlist?</strong><p>Ullswater Investments reviews your project against the best-matching calls, checks eligibility and tells you where your chances are highest.</p></div>
<div class="actions" style="margin:0"><a class="btn" id="ff-mail" href="#">Request an expert review</a><a class="btn ghost" id="ff-alert" href="{form_alerts}">🔔 Get alerts for new matches</a></div></div>
</div></main>
<script>
(function(){{
var IDX=null,$=function(s){{return document.querySelector(s)}};
var STOP='the and for with that this from are our we will which their have has into using use based also can more new such its not but all any been other than they them these those would could should about over under between within across very your you'.split(' ');
function norm(s){{return (s||'').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g,'')}}
function stem(w){{return w.replace(/(ies)$/,'y').replace(/(ing|ed|es|s)$/,'')}}
function toks(s){{var w=norm(s).match(/[a-z][a-z0-9\\-]{{2,}}/g)||[];w=w.filter(function(x){{return STOP.indexOf(x)<0}});var out={{}};w.forEach(function(x){{out[stem(x)]=1}});for(var i=0;i<w.length-1;i++)out[stem(w[i])+' '+stem(w[i+1])]=1;return out}}
function load(cb){{if(IDX)return cb();$('#ff-msg').textContent='Loading calls…';fetch('/data/finder.json').then(function(r){{return r.json()}}).then(function(d){{IDX=d.map(function(c){{var ws={{}};for(var k in c.w)ws[k.split(' ').map(stem).join(' ')]=c.w[k];c.ws=ws;return c}});$('#ff-msg').textContent='';cb()}})}}
function days(d){{return d?Math.round((new Date(d+'T00:00:00')-new Date())/864e5):null}}
function money(v){{return v>=1e6?'€'+(v/1e6).toFixed(1).replace('.0','')+'M':'€'+Math.round(v/1e3)+'k'}}
function run(){{var q=$('#ff-q').value.trim();if(q.split(/\\s+/).length<6){{$('#ff-msg').textContent='Please describe your project in at least a couple of sentences.';return}}
load(function(){{var T=toks(q),org=$('#ff-org').value,trl=$('#ff-trl').value,cons=$('#ff-cons').value,dl=+$('#ff-dl').value||0;
var res=IDX.map(function(c){{var s=0,hits=[];for(var k in T)if(c.ws[k]){{s+=c.ws[k]*(k.indexOf(' ')>0?1.6:1);hits.push([k,c.ws[k]])}}
if(!s)return null;var f=1,why=[];
if(trl==='low'&&(c.a==='RIA'||c.a==='MSCA'))f*=1.25,why.push('research-oriented action');
if(trl==='mid'&&(c.a==='IA'||c.a==='RIA'))f*=1.15,why.push(c.a==='IA'?'innovation action for pilots and demonstration':'research and innovation action');
if(trl==='high'&&(c.a==='IA'||c.a==='EIC'||c.k==='cascade'))f*=1.3,why.push('close-to-market support');
if(trl==='high'&&c.a==='RIA')f*=0.75;
if(cons==='alone'&&(c.k==='cascade'||c.a==='EIC'))f*=1.4,why.push('you can apply on your own');
if(cons==='alone'&&(c.a==='RIA'||c.a==='IA'))f*=0.6;
if(cons==='cons'&&c.k==='cascade')f*=0.7;
if(org==='sme'&&c.k==='cascade')f*=1.15,why.push('cascade funding usually targets SMEs');
if((org==='uni'||org==='rto')&&c.a==='CSA')f*=1.05;
var dd=days(c.d);if(dl&&(dd===null||dd>dl))return null;if(dd!==null&&dd<10)f*=0.6;
if(c.s==='open')f*=1.05;
hits.sort(function(a,b){{return b[1]-a[1]}});return {{c:c,s:s*f,hits:hits.slice(0,5).map(function(h){{return h[0]}}),why:why}}}}).filter(Boolean).sort(function(a,b){{return b.s-a.s}}).slice(0,12);
if(!res.length){{$('#ff-out').innerHTML='<div class="empty">No close match. Try describing the technology, the sector and the expected results in more detail.</div>';$('#ff-cta').hidden=false;return}}
var top=res[0].s,html='<h2>Your best-matching calls</h2>';
res.forEach(function(r){{var c=r.c,pct=Math.max(35,Math.round(100*r.s/top)),dd=days(c.d);
html+='<article class="hit"><div class="meta"><span class="score">'+pct+'%</span><span class="tag '+(c.s==='open'?'open':'fc')+'">'+(c.s==='open'?'Open':'Forthcoming')+'</span><span class="tag">'+c.p+'</span><span class="code">'+c.id+'</span></div>'+
'<h3><a href="/call/'+c.id.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')+'/">'+c.t.replace(/[<>&]/g,'')+'</a></h3>'+
'<p class="why"><b>Deadline:</b> '+(c.d||'TBC')+(dd!==null?' ('+dd+' days)':'')+(c.lo&&c.hi?' · <b>EU contribution per project:</b> '+(c.lo===c.hi?money(c.lo):money(c.lo)+'–'+money(c.hi)):'')+'</p>'+
'<p class="why"><b>Why it matches:</b> '+r.hits.join(', ')+(r.why.length?' · '+r.why.join(' · '):'')+'</p></article>'}});
$('#ff-out').innerHTML=html;$('#ff-cta').hidden=false;
var list=res.slice(0,6).map(function(r){{return '- '+r.c.id+' – '+r.c.t}}).join('\\n');
$('#ff-mail').href='mailto:eufunding@ullswaterinvestments.com?subject='+encodeURIComponent('Fund Finder – expert review request')+'&body='+encodeURIComponent('Project:\\n'+q+'\\n\\nShortlist from the Fund Finder:\\n'+list+'\\n\\nOrganisation and contact:\\n');
$('#ff-alert').href='/alerts/?q='+encodeURIComponent(Object.keys(T).filter(function(k){{return k.indexOf(' ')<0}}).slice(0,8).join(' '));
$('#ff-out').scrollIntoView({{behavior:'smooth'}})}})}}
$('#ff-go').onclick=run;
}})();
</script>"""
