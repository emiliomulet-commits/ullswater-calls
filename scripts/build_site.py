#!/usr/bin/env python3
"""Build the static site for calls.ullswaterinvestments.com from site/data/calls.json.

Output (in site/): index.html, programme/<slug>/index.html, closing-soon/index.html,
sitemap.xml, robots.txt, 404.html, CNAME, assets/app.js
"""
import json
from pathlib import Path
import re
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import call_pages
import finder_page
import extra_pages
import ai_pages
import tools_pages
import theme_pages
from datetime import date, datetime
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
BASE = "https://calls.ullswaterinvestments.com"
MAIN = "https://www.ullswaterinvestments.com"

CSS = """:root{--navy:#233567;--navy2:#1a2850;--gold:#c9a646;--ink:#1f2937;--muted:#4b5563;--line:#e5e7eb;--bg:#f5f6f8;--red:#b42318;--green:#067647}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;font-family:Inter,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:var(--ink);background:#fff;line-height:1.6}
a{color:var(--navy)}a:hover{color:var(--navy2)}
.wrap{max-width:1120px;margin:0 auto;padding:0 20px}
header.site{background:var(--navy);color:#fff}
header.site .wrap{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:64px;flex-wrap:wrap}
.brand{color:#fff;text-decoration:none;font-weight:800;font-size:18px;letter-spacing:.01em}.brand span{color:var(--gold);font-weight:600}
nav.cats{background:var(--navy2)}nav.cats .wrap{display:flex;gap:4px;overflow-x:auto;padding-top:6px;padding-bottom:6px}
nav.cats a{color:#dbe2f5;text-decoration:none;font-size:14px;padding:6px 10px;border-radius:6px;white-space:nowrap}
nav.cats a:hover,nav.cats a[aria-current]{background:rgba(255,255,255,.12);color:#fff}
.btn.gold{background:#c9a646;color:#1a2850;border-color:#c9a646}.top-links a{color:#fff;font-size:14px;text-decoration:none;margin-left:16px;opacity:.9}
.hero{background:var(--bg);border-bottom:1px solid var(--line)}.hero .wrap{padding:40px 20px 32px}
.kicker{font-size:12px;letter-spacing:.08em;text-transform:uppercase;font-weight:700;color:#8a6a1c;margin:0 0 8px}
h1{font-size:36px;line-height:1.2;margin:0 0 12px;color:var(--navy)}
.lead{font-size:18px;color:var(--muted);margin:0;max-width:780px}
.stats{display:flex;flex-wrap:wrap;gap:12px;margin:22px 0 0;padding:0;list-style:none}
.stats li{background:#fff;border:1px solid var(--line);border-radius:8px;padding:10px 16px;font-size:14px;color:var(--muted)}.stats strong{display:block;font-size:22px;color:var(--navy);line-height:1.2}
.actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}
.btn{display:inline-block;background:var(--gold);color:var(--navy);font-weight:700;text-decoration:none;padding:10px 18px;border-radius:6px;white-space:nowrap;border:0;font:inherit;cursor:pointer}
.btn.ghost{background:#fff;border:1px solid var(--line);font-weight:600}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0 0}.chips a{font-size:14px;border:1px solid var(--line);border-radius:999px;padding:4px 12px;text-decoration:none;background:#fff}
.chips a b{color:var(--muted);font-weight:600;margin-left:4px}
.filters{position:sticky;top:0;z-index:5;background:#fff;border-bottom:1px solid var(--line);box-shadow:0 2px 6px rgba(0,0,0,.03)}
.filters .wrap{display:grid;grid-template-columns:2fr repeat(4,1fr);gap:10px;padding:12px 20px}
.filters label{display:flex;flex-direction:column;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);gap:4px}
.filters input,.filters select{font:inherit;font-size:14px;text-transform:none;letter-spacing:0;font-weight:400;color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:8px 10px;background:#fff;width:100%}
.filters input:focus,.filters select:focus{outline:2px solid var(--gold);outline-offset:0}
.resbar{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;padding:18px 0 6px;color:var(--muted);font-size:14px}
.resbar strong{color:var(--navy)}.linkbtn{background:none;border:0;color:var(--navy);text-decoration:underline;cursor:pointer;font:inherit;font-size:14px;padding:0}
.call{display:grid;grid-template-columns:96px 1fr;gap:18px;border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin:0 0 14px;background:#fff}
.call[hidden]{display:none}
.date{background:var(--navy);color:#fff;border-radius:8px;text-align:center;padding:10px 6px;align-self:start}
.date small{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#dbe2f5}
.date b{display:block;font-size:22px;line-height:1.15}.date i{font-style:normal;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:#dbe2f5}
.date.soon{background:var(--red)}.date.tbc{background:#555}
.call h3{font-size:18px;line-height:1.35;margin:4px 0 2px}.call h3 a{text-decoration:none}.call h3 a:hover{text-decoration:underline}
.call p{margin:6px 0 0;color:var(--muted);font-size:15px}
.meta{font-size:13px;color:var(--muted);display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center}
.code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;color:var(--muted);word-break:break-all}
.tag{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#fff;background:var(--navy);border-radius:4px;padding:3px 8px;text-decoration:none}
.tag.open{background:var(--green)}.tag.fc{background:#8a6a1c}.tag.cas{background:#555}.tag.urg{background:var(--red)}
.facts{display:flex;flex-wrap:wrap;gap:4px 18px;margin-top:8px;font-size:14px}.facts span b{color:var(--navy)}
.more{font-size:14px;font-weight:600;margin-top:8px;display:inline-block}
.empty{border:1px dashed var(--line);border-radius:10px;padding:28px;text-align:center;color:var(--muted)}
.cta{background:var(--navy);color:#fff;border-radius:10px;padding:22px 24px;margin:32px 0;display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}
.cta strong{font-size:18px}.cta p{margin:4px 0 0;color:#dbe2f5;font-size:15px}
.about{border-top:1px solid var(--line);margin-top:24px;padding:24px 0 8px;color:var(--muted);font-size:15px}.about h2{font-size:20px;color:var(--navy);margin:0 0 8px}
.crumbs{font-size:13px;color:var(--muted);margin-bottom:14px}.crumbs a{color:var(--muted)}
.links{display:flex;flex-wrap:wrap;gap:4px 18px}.more.ext{font-weight:500;color:var(--muted)}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}.tile{display:block;border:1px solid var(--line);border-radius:10px;padding:16px;text-decoration:none;background:#fff}.tile:hover{border-color:var(--gold);box-shadow:0 4px 14px rgba(35,53,103,.08)}.tile b{display:block;color:var(--navy);font-size:17px}.tile span{display:block;color:#8a6a1c;font-weight:600;font-size:13px;margin:2px 0 6px}.tile small{color:var(--muted);font-size:13px;line-height:1.5}
.callhead .facts{font-size:15px;margin-top:14px}.sec{padding:28px 0 4px}.sec h2{font-size:24px;color:var(--navy);margin:0 0 6px}.sec>p.note{color:var(--muted);font-size:14px;margin:0 0 14px;max-width:820px}
.tbl{width:100%;border-collapse:collapse;font-size:14px;background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden}
.tbl th{background:var(--bg);text-align:left;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);padding:9px 12px;border-bottom:1px solid var(--line)}
.tbl td{padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}.tbl tr:last-child td{border-bottom:0}.tbl td.n{text-align:center;font-weight:700;color:var(--navy)}
.tbl small{color:var(--muted)}.scroll{overflow-x:auto}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.box{border:1px solid var(--line);border-radius:10px;padding:16px 18px;background:#fff}
.box h3{font-size:16px;margin:0 0 6px;color:var(--navy)}.box p{margin:0;color:var(--muted);font-size:14px}.box a.go{display:inline-block;margin-top:8px;font-weight:600;font-size:14px}
.kpi{display:flex;flex-wrap:wrap;gap:12px;margin:0 0 12px;padding:0;list-style:none}.kpi li{background:var(--bg);border-radius:8px;padding:10px 16px;font-size:14px;color:var(--muted)}.kpi strong{display:block;font-size:22px;color:var(--navy);line-height:1.2}
.bar{display:flex;height:14px;border-radius:7px;overflow:hidden;margin:6px 0 6px}.bar span{display:block}.legend{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:13px;color:var(--muted)}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.disc{font-size:13px;color:var(--muted);background:var(--bg);border-radius:8px;padding:12px 16px;margin-top:14px}
@media(max-width:860px){.grid3{grid-template-columns:1fr}}
footer.site{background:var(--navy);color:#dbe2f5;font-size:14px;margin-top:40px}footer.site .wrap{padding:28px 20px;display:flex;flex-wrap:wrap;gap:24px;justify-content:space-between}footer.site a{color:#fff}
@media(max-width:860px){.filters .wrap{grid-template-columns:1fr 1fr}.filters .q{grid-column:1/-1}.filters{position:static}}
@media(max-width:640px){h1{font-size:28px}.top-links{display:flex;overflow-x:auto;width:100%;padding-bottom:6px}.top-links a{margin:0 14px 0 0;white-space:nowrap}.call{grid-template-columns:72px 1fr;gap:12px;padding:14px}.date b{font-size:18px}}
"""

