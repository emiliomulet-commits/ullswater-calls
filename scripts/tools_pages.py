"""Static interactive tools: Horizon Europe budget calculator and consortium eligibility checker."""

EU27 = ["Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia", "Denmark", "Estonia", "Finland", "France", "Germany", "Greece",
        "Hungary", "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg", "Malta", "Netherlands", "Poland", "Portugal", "Romania",
        "Slovakia", "Slovenia", "Spain", "Sweden"]
# Official "List of participating countries in Horizon Europe" V4.2 (07.10.2026)
ASSOC_ALL = ["Albania", "Armenia", "Bosnia and Herzegovina", "Egypt", "Faroe Islands", "Georgia", "Iceland", "Israel", "Kosovo", "Moldova",
             "Montenegro", "North Macedonia", "Norway", "Serbia", "Switzerland", "Tunisia", "Türkiye", "Ukraine", "United Kingdom"]
ASSOC_P2 = ["Canada", "Japan", "New Zealand", "Republic of Korea"]  # associated to Pillar II only
OTHER = ["United States", "Australia", "Brazil", "Chile", "China", "India", "Mexico", "Morocco", "Singapore", "South Africa", "Other (non-associated)"]

TOOLS_CSS = """.tool{border:1px solid var(--line);border-radius:12px;padding:22px;background:#fff;margin:22px 0}
.tool h2{margin-top:0}.row{display:grid;grid-template-columns:2fr 1.2fr 1fr 1fr 1fr 1fr 40px;gap:8px;align-items:end;margin-bottom:8px}
.row label,.crow label{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);display:flex;flex-direction:column;gap:4px}
.tool input,.tool select{font:inherit;font-size:14px;border:1px solid var(--line);border-radius:6px;padding:7px 9px;width:100%;background:#fff}
.rm{border:0;background:var(--bg);border-radius:6px;height:36px;cursor:pointer;font-size:16px}
.res{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0 0;padding:0;list-style:none}.res li{background:var(--bg);border-radius:8px;padding:10px 16px;font-size:14px;color:var(--muted)}.res strong{display:block;font-size:22px;color:var(--navy)}
.crow{display:grid;grid-template-columns:2fr 1.5fr 1.5fr 40px;gap:8px;align-items:end;margin-bottom:8px}
.checks{list-style:none;padding:0;margin:14px 0 0}.checks li{padding:8px 12px;border-radius:8px;margin-bottom:6px;font-size:15px}
.ok{background:#e7f6ec;color:#05603a}.ko{background:#fdecea;color:#912018}.warn{background:#fff4d6;color:#7a5600}
@media(max-width:860px){.row,.crow{grid-template-columns:1fr 1fr}.row label:first-child,.crow label:first-child{grid-column:1/-1}}"""


def countries_opts():
    o = '<optgroup label="EU Member States">' + "".join(f"<option>{c}</option>" for c in EU27) + "</optgroup>"
    o += '<optgroup label="Associated countries (whole programme)">' + "".join(f"<option>{c}</option>" for c in ASSOC_ALL) + "</optgroup>"
    o += '<optgroup label="Associated to Pillar II only">' + "".join(f"<option>{c}</option>" for c in ASSOC_P2) + "</optgroup>"
    o += '<optgroup label="Other countries">' + "".join(f"<option>{c}</option>" for c in OTHER) + "</optgroup>"
    return o


