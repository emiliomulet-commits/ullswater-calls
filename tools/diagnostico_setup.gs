/**
 * Ullswater · Diagnósticos gratuitos de licitaciones (Google Apps Script) — Nov 2026.
 * Recibe del Worker (POST /diagnostico, secreto DIAG_WEBHOOK) cada diagnóstico o reserva de la web de licitaciones,
 * lo guarda en una hoja privada y envía un email a tenders@ (responder = la empresa).
 * Uso: crea el proyecto, ejecuta setupDiagnosticos() una vez, publica como aplicación web
 * (Ejecutar como: yo · Acceso: cualquiera) y guarda la URL en el secreto DIAG_WEBHOOK del Worker
 * y el TOKEN del log en el secreto DIAG_TOKEN.
 */
var DIAG_EMAILS = 'tenders@ullswaterinvestments.com';

function setupDiagnosticos() {
  var ss = SpreadsheetApp.create('Ullswater · Diagnósticos de licitaciones (privado)');
  ss.getSheets()[0].appendRow(['Fecha', 'Tipo', 'Licitación', 'Expediente', 'Nombre', 'Empresa', 'Email', 'CIF', 'Veredicto',
    'Puntuación', 'Probabilidad', 'Lotes', 'Comunicaciones', 'Guardar perfil', 'Página']);
  var token = Utilities.getUuid();
  PropertiesService.getScriptProperties().setProperties({SHEET: ss.getId(), TOKEN: token});
  Logger.log('SHEET: ' + ss.getUrl());
  Logger.log('TOKEN (secreto DIAG_TOKEN del Worker): ' + token);
}

function doPost(e) {
  var p = PropertiesService.getScriptProperties(), d = JSON.parse(e.postData.contents || '{}');
  if (!d.token || d.token !== p.getProperty('TOKEN')) return ContentService.createTextOutput('no');
  var r = d.result || {}, esc = function (v) { return String(v == null ? '' : v).replace(/</g, '&lt;'); };
  var prob = r.prob != null ? r.prob + ' % (' + (r.low || '') + '–' + (r.high || '') + ' %, confianza ' + (r.conf || '') + ')' : '';
  SpreadsheetApp.openById(p.getProperty('SHEET')).getSheets()[0].appendRow([new Date(), d.event, d.title || d.tender, d.ref, d.name, d.org,
    d.email, d.cif, r.verdict || '', r.score || '', prob, (r.lots || []).join(', '), d.marketing ? 'sí' : 'no', d.save_profile ? 'sí' : 'no', d.page]);
  var rows = [['Licitación', d.title || d.tender], ['Expediente', d.ref], ['Empresa', d.org + (d.cif ? ' (' + d.cif + ')' : '')], ['Persona', d.name],
    ['Email', d.email], ['Veredicto', r.verdict], ['Puntuación de decisión', r.score != null ? r.score + ' / 100' : ''], ['Probabilidad', prob],
    ['Lotes', (r.lots || []).join(', ')], ['Brechas', (r.gaps || []).join(' · ')], ['Acepta comunicaciones', d.marketing ? 'sí' : 'no'], ['Página', d.page]]
    .map(function (x) { return '<tr><td style="padding:4px 12px 4px 0;color:#4b5563;vertical-align:top">' + x[0] + '</td><td style="padding:4px 0"><b>' + esc(x[1]) + '</b></td></tr>'; });
  var kind = d.event === 'reserva' ? 'Quiere reservar una cita' : 'Nuevo diagnóstico';
  MailApp.sendEmail({to: DIAG_EMAILS, replyTo: d.email || '', name: 'Ullswater · Licitaciones',
    subject: kind + ': ' + (d.org || '') + ' · ' + (d.ref || d.tender) + (r.verdict ? ' · ' + r.verdict : ''),
    htmlBody: '<h2 style="color:#233567;font-family:Arial">' + kind + '</h2><table style="font-family:Arial;font-size:14px">' + rows.join('') + '</table>' +
      '<p style="font-family:Arial;font-size:13px;color:#4b5563">Responde a este email para contestar directamente a la empresa. Recuerda: si otra empresa ya contrató el servicio de pago para esta licitación, solo podemos ofrecer el diagnóstico gratuito.</p>'});
  return ContentService.createTextOutput('ok');
}