JS = r"""(function(){
var $=function(s){return document.querySelector(s)},cards=[].slice.call(document.querySelectorAll('.call')),
q=$('#f-q'),st=$('#f-status'),pg=$('#f-prog'),dl=$('#f-dl'),tp=$('#f-type'),count=$('#count'),empty=$('#empty'),list=$('#list');
if(!q)return;
var today=new Date();today.setHours(0,0,0,0);
cards.forEach(function(c){var d=c.getAttribute('data-deadline');if(d){var days=Math.round((new Date(d+'T00:00:00')-today)/864e5);c.setAttribute('data-days',days);
 var b=c.querySelector('.left');if(b&&c.getAttribute('data-status')==='open'){b.textContent=days<=0?'Closes today':days===1?'Closes tomorrow':'Closes in '+days+' days';b.hidden=false;if(days<=15)b.classList.add('urg');}}});
function norm(s){return (s||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'')}
function apply(){var words=norm(q.value).split(/\s+/).filter(Boolean),n=0,s=st.value,p=pg?pg.value:'',w=dl.value,t=tp.value;
 cards.forEach(function(c){var ok=(s==='all'||c.getAttribute('data-status')===s)&&(!p||c.getAttribute('data-prog')===p)&&(!t||c.getAttribute('data-kind')===t);
  if(ok&&w){var days=c.getAttribute('data-days');ok=days!==null&&+days<=+w;}
  if(ok&&words.length){var h=c._h||(c._h=norm(c.textContent));ok=words.every(function(x){return h.indexOf(x)>-1});}
  c.hidden=!ok;if(ok)n++;});
 count.textContent=n;empty.hidden=n>0;
 var u=new URLSearchParams();if(q.value)u.set('q',q.value);if(s!=='open')u.set('status',s);if(p)u.set('programme',p);if(w)u.set('closing',w);if(t)u.set('type',t);
 history.replaceState(null,'',(u.toString()?'?'+u:location.pathname));}
var u=new URLSearchParams(location.search);if(u.get('q'))q.value=u.get('q');if(u.get('status'))st.value=u.get('status');if(pg&&u.get('programme'))pg.value=u.get('programme');if(u.get('closing'))dl.value=u.get('closing');if(u.get('type'))tp.value=u.get('type');
[q,st,pg,dl,tp].forEach(function(e){if(e)e.addEventListener(e===q?'input':'change',apply)});
$('#reset').addEventListener('click',function(){q.value='';st.value='open';if(pg)pg.value='';dl.value='';tp.value='';apply();});
apply();})();
"""

