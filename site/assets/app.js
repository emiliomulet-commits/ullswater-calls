(function(){
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