def tools_html(MAIN):
    import json
    js_data = json.dumps({"eu": EU27, "assoc": ASSOC_ALL, "p2": ASSOC_P2})
    return f"""<main><section class="hero"><div class="wrap"><div class="crumbs"><a href="/">All calls</a> › Tools</div><p class="kicker">Free tools</p>
<h1>Horizon Europe proposal tools</h1><p class="lead">Estimate your consortium budget and EU grant, and check that your consortium meets the standard eligibility conditions, in a couple of minutes.</p>
<div class="actions"><a class="btn ghost" href="#budget">Budget calculator</a><a class="btn ghost" href="#consortium">Consortium checker</a><a class="btn ghost" href="/finder/">Fund Finder</a></div></div></section>
<div class="wrap"><style>{TOOLS_CSS}</style>

<section class="tool" id="budget"><h2>Budget and EU grant calculator</h2>
<p class="note">For Horizon Europe actual-cost grants. Personnel costs = person-months × monthly cost. Indirect costs are a flat 25% of eligible direct costs, excluding subcontracting. Funding rate: 100% for Research and Innovation Actions (RIA) and Coordination and Support Actions (CSA); 70% for Innovation Actions (IA), or 100% for non-profit legal entities.</p>
<div class="crow" style="grid-template-columns:1fr 1fr 2fr"><label>Type of action<select id="b-type"><option value="RIA">RIA – Research and Innovation Action</option><option value="IA">IA – Innovation Action</option><option value="CSA">CSA – Coordination and Support Action</option></select></label></div>
<div id="b-rows"></div>
<button class="btn ghost" type="button" id="b-add">+ Add partner</button>
<ul class="res" id="b-res"></ul>
<div class="scroll" style="margin-top:14px"><table class="tbl" id="b-tbl"></table></div>
<p class="disc">Indicative estimate. Many 2026–2027 topics use lump-sum funding, where the budget is fixed in the proposal and paid against completed work packages; the cost logic is the same. Always check the call conditions and the Model Grant Agreement.</p></section>

<section class="tool" id="consortium"><h2>Consortium eligibility checker</h2>
<p class="note">Standard condition for Horizon Europe collaborative actions (RIA, IA): at least three independent legal entities, each established in a different EU Member State or associated country, with at least one in an EU Member State. Country list: official “List of participating countries in Horizon Europe”, version of 7 October 2026.</p>
<div class="crow" style="grid-template-columns:1fr 1fr 2fr"><label>Programme part<select id="c-pillar"><option value="2">Pillar II – Clusters, Missions, partnerships</option><option value="1">Pillar I or III / WIDERA (e.g. ERC, MSCA, EIC)</option></select></label></div>
<div id="c-rows"></div>
<button class="btn ghost" type="button" id="c-add">+ Add partner</button>
<ul class="checks" id="c-res"></ul>
<p class="disc">Some topics restrict participation (for example for security reasons) or add extra conditions. Read the topic conditions, and the “Topic update” on the portal for recently associated countries.</p>
<div class="cta"><div><strong>Missing a partner?</strong><p>Every call page lists organisations with a track record in the topic, and our partner board connects you with organisations looking for consortia.</p></div><a class="btn" href="/partners/">Partner board →</a></div>
</section></div></main>
<script>
(function(){{
var D={js_data},fmt=function(n){{return '€'+Math.round(n).toLocaleString('en-GB')}},$=function(s){{return document.querySelector(s)}};
var CO='{countries_opts().replace("'", "&#39;")}';
// ---- budget
function brow(n){{var d=document.createElement('div');d.className='row';d.innerHTML='<label>Partner<input class="p" value="Partner '+n+'"></label><label>Legal status<select class="np"><option value="0">For-profit</option><option value="1">Non-profit (university, RTO, public)</option></select></label><label>Person-months<input class="pm" type="number" min="0" value="36"></label><label>Monthly personnel cost (€)<input class="mc" type="number" min="0" value="6000"></label><label>Other direct costs (€)<input class="oc" type="number" min="0" value="40000"></label><label>Subcontracting (€)<input class="sc" type="number" min="0" value="0"></label><button class="rm" type="button" title="Remove">×</button>';d.querySelector('.rm').onclick=function(){{d.remove();calc()}};d.querySelectorAll('input,select').forEach(function(e){{e.oninput=calc;e.onchange=calc}});$('#b-rows').appendChild(d)}}
function calc(){{var t=$('#b-type').value,rows=[].slice.call(document.querySelectorAll('#b-rows .row')),T={{c:0,g:0,pm:0}},h='<thead><tr><th>Partner</th><th>Personnel</th><th>Other direct</th><th>Subcontracting</th><th>Indirect (25%)</th><th>Total cost</th><th>Rate</th><th>EU grant</th></tr></thead><tbody>';
rows.forEach(function(r){{var v=function(c){{return +r.querySelector(c).value||0}},per=v('.pm')*v('.mc'),oc=v('.oc'),sc=v('.sc'),ind=0.25*(per+oc),tot=per+oc+sc+ind,rate=(t==='IA'&&r.querySelector('.np').value==='0')?0.7:1,g=tot*rate;T.c+=tot;T.g+=g;T.pm+=v('.pm');
h+='<tr><td>'+r.querySelector('.p').value.replace(/[<>&]/g,'')+'</td><td>'+fmt(per)+'</td><td>'+fmt(oc)+'</td><td>'+fmt(sc)+'</td><td>'+fmt(ind)+'</td><td><strong>'+fmt(tot)+'</strong></td><td>'+(rate*100)+'%</td><td><strong>'+fmt(g)+'</strong></td></tr>'}});
$('#b-tbl').innerHTML=h+'</tbody>';$('#b-res').innerHTML='<li><strong>'+fmt(T.c)+'</strong>total eligible costs</li><li><strong>'+fmt(T.g)+'</strong>requested EU contribution</li><li><strong>'+(T.c?Math.round(100*T.g/T.c):0)+'%</strong>average funding rate</li><li><strong>'+T.pm+'</strong>person-months</li>'}}
$('#b-type').onchange=calc;$('#b-add').onclick=function(){{brow(document.querySelectorAll('#b-rows .row').length+1);calc()}};brow(1);brow(2);brow(3);calc();
// ---- consortium
function crow(n,c){{var d=document.createElement('div');d.className='crow';d.innerHTML='<label>Partner<input class="p" value="Partner '+n+'"></label><label>Country<select class="c">'+CO+'</select></label><label>Independent from the others?<select class="ind"><option value="1">Yes</option><option value="0">No (same group / affiliated)</option></select></label><button class="rm" type="button" title="Remove">×</button>';if(c)d.querySelector('.c').value=c;d.querySelector('.rm').onclick=function(){{d.remove();check()}};d.querySelectorAll('input,select').forEach(function(e){{e.oninput=check;e.onchange=check}});$('#c-rows').appendChild(d)}}
function check(){{var p2=$('#c-pillar').value==='2',rows=[].slice.call(document.querySelectorAll('#c-rows .crow')),eu=0,set={{}},res=[],nonassoc=[],indep=0;
rows.forEach(function(r){{var c=r.querySelector('.c').value,i=r.querySelector('.ind').value==='1',ok=D.eu.indexOf(c)>-1||D.assoc.indexOf(c)>-1||(p2&&D.p2.indexOf(c)>-1);if(D.eu.indexOf(c)>-1)eu++;if(ok&&i){{set[c]=1;indep++}}if(!ok)nonassoc.push(c)}});
var n=Object.keys(set).length;
res.push([rows.length>=3,'At least 3 legal entities ('+rows.length+')']);
res.push([n>=3,'Independent entities from at least 3 different eligible countries ('+n+')']);
res.push([eu>=1,'At least one entity established in an EU Member State ('+eu+')']);
var h=res.map(function(x){{return '<li class="'+(x[0]?'ok':'ko')+'">'+(x[0]?'✔ ':'✘ ')+x[1]+'</li>'}}).join('');
if(!p2)rows.forEach(function(r){{var c=r.querySelector('.c').value;if(D.p2.indexOf(c)>-1)h+='<li class="warn">⚠ '+c+' is associated to Pillar II only: outside Pillar II it counts as a non-associated country.</li>'}});
if(nonassoc.length)h+='<li class="warn">⚠ Non-associated countries ('+nonassoc.join(', ')+') can join, but they do not count towards the minimum and are usually not funded unless the topic allows it.</li>';
if(res.every(function(x){{return x[0]}}))h+='<li class="ok">Your consortium meets the standard minimum. Check the topic for extra conditions.</li>';
$('#c-res').innerHTML=h}}
$('#c-pillar').onchange=check;$('#c-add').onclick=function(){{crow(document.querySelectorAll('#c-rows .crow').length+1);check()}};crow(1,'Spain');crow(2,'Germany');crow(3,'United Kingdom');check();
}})();
</script>"""