JS += r"""
/* External links open in a new tab (Nov 2026). The build already does this for static HTML (scripts/extlinks.py);
   this covers links added later by JavaScript (Fund Finder results, Ask EU Funding answers, partner lists). */
(function(){
var own=/(^|\.)ullswaterinvestments\.(com|eu)$/i,es=/^es/i.test(document.documentElement.lang||'');
function fix(a){if(a.dataset.uwExt)return;var h=a.hostname;if(!/^https?:$/.test(a.protocol)||!h||own.test(h))return;
 a.dataset.uwExt=1;a.target='_blank';var r=(a.rel||'').split(/\s+/).filter(Boolean);['noopener','noreferrer'].forEach(function(v){if(r.indexOf(v)<0)r.push(v)});a.rel=r.join(' ');
 if(a.querySelector('.uw-sr'))return;var s=document.createElement('span');s.className='uw-sr';s.textContent=es?' (se abre en una pestaña nueva)':' (opens in a new tab)';
 if(!a.querySelector('img,svg')&&(a.textContent||'').indexOf('\u2197')<0){var i=document.createElement('span');i.className='uw-ext';i.setAttribute('aria-hidden','true');i.textContent='\u2197';a.appendChild(i)}a.appendChild(s)}
function scan(n){if(n.nodeType!==1)return;if(n.tagName==='A')fix(n);[].forEach.call(n.querySelectorAll('a[href]'),fix)}
if(!document.getElementById('uw-ext')){var st=document.createElement('style');st.id='uw-ext';st.textContent='.uw-ext{display:inline-block;margin-left:.25em;font-size:.85em;line-height:1;text-decoration:none;opacity:.75}.uw-sr{position:absolute!important;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}';document.head.appendChild(st)}
scan(document.body);new MutationObserver(function(m){m.forEach(function(x){[].forEach.call(x.addedNodes,scan)})}).observe(document.body,{childList:true,subtree:true});
})();
"""

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

PROG_LABELS = {
    "HORIZON": "Horizon Europe", "DIGITAL": "Digital Europe", "EDF": "European Defence Fund",
    "CREA": "Creative Europe", "CERV": "CERV", "I3": "Interregional Innovation Investments (I3)",
    "EUBA": "EU Bodies & Agencies", "EURATOM": "Euratom", "ERASMUS": "Erasmus+", "LIFE": "LIFE",
    "CEF": "Connecting Europe Facility", "EU4H": "EU4Health", "SMP": "Single Market Programme",
    "PPPA": "Pilot Projects & Preparatory Actions", "ISF": "Internal Security Fund", "JUST": "Justice",
    "SOCPL": "Social Prerogative", "NDICI": "Global Europe (NDICI)", "JTM": "Just Transition Mechanism",
    "IMREG": "Single Market – Internal Market", "IMCAP": "Customs Control Equipment", "HUMA": "Humanitarian Aid",
    "COSME": "COSME", "AGRIP": "Agricultural Promotion", "EMFAF": "EMFAF", "RFCS": "Research Fund for Coal & Steel",
    "INNOVFUND": "Innovation Fund", "UCPM": "Union Civil Protection Mechanism", "ESF": "ESF+", "EUAF": "EU Anti-Fraud",
}


TAXONOMY = json.loads((Path(__file__).resolve().parent.parent / "content" / "taxonomy.json").read_text(encoding="utf-8"))
NETWORK_HTML = "".join(f'<a href="{u}"{" aria-current=page" if t == "EU calls" else ""}>{t}</a>' for t, u in TAXONOMY["network"])
EVENTS_URL, NEWS_URL = "https://events.ullswaterinvestments.com", "https://news.ullswaterinvestments.com"


_LIVE = {}


def _live_sections():
    """Programme keys with upcoming events and news categories that have a page (only link to pages that exist)."""
    if not _LIVE:
        import urllib.request
        _LIVE["events"], _LIVE["news"] = set(), set()
        try:
            req = urllib.request.Request(EVENTS_URL + "/events.json", headers={"User-Agent": "UllswaterCallsBot/1.0"})
            _LIVE["events"] = {e.get("programme") for e in json.load(urllib.request.urlopen(req, timeout=30)).get("events", [])}
            req = urllib.request.Request(NEWS_URL + "/sitemap.xml", headers={"User-Agent": "UllswaterCallsBot/1.0"})
            sm = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
            _LIVE["news"] = set(re.findall(re.escape(NEWS_URL) + r"/([a-z-]+)/</loc>", sm))
        except Exception as e:
            print(f"  events/news sections unavailable: {e}")
    return _LIVE


