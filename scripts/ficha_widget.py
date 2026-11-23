"""Front-end of the email-verified PDF factsheet download (written to site/assets/ficha.js by build_site.py).

Any element with data-ficha="<call id>" (and optional data-title, data-lang="es|en") becomes a download button.
Buttons whose factsheet does not exist in /fichas/index.json are hidden.
"""
WORKER = "https://ullswater-fichas.emilio-mulet-b52.workers.dev"
PRIVACY = "https://www.ullswaterinvestments.com/privacy/"


def button(call_id, title, lang="en", cls="btn ghost"):
    from html import escape
    label = "📄 Descargar ficha PDF" if lang == "es" else "📄 Download factsheet (PDF)"
    return (f'<button type="button" class="{cls}" data-ficha="{escape(call_id)}" data-title="{escape(title[:220])}" '
            f'data-lang="{lang}" hidden>{label}</button>')


JS = r"""(function(){
var W='__WORKER__',PRIV='__PRIVACY__',K='ullFichaAccess';
var T={en:{h:'Download the PDF factsheet',p:'Enter your email. We will send you a link to confirm it is yours; the download starts when you open it. You only need to do this once per browser.',
 e:'Your email',a:'I accept the <a href="'+PRIV+'" target="_blank" rel="noopener">privacy policy</a>. Ullswater Investments uses my email to verify it and send me the factsheet.',
 m:'I also want to receive news on EU and Spanish funding calls (optional, you can unsubscribe at any time).',s:'Send me the link',c:'Cancel',
 ok:'Check your inbox',ok2:'We have sent a confirmation link to <b>{e}</b>. It is valid for 24 hours. If you cannot find it, look in your spam folder.',
 err:{email:'Please enter a valid email address.',privacy:'Please accept the privacy policy to continue.',rate:'Too many requests. Please try again later.',mail:'We could not send the email. Please check the address or try again later.',unknown_ficha:'This factsheet is not available right now.',_:'Something went wrong. Please try again.'},
 v:'Email verified. Your factsheet is downloading…',as:'Downloading as {e}',sw:'Use another email'},
 es:{h:'Descargar la ficha en PDF',p:'Introduzca su email. Le enviaremos un enlace para confirmar que es suyo; la descarga empieza al abrirlo. Solo tendrá que hacerlo una vez en este navegador.',
 e:'Su email',a:'Acepto la <a href="'+PRIV+'" target="_blank" rel="noopener">política de privacidad</a>. Ullswater Investments usa mi email para verificarlo y enviarme la ficha.',
 m:'Quiero recibir también novedades sobre convocatorias y ayudas (opcional, puede darse de baja cuando quiera).',s:'Enviarme el enlace',c:'Cancelar',
 ok:'Revise su correo',ok2:'Hemos enviado un enlace de confirmación a <b>{e}</b>. Es válido durante 24 horas. Si no lo encuentra, mire en la carpeta de spam.',
 err:{email:'Introduzca un email válido.',privacy:'Debe aceptar la política de privacidad para continuar.',rate:'Demasiadas solicitudes. Inténtelo más tarde.',mail:'No hemos podido enviar el email. Revise la dirección o inténtelo más tarde.',unknown_ficha:'Esta ficha no está disponible ahora mismo.',_:'Algo ha fallado. Inténtelo de nuevo.'},
 v:'Email verificado. Su ficha se está descargando…',as:'Descargando como {e}',sw:'Usar otro email'}};
var css='.uf-bg{position:fixed;inset:0;background:rgba(15,23,42,.55);display:flex;align-items:center;justify-content:center;z-index:9999;padding:16px}'+
'.uf{background:#fff;border-radius:12px;max-width:460px;width:100%;padding:26px 26px 22px;border-top:5px solid #c9a646;font-family:Inter,Arial,sans-serif;color:#1f2937;box-shadow:0 20px 50px rgba(0,0,0,.25)}'+
'.uf h3{margin:0 0 6px;color:#233567;font-size:19px}.uf .t{font-size:13px;color:#475467;margin:0 0 14px}.uf .n{font-size:13px;font-weight:600;color:#233567;margin:0 0 12px}'+
'.uf input[type=email]{width:100%;box-sizing:border-box;padding:11px 12px;border:1px solid #d0d5dd;border-radius:8px;font-size:15px;margin-bottom:12px}'+
'.uf label.c{display:flex;gap:8px;font-size:12.5px;color:#344054;margin-bottom:10px;line-height:1.4}.uf label.c input{margin-top:2px;flex:none}.uf a{color:#233567}'+
'.uf .r{display:flex;gap:10px;justify-content:flex-end;margin-top:14px}.uf button{border:0;border-radius:8px;padding:10px 16px;font-weight:600;font-size:14px;cursor:pointer}'+
'.uf .go{background:#233567;color:#fff}.uf .go[disabled]{opacity:.6}.uf .no{background:#f2f4f7;color:#344054}.uf .er{color:#b42318;font-size:13px;margin:6px 0 0;min-height:18px}'+
'button.ficha{background:none;border:0;padding:0;margin-left:16px;font:inherit;font-weight:600;color:#233567;cursor:pointer}button.ficha:hover{text-decoration:underline}'+
'.uf .hp{position:absolute;left:-5000px}.uf-toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#233567;color:#fff;padding:12px 18px;border-radius:8px;font:600 14px Inter,Arial,sans-serif;z-index:9999;box-shadow:0 8px 24px rgba(0,0,0,.25)}';
function el(h){var d=document.createElement('div');d.innerHTML=h;return d.firstChild}
function toast(m){var t=el('<div class="uf-toast"></div>');t.textContent=m;document.body.appendChild(t);setTimeout(function(){t.remove()},6000)}
function get(){try{return localStorage.getItem(K)}catch(e){return null}}
function put(v){try{v?localStorage.setItem(K,v):localStorage.removeItem(K)}catch(e){}}
function download(id,a){window.location.href=W+'/pdf?id='+encodeURIComponent(id)+'&a='+encodeURIComponent(a)}
function modal(b,known){
 var L=T[b.dataset.lang==='es'?'es':'en'],id=b.dataset.ficha;
 var m=el('<div class="uf-bg" role="dialog" aria-modal="true"><form class="uf" novalidate><h3></h3>'+(known?'<p class="n"></p>':'')+'<p class="t"></p>'+
  '<input type="email" name="email" autocomplete="email" required><input class="hp" name="website" tabindex="-1" autocomplete="off">'+
  '<label class="c"><input type="checkbox" name="privacy"><span class="pa"></span></label><label class="c"><input type="checkbox" name="marketing"><span class="ma"></span></label>'+
  '<p class="er" aria-live="polite"></p><div class="r"><button type="button" class="no"></button><button class="go"></button></div></form></div>');
 var f=m.querySelector('form');f.querySelector('h3').textContent=L.h;f.querySelector('.t').textContent=L.p;f.email.placeholder=L.e;
 f.querySelector('.pa').innerHTML=L.a;f.querySelector('.ma').textContent=L.m;f.querySelector('.go').textContent=L.s;f.querySelector('.no').textContent=L.c;
 function close(){m.remove()} m.addEventListener('click',function(e){if(e.target===m)close()});f.querySelector('.no').onclick=close;
 document.addEventListener('keydown',function k(e){if(e.key==='Escape'){close();document.removeEventListener('keydown',k)}});
 f.onsubmit=function(e){e.preventDefault();var er=f.querySelector('.er'),go=f.querySelector('.go'),em=f.email.value.trim();er.textContent='';
  if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(em)){er.textContent=L.err.email;return}
  if(!f.privacy.checked){er.textContent=L.err.privacy;return}
  go.disabled=true;
  fetch(W+'/request',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:em,id:id,title:b.dataset.title||'',lang:b.dataset.lang==='es'?'es':'en',
   privacy:true,marketing:f.marketing.checked,page:location.href.split('#')[0],hp:f.website.value})})
  .then(function(r){return r.json().then(function(j){return{ok:r.ok,j:j}})})
  .then(function(x){if(x.ok&&x.j.ok){f.innerHTML='<h3></h3><p class="t"></p><div class="r"><button type="button" class="go">OK</button></div>';
    f.querySelector('h3').textContent=L.ok;f.querySelector('.t').innerHTML=L.ok2.replace('{e}',em.replace(/[<>&"]/g,''));f.querySelector('.go').onclick=close}
   else{er.textContent=L.err[x.j.error]||L.err._;go.disabled=false}})
  .catch(function(){er.textContent=L.err._;go.disabled=false})};
 f.privacy.onchange=function(){f.querySelector('.er').textContent=''};
 document.body.appendChild(m);f.email.focus();
}
function click(b){var a=get();if(!a){modal(b);return}
 fetch(W+'/status?a='+encodeURIComponent(a)).then(function(r){return r.json()}).then(function(s){
  if(s.valid){var L=T[b.dataset.lang==='es'?'es':'en'];toast(L.as.replace('{e}',s.email));download(b.dataset.ficha,a)}else{put(null);modal(b)}})
 .catch(function(){download(b.dataset.ficha,a)})}
function init(){
 var st=document.createElement('style');st.textContent=css;document.head.appendChild(st);
 var h=location.hash.match(/ficha=([^&]+)&fid=([^&]+)/);
 if(h){var a=decodeURIComponent(h[1]),id=decodeURIComponent(h[2]);put(a);history.replaceState(null,'',location.pathname+location.search);
  var bb=document.querySelector('[data-ficha]');toast(T[bb&&bb.dataset.lang==='es'?'es':(document.documentElement.lang==='es'?'es':'en')].v);setTimeout(function(){download(id,a)},600)}
 var bs=[].slice.call(document.querySelectorAll('[data-ficha]'));if(!bs.length)return;
 fetch('/fichas/index.json',{cache:'no-cache'}).then(function(r){return r.ok?r.json():{fichas:{}}}).then(function(ix){
  bs.forEach(function(b){if(ix.fichas&&ix.fichas[b.dataset.ficha]){b.hidden=false;b.addEventListener('click',function(e){e.preventDefault();click(b)})}})}).catch(function(){});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
""".replace("__WORKER__", WORKER).replace("__PRIVACY__", PRIVACY)