def theme_links(tslug):
    """Links from a theme page to the matching events and news sections (shared taxonomy)."""
    t, live = TAXONOMY["themes"].get(tslug, {}), _live_sections()
    li = [f'<a class="btn ghost" href="{EVENTS_URL}/programme/{k}/">Events for this area →</a>' for k in t.get("events", []) if k in live["events"]][:1]
    li += [f'<a class="btn ghost" href="{NEWS_URL}/{k}/">News for this area →</a>' for k in t.get("news", []) if k in live["news"]][:1]
    return f'<div class="actions">{"".join(li)}</div>' if li else ""


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def label(code, full):
    return PROG_LABELS.get(code) or re.sub(r"\s*\([^)]*\)\s*$", "", full or code) or code


def money(v):
    if not v:
        return ""
    if v >= 1_000_000:
        x = v / 1_000_000
        return f"€{x:.1f}M".replace(".0M", "M")
    return f"€{round(v / 1000):,}k"


def fmt_date(iso):
    d = date.fromisoformat(iso)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def card(c):
    kind = "Cascade funding" if c["kind"] == "cascade" else "EU call"
    st_tag = '<span class="tag open">Open</span>' if c["status"] == "open" else '<span class="tag fc">Forthcoming</span>'
    if c["deadline"]:
        d = date.fromisoformat(c["deadline"])
        dbox = f'<div class="date"><small>Deadline</small><b>{d.day}</b><i>{MONTHS[d.month-1]} {d.year}</i></div>'
    else:
        dbox = '<div class="date tbc"><small>Deadline</small><b>TBC</b></div>'
    facts = []
    if c["status"] == "forthcoming" and c.get("opening"):
        facts.append(f"<span>Opens <b>{fmt_date(c['opening'])}</b></span>")
    if c.get("budget"):
        facts.append(f"<span>Budget <b>{money(c['budget'])}</b></span>")
    if c.get("deadlineModel"):
        facts.append(f"<span>{escape(c['deadlineModel'].replace('-', ' ').capitalize())}</span>")
    if c.get("actions"):
        facts.append(f"<span>{escape(', '.join(a.split(' ', 1)[-1] if ' ' in a else a for a in c['actions'][:2]))}</span>")
    ident = c["id"] if c["kind"] == "topic" else c.get("call", "")
    return (
        f'<article class="call" data-status="{c["status"]}" data-prog="{escape(c["programme"])}" data-kind="{c["kind"]}" '
        f'data-deadline="{c["deadline"] or ""}">{dbox}<div>'
        f'<div class="meta">{st_tag}<span class="tag left" hidden></span><a class="tag" href="/programme/{slug(c["programme"])}/">{escape(label(c["programme"], c["programmeName"]))}</a>'
        + (f'<span class="tag cas">{kind}</span>' if c["kind"] == "cascade" else "")
        + f'<span class="code">{escape(ident)}</span></div>'
        f'<h3><a href="/call/{slug(c["id"])}/">{escape(c["title"])}</a></h3>'
        + (f"<p>{escape(c['summary'][:300] + ('…' if len(c['summary']) > 300 and not c['summary'].endswith('…') else ''))}</p>" if c.get("summary") else "")
        + (f'<div class="facts">{"".join(facts)}</div>' if facts else "")
        + f'<div class="links"><a class="more" href="/call/{slug(c["id"])}/">Details &amp; potential partners →</a><a class="more ext" href="{escape(c["url"])}" target="_blank" rel="noopener">EU portal ↗</a></div>'
        + (f'<span hidden>{escape(" ".join(c.get("tags") or []) + " " + (c.get("callTitle") or ""))}</span>')
        + "</div></article>"
    )


def page(title, desc, path, body, jsonld=None):
    canon = BASE + path
    ld = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><meta name="description" content="{escape(desc)}"><link rel="canonical" href="{canon}">
<meta property="og:type" content="website"><meta property="og:title" content="{escape(title)}"><meta property="og:description" content="{escape(desc)}"><meta property="og:url" content="{canon}"><meta property="og:site_name" content="Ullswater Investments · EU Funding Advisors">
<meta name="twitter:card" content="summary">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='12' fill='%23233567'/%3E%3Ctext x='32' y='44' font-family='Arial' font-weight='700' font-size='34' text-anchor='middle' fill='%23c9a646'%3EU%3C/text%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<link rel="alternate" type="application/json" href="/data/calls.json" title="EU funding calls (JSON)">
<style>{CSS}</style>{ld}</head><body>
<header class="site"><div class="wrap"><a class="brand" href="/">Ullswater Investments <span>· EU Funding Calls</span></a>
<nav class="top-links" aria-label="Ullswater Investments sites">{NETWORK_HTML}</nav></div></header>
{body}
<footer class="site"><div class="wrap"><div><strong>Ullswater Investments · EU Funding Advisors</strong><br>Madrid: Calle Ramírez de Arellano 17, 28043 Madrid · Brussels: Square de Meeûs 37, 1000 Brussels</div>
<div>Data: <a href="https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/home" rel="noopener">EU Funding &amp; Tenders Portal</a> (European Commission), refreshed weekly.<br>Always check the official call page before applying.</div>
<div><a href="{MAIN}">ullswaterinvestments.com</a> · <a href="/data/calls.json">JSON</a> · © {date.today().year}</div></div></footer>
<script src="/assets/app.js" defer></script>{ai_pages.CHAT}</body></html>"""


def nav(progs, current=None):
    links = [f'<a href="/"{" aria-current=page" if current == "all" else ""}>All calls</a>',
             f'<a href="/closing-soon/"{" aria-current=page" if current == "soon" else ""}>Closing soon</a>',
             f'<a href="/theme/"{" aria-current=page" if current == "theme" else ""}>Themes</a>',
             f'<a href="/finder/"{" aria-current=page" if current == "finder" else ""}>Fund Finder</a>',
             f'<a href="/review/"{" aria-current=page" if current == "review" else ""}>AI pre-check</a>',
             f'<a href="/spain/"{" aria-current=page" if current == "spain" else ""}>Spain</a>',
             f'<a href="/partners/"{" aria-current=page" if current == "board" else ""}>Partner board</a>',
             f'<a href="/directory/"{" aria-current=page" if current == "directory" else ""}>Directory</a>',
             f'<a href="/tools/"{" aria-current=page" if current == "tools" else ""}>Tools</a>',
             f'<a href="/alerts/"{" aria-current=page" if current == "alerts" else ""}>🔔 Alerts</a>']
    for code, n in progs[:9]:
        links.append(f'<a href="/programme/{slug(code)}/"{" aria-current=page" if current == code else ""}>{escape(label(code, ""))}</a>')
    return f'<nav class="cats" aria-label="Programmes"><div class="wrap">{"".join(links)}</div></nav>'


def filters(progs, show_prog=True, default_status="open", default_dl=""):
    popts = "".join(f'<option value="{escape(c)}">{escape(label(c, ""))} ({n})</option>' for c, n in progs)
    prog = f'<label>Programme<select id="f-prog"><option value="">All programmes</option>{popts}</select></label>' if show_prog else ""
    def sel(v, cur):
        return " selected" if v == cur else ""
    return f"""<div class="filters" role="search"><div class="wrap">
<label class="q">Search<input id="f-q" type="search" placeholder="Keyword, topic ID, e.g. AI, hydrogen, HORIZON-CL4…" autocomplete="off"></label>
<label>Status<select id="f-status"><option value="open"{sel('open',default_status)}>Open now</option><option value="forthcoming"{sel('forthcoming',default_status)}>Forthcoming</option><option value="all"{sel('all',default_status)}>Open + forthcoming</option></select></label>
{prog}<label>Deadline<select id="f-dl"><option value="">Any deadline</option><option value="15"{sel('15',default_dl)}>Within 15 days</option><option value="30"{sel('30',default_dl)}>Within 30 days</option><option value="60">Within 60 days</option><option value="90">Within 90 days</option><option value="180">Within 6 months</option></select></label>
<label>Type<select id="f-type"><option value="">All types</option><option value="topic">EU calls (topics)</option><option value="cascade">Cascade funding</option></select></label>
</div></div>"""


def listing(calls):
    return (f'<div class="wrap"><div class="resbar"><span><strong id="count">{len(calls)}</strong> funding opportunities match your filters</span>'
            f'<button class="linkbtn" id="reset" type="button">Reset filters</button></div><div id="list">'
            + "".join(card(c) for c in calls)
            + '</div><div class="empty" id="empty" hidden>No calls match these filters. Try “Open + forthcoming” or a broader keyword.</div>'
            f'<div class="cta"><div><strong>Not sure which call fits your project?</strong><p>Ullswater Investments matches your company with the right EU instrument and builds the proposal with you.</p></div><a class="btn" href="{MAIN}/eu-fund-matching">EU Fund Matching →</a></div>')


def itemlist(calls, name):
    return {"@context": "https://schema.org", "@type": "CollectionPage", "name": name, "url": BASE + "/",
            "publisher": {"@type": "Organization", "name": "Ullswater Investments S.L.", "url": MAIN},
            "mainEntity": {"@type": "ItemList", "numberOfItems": len(calls), "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": c["title"], "url": c["url"]} for i, c in enumerate(calls[:60])]}}


def main():
    data = json.loads((SITE / "data" / "calls.json").read_text(encoding="utf-8"))
    calls, stats = data["calls"], data["stats"]
    import enrich
    enrich.apply(calls)
    upd = datetime.fromisoformat(stats["updated"]).date()
    upd_s = fmt_date(upd.isoformat())
    open_calls = [c for c in calls if c["status"] == "open"]
    counts = {}
    for c in calls:
        counts[c["programme"]] = counts.get(c["programme"], 0) + 1
    progs = sorted(counts.items(), key=lambda kv: -kv[1])
    import shutil
    for old in ("call", "programme", "closing-soon", "partners", "finder", "tools", "alerts", "directory", "spain", "review", "theme", "data/t"):  # drop pages of calls that have closed
        shutil.rmtree(SITE / old, ignore_errors=True)
    (SITE / "assets").mkdir(parents=True, exist_ok=True)
    (SITE / "assets" / "app.js").write_text(JS, encoding="utf-8")

    chips = "".join(f'<a href="/programme/{slug(c)}/">{escape(label(c, ""))}<b>{n}</b></a>' for c, n in progs)
    hero = f"""<main><section class="hero"><div class="wrap"><p class="kicker">EU Funding Calls · updated {upd_s}</p>
<h1>Open EU funding calls 2026–2027</h1>
<p class="lead">Every open and forthcoming EU grant and cascade-funding call from the European Commission's Funding &amp; Tenders Portal, in one searchable list. Filter by programme, deadline or keyword. Refreshed automatically every week.</p>
<ul class="stats"><li><strong>{stats['open']}</strong>calls open now</li><li><strong>{stats['forthcoming']}</strong>forthcoming calls</li><li><strong>{stats['closingIn30Days']}</strong>closing in 30 days</li><li><strong>{stats['programmes']}</strong>EU programmes</li></ul>
<div class="actions"><a class="btn" href="{MAIN}/eu-fund-matching">Find the right call for my project</a><a class="btn ghost" href="/closing-soon/">Deadlines in the next 30 days</a></div>
<nav class="chips" aria-label="Programmes">{chips}</nav></div></section>"""
    about = """<section class="about"><h2>About this list</h2><p>The list is built from the European Commission's public Funding &amp; Tenders Portal search service and refreshed every Monday. Calls whose deadlines have passed are removed automatically, even if the portal still flags them as open. “Open” means you can submit now; “forthcoming” means the call has been announced but is not yet open. Budgets are the indicative topic budgets published by the Commission. Always read the official call documents before applying.</p></section></div></main>"""

    title = f"Open EU funding calls {upd.year}–{upd.year + 1}: {stats['open']} open, {stats['forthcoming']} forthcoming | Ullswater Investments"
    desc = f"Search {stats['total']} open and forthcoming EU funding calls (Horizon Europe, Digital Europe, EDF, LIFE, EU4Health, cascade funding). Deadlines and budgets, updated {upd_s}."
    (SITE / "index.html").write_text(page(title, desc, "/", nav(progs, "all") + hero + filters(progs) + listing(calls) + about, itemlist(open_calls, "Open EU funding calls")), encoding="utf-8")

    # Closing soon
    soon = [c for c in open_calls if c["deadline"] and (date.fromisoformat(c["deadline"]) - upd).days <= 30]
    h = f"""<main><section class="hero"><div class="wrap"><div class="crumbs"><a href="/">All calls</a> › Closing soon</div><p class="kicker">Deadlines · updated {upd_s}</p>
<h1>EU funding calls closing in the next 30 days</h1><p class="lead">{len(soon)} open EU calls have a deadline within 30 days. If you want to apply, start now.</p></div></section>"""
    (SITE / "closing-soon").mkdir(exist_ok=True)
    (SITE / "closing-soon" / "index.html").write_text(page(f"EU funding calls closing in the next 30 days ({len(soon)}) | Ullswater Investments",
        f"{len(soon)} EU funding calls with deadlines in the next 30 days. Updated {upd_s}.", "/closing-soon/",
        nav(progs, "soon") + h + filters(progs, default_dl="30") + listing(open_calls) + about, itemlist(soon, "EU calls closing soon")), encoding="utf-8")

    # Programme pages
    urls = ["/", "/closing-soon/"]
    for code, n in progs:
        pc = [c for c in calls if c["programme"] == code]
        po = sum(1 for c in pc if c["status"] == "open")
        name = label(code, pc[0]["programmeName"])
        full = pc[0]["programmeName"]
        path = f"/programme/{slug(code)}/"
        h = f"""<main><section class="hero"><div class="wrap"><div class="crumbs"><a href="/">All calls</a> › {escape(name)}</div><p class="kicker">{escape(full)} · updated {upd_s}</p>
<h1>{escape(name)} calls: open and forthcoming</h1><p class="lead">{po} open and {n - po} forthcoming {escape(name)} funding opportunities from the EU Funding &amp; Tenders Portal, with deadlines and budgets.</p></div></section>"""
        d = SITE / "programme" / slug(code)
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page(f"{name} calls {upd.year}–{upd.year + 1}: {po} open, {n - po} forthcoming | Ullswater Investments",
            f"All open and forthcoming {name} calls with deadlines and budgets. Updated {upd_s}.", path,
            nav(progs, code) + h + filters(progs, show_prog=False, default_status="all" if po == 0 else "open") + listing(pc) + about,
            itemlist(pc, f"{name} calls")), encoding="utf-8")
        urls.append(path)

    # Thematic pages (replace the old www.ullswaterinvestments.com/calls/* pages)
    themes = theme_pages.build(calls, upd.year)
    tiles = ""
    for tslug, ttitle, short, intro, old, tc in themes:
        to = sum(1 for c in tc if c["status"] == "open")
        tiles += f'<a class="tile" href="/theme/{tslug}/"><b>{escape(short)}</b><span>{len(tc)} calls · {to} open</span><small>{escape(intro)}</small></a>'
        h = f"""<main><section class="hero"><div class="wrap"><div class="crumbs"><a href="/">All calls</a> › <a href="/theme/">Themes</a> › {escape(short)}</div><p class="kicker">Theme · updated {upd_s}</p>
<h1>{escape(ttitle)}</h1><p class="lead">{escape(intro)} {to} open and {len(tc) - to} forthcoming, from the EU Funding &amp; Tenders Portal.</p>{theme_links(tslug)}</div></section>"""
        d = SITE / "theme" / tslug
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page(f"{ttitle}: {to} open, {len(tc) - to} forthcoming | Ullswater Investments",
            f"{intro} Deadlines and budgets, updated {upd_s}.", f"/theme/{tslug}/",
            nav(progs, "theme") + h + filters(progs, default_status="all" if to == 0 else "open") + listing(tc) + about, itemlist(tc, ttitle)), encoding="utf-8")
        urls.append(f"/theme/{tslug}/")
    th = f"""<main><section class="hero"><div class="wrap"><div class="crumbs"><a href="/">All calls</a> › Themes</div><p class="kicker">Themes · updated {upd_s}</p>
<h1>EU funding calls by theme</h1><p class="lead">Browse open and forthcoming EU calls by Horizon Europe cluster, technology or instrument.</p></div></section>
<div class="wrap"><section class="sec"><div class="tiles">{tiles}</div></section></div></main>"""
    (SITE / "theme" / "index.html").write_text(page("EU funding calls by theme | Ullswater Investments",
        "Open EU calls grouped by theme: AI, EIC, health, security, digital, climate and energy, food, missions, science, defence, cascade funding.", "/theme/",
        nav(progs, "theme") + th), encoding="utf-8")
    urls.append("/theme/")
    (SITE / "data" / "taxonomy.json").write_text(json.dumps(TAXONOMY, ensure_ascii=False, indent=1), encoding="utf-8")
    (SITE / "data" / "themes.json").write_text(json.dumps([{"slug": t[0], "title": t[1], "short": t[2], "old": t[4], "count": len(t[5]),
        "open": sum(1 for c in t[5] if c["status"] == "open")} for t in themes], ensure_ascii=False), encoding="utf-8")

    # Per-call topic text for the AI Worker
    ttext = json.loads((ROOT / "data" / "topic_text.json").read_text(encoding="utf-8")) if (ROOT / "data" / "topic_text.json").exists() else {}
    (SITE / "data" / "t").mkdir(parents=True, exist_ok=True)
    for c in calls:
        (SITE / "data" / "t" / f"{slug(c['id'])}.json").write_text(json.dumps({"id": c["id"], "title": c["title"], "url": c["url"], "deadline": c.get("deadline"),
            "actions": c.get("actions"), "text": ttext.get(c["id"], c.get("summary", ""))}, ensure_ascii=False), encoding="utf-8")
    # Per-call pages with "Find partners"
    pfile = ROOT / "data" / "partners.json"
    partners = json.loads(pfile.read_text(encoding="utf-8")) if pfile.exists() else {}
    events = call_pages.load_events()
    board = call_pages.load_board()
    directory = extra_pages.load_directory()
    dir_by_profile, dir_by_call = extra_pages.match_directory(directory, calls)
    for c in calls:
        path, ics, html_ = call_pages.render_call(c, partners.get(c["id"]), events, page, nav(progs), fmt_date, money, label, slug, MAIN, board, dir_by_call.get(c["id"]))
        d = SITE / path.strip("/")
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(html_, encoding="utf-8")
        if ics:
            (d / "deadline.ics").write_text(ics, encoding="utf-8")
        urls.append(path)
    # Partner board page
    by_id = {c["id"].upper(): c for c in calls}
    live_reqs = [r for k, rs in board.items() if k in by_id for r in rs]
    cards = call_pages.board_cards(sorted(live_reqs, key=lambda r: r.get("submitted", ""), reverse=True), True, by_id)
    pb = f"""<main><section class="hero"><div class="wrap"><div class="crumbs"><a href="/">All calls</a> › Partner board</div><p class="kicker">Partner board · updated {upd_s}</p>
<h1>EU call partner board</h1><p class="lead">Organisations looking for partners, or offering to join a consortium, for open EU calls. Every request is reviewed by Ullswater Investments before it is published, and contact goes through us.</p>
<div class="actions"><a class="btn" href="{call_pages.form_link()}" target="_blank" rel="noopener">Post a partner request</a></div></div></section>
<div class="wrap"><section class="sec">{f'<div class="grid3">{cards}</div>' if cards else '<div class="empty">No partner requests published yet. Be the first: post what you are looking for and we will match you with organisations from our network and from EU project data.</div>'}</section></div></main>"""
    (SITE / "partners").mkdir(exist_ok=True)
    (SITE / "partners" / "index.html").write_text(page(f"EU call partner board: find consortium partners ({len(live_reqs)} requests) | Ullswater Investments",
        "Partner requests and offers for open EU funding calls, reviewed by Ullswater Investments.", "/partners/", nav(progs, "board") + pb), encoding="utf-8")
    urls.append("/partners/")
    for sub, cur, ttl, dsc, body in [
        ("finder", "finder", "Fund Finder: which EU call fits your project? | Ullswater Investments",
         "Describe your project and get a ranked shortlist of matching open EU calls, with the reasons for each match.", finder_page.finder_html(MAIN)),
        ("tools", "tools", "Horizon Europe budget calculator and consortium checker | Ullswater Investments",
         "Free tools: estimate your Horizon Europe budget and EU grant, and check consortium eligibility with the official list of associated countries.", tools_pages.tools_html(MAIN))]:
        (SITE / sub).mkdir(exist_ok=True)
        (SITE / sub / "index.html").write_text(page(ttl, dsc, f"/{sub}/", nav(progs, cur) + body), encoding="utf-8")
        urls.append(f"/{sub}/")
    spain_file = SITE / "data" / "spain.json"
    spain = json.loads(spain_file.read_text(encoding="utf-8")) if spain_file.exists() else {"calls": [], "updated": upd.isoformat()}
    for sub, cur, ttl, dsc, body in [
        ("review", "review", "AI pre-check: test your project idea against an EU call | Ullswater Investments",
         "Free AI pre-check of your project idea against an EU call: fit, indicative scores, gaps and partners needed.", ai_pages.review_html(calls)),
        ("alerts", "alerts", "Free EU funding alerts by email | Ullswater Investments", "Weekly email with new EU calls for your keywords, upcoming deadlines and partner requests.", extra_pages.alerts_html()),
        ("directory", "directory", f"Directory of organisations open to EU consortia ({len(directory)}) | Ullswater Investments",
         "Organisations looking to join or lead EU projects, matched with open calls by Ullswater Investments.", extra_pages.directory_html(directory, dir_by_profile, slug)),
        ("spain", "spain", f"Spanish R&D, innovation and industry calls ({len(spain['calls'])} open or upcoming) | Ullswater Investments",
         "Competitive national and regional calls in Spain for R&D&I and industry, from the official BDNS, updated daily.", extra_pages.spain_html(spain, money, fmt_date))]:
        (SITE / sub).mkdir(exist_ok=True)
        (SITE / sub / "index.html").write_text(page(ttl, dsc, f"/{sub}/", nav(progs, cur) + body), encoding="utf-8")
        urls.append(f"/{sub}/")
    print(f"  partner board: {len(live_reqs)} approved requests")
    print(f"  call pages: {len(calls)} ({sum(1 for c in calls if call_pages.partners_enabled(c, partners.get(c['id'])))} with track-record partners), events: {len(events)}")

    (SITE / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{BASE}{u}</loc><lastmod>{upd.isoformat()}</lastmod><changefreq>weekly</changefreq></url>" for u in urls) + "</urlset>\n", encoding="utf-8")
    ai_bots = ['Googlebot', 'Google-Extended', 'Bingbot', 'GPTBot', 'OAI-SearchBot', 'ChatGPT-User', 'ClaudeBot', 'Claude-SearchBot', 'Claude-User', 'PerplexityBot', 'Perplexity-User', 'Applebot', 'Applebot-Extended', 'DuckAssistBot', 'MistralAI-User', 'CCBot']
    (SITE / "robots.txt").write_text("# calls.ullswaterinvestments.com: public EU funding data, open to search engines and AI assistants.\n"
        + "".join(f"User-agent: {b}\nAllow: /\n\n" for b in ai_bots) + f"User-agent: *\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n", encoding="utf-8")
    key = (ROOT / "content" / "indexnow_key.txt").read_text().strip()
    (SITE / f"{key}.txt").write_text(key, encoding="utf-8")
    (SITE / "llms.txt").write_text(f"""# EU Funding Calls · Ullswater Investments

> Every open and forthcoming EU funding call (Horizon Europe, Digital Europe, EDF, LIFE, EU4Health, cascade funding and more), refreshed daily from the European Commission's Funding & Tenders Portal. Run by Ullswater Investments S.L., EU funding advisors with offices in Madrid and Brussels ({MAIN}/).

## Data
- [All calls as JSON]({BASE}/data/calls.json): id, title, programme, status, opening, deadline, budget, URL
- [Summary statistics]({BASE}/data/stats.json)
- [Spanish national and regional calls (BDNS) as JSON]({BASE}/data/spain.json)

## Pages
- [All open and forthcoming EU calls]({BASE}/)
- [Calls closing in the next 30 days]({BASE}/closing-soon/)
- [Calls by theme]({BASE}/theme/): """ + ", ".join(f"[{t[2]}]({BASE}/theme/{t[0]}/)" for t in themes) + f"""
- [Fund Finder: match a project description to calls]({BASE}/finder/)
- [AI pre-check of a project idea against a call]({BASE}/review/)
- [Partner board]({BASE}/partners/) · [Directory]({BASE}/directory/) · [Tools]({BASE}/tools/)
- [Spain: national and regional R&D and industry calls]({BASE}/spain/)

## About
- [Ullswater Investments]({MAIN}/about/) · [EU Fund Matching]({MAIN}/eu-fund-matching/) · [EU Funding News](https://news.ullswaterinvestments.com/)
""", encoding="utf-8")
    (SITE / "CNAME").write_text("calls.ullswaterinvestments.com\n", encoding="utf-8")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    (SITE / "404.html").write_text(page("Page not found | Ullswater Investments EU Funding Calls", "Page not found.", "/404.html",
        '<main><section class="hero"><div class="wrap"><h1>Page not found</h1><p class="lead">The call you are looking for may have closed.</p><div class="actions"><a class="btn" href="/">See all open calls</a></div></div></section></main>'), encoding="utf-8")
    import extlinks; extlinks.run(SITE)  # external links open in a new tab (shared rule, see scripts/extlinks.py)
    print(f"Built {len(urls)} pages, {len(calls)} calls")


if __name__ == "__main__":
    main()
