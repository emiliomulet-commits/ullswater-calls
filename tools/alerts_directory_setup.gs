/**
 * Ullswater · EU funding alerts (double opt-in, weekly digest) and organisation directory.
 * Run setupAlertsAndDirectory() once. Then every Monday weeklyDigest() runs automatically.
 */
var SITE = 'https://calls.ullswaterinvestments.com';
var BOARD_CSV = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vQFlSKgfShj44obux_LhMrxiJ0KpxLOkAqqxsyEwBDv0_R2Ojf-v3dT0K4cn-Z-T1bI8V_xz1XH001c/pub?gid=0&single=true&output=csv';
var OWNER_EMAIL = 'emilio.mulet@ullswaterinvestments.com';
var PROGRAMMES = ['Horizon Europe', 'Digital Europe', 'LIFE', 'EU4Health', 'European Defence Fund', 'Creative Europe', 'Erasmus+', 'Cascade funding (open calls for SMEs)', 'Spain – national and regional calls'];
var PROG_CODES = {'Horizon Europe': 'HORIZON', 'Digital Europe': 'DIGITAL', 'LIFE': 'LIFE', 'EU4Health': 'EU4H', 'European Defence Fund': 'EDF', 'Creative Europe': 'CREA', 'Erasmus+': 'ERASMUS'};

function setupAlertsAndDirectory() {
  var P = PropertiesService.getScriptProperties();

  // ---------- Alerts: subscription form ----------
  var sub = FormApp.create('Ullswater Investments · EU funding alerts');
  sub.setDescription('A free weekly email with new EU calls matching your interests, upcoming deadlines and new partner requests for the calls you follow. ' +
    'You will receive a confirmation email first. You can unsubscribe at any time from any alert.');
  sub.setCollectEmail(false);
  sub.setConfirmationMessage('Thank you. Please check your inbox and confirm your subscription (check the spam folder too).');
  var qEmail = sub.addTextItem().setTitle('Email').setValidation(FormApp.createTextValidation().requireTextIsEmail().build()).setRequired(true);
  var qKw = sub.addTextItem().setTitle('Keywords').setHelpText('Separate with commas, e.g. artificial intelligence, hydrogen, health data').setRequired(true);
  var qProg = sub.addCheckboxItem().setTitle('Programmes').setChoiceValues(PROGRAMMES).setRequired(true);
  var qCalls = sub.addTextItem().setTitle('Calls to follow (optional)').setHelpText('Topic IDs separated by commas, for deadline reminders and new partner requests');
  sub.addCheckboxItem().setTitle('Consent').setChoiceValues(['I agree that Ullswater Investments stores my email and preferences to send me these alerts. I can unsubscribe at any time.']).setRequired(true);
  var subSS = SpreadsheetApp.create('Ullswater · Alerts subscribers (private)');
  sub.setDestination(FormApp.DestinationType.SPREADSHEET, subSS.getId());

  // ---------- Alerts: manage form (confirm / unsubscribe via token) ----------
  var man = FormApp.create('Ullswater Investments · Manage EU funding alerts');
  man.setDescription('Confirm or cancel your Ullswater EU funding alerts. Just press Submit.');
  man.setCollectEmail(false);
  var qTok = man.addTextItem().setTitle('Subscription code').setRequired(true);
  var qAct = man.addMultipleChoiceItem().setTitle('Action').setChoiceValues(['Confirm my subscription', 'Unsubscribe']).setRequired(true);
  man.setConfirmationMessage('Done. Thank you.');

  // ---------- Directory: organisation profile form ----------
  var dir = FormApp.create('Ullswater Investments · Organisation profile for the EU partner directory');
  dir.setDescription('Join the Ullswater directory of organisations open to EU consortia. Your profile is reviewed before publication on ' + SITE + '/directory/ and matched with new calls. Your email is never published.');
  dir.setCollectEmail(false);
  dir.addTextItem().setTitle('Organisation name').setRequired(true);
  dir.addTextItem().setTitle('Country').setRequired(true);
  dir.addListItem().setTitle('Organisation type').setChoiceValues(['University', 'Research organisation', 'SME', 'Large company', 'Public body', 'Association / NGO', 'Other']).setRequired(true);
  dir.addTextItem().setTitle('Website');
  dir.addParagraphTextItem().setTitle('Expertise and what you bring to a consortium').setHelpText('Public. Max 800 characters.')
    .setValidation(FormApp.createParagraphTextValidation().requireTextLengthLessThanOrEqualTo(800).build()).setRequired(true);
  dir.addTextItem().setTitle('Keywords').setHelpText('Public. Separate with commas.').setRequired(true);
  dir.addListItem().setTitle('Preferred role').setChoiceValues(['Coordinator', 'Work-package leader', 'Partner', 'Associated partner / third party', 'Open to discuss']).setRequired(true);
  dir.addTextItem().setTitle('Contact email (not published)').setValidation(FormApp.createTextValidation().requireTextIsEmail().build()).setRequired(true);
  dir.addCheckboxItem().setTitle('Consent').setChoiceValues(['I agree that Ullswater Investments publishes the organisation details, expertise and keywords above (not my email) on calls.ullswaterinvestments.com and contacts me about matching calls and partners.']).setRequired(true);
  var dirSS = SpreadsheetApp.create('Ullswater · Directory (moderation)');
  dir.setDestination(FormApp.DestinationType.SPREADSHEET, dirSS.getId());
  man.setDestination(FormApp.DestinationType.SPREADSHEET, subSS.getId());

  SpreadsheetApp.flush();
  Utilities.sleep(4000);

  // Subscribers sheet: extra columns Status | Token | Last sent
  var sh = subSS.getSheets().filter(function (s) { return s.getFormUrl() && s.getFormUrl().indexOf(sub.getId()) > -1; })[0] || subSS.getSheets()[0];
  sh.setName('Subscribers');
  var lastCol = sh.getLastColumn();
  sh.getRange(1, lastCol + 1, 1, 3).setValues([['Status', 'Token', 'Last sent']]).setFontWeight('bold');
  subSS.getSheets().forEach(function (s) { if (s.getFormUrl() && s.getFormUrl().indexOf(man.getId()) > -1) s.setName('Manage'); });
  subSS.getSheets().forEach(function (s) { if (!s.getFormUrl() && s.getName() !== 'Subscribers' && s.getName() !== 'Manage' && s.getLastRow() === 0) subSS.deleteSheet(s); });

  // Directory sheet: Status | Profile ID ; Published tab (public fields only)
  var dsh = dirSS.getSheets().filter(function (s) { return s.getFormUrl(); })[0];
  dsh.setName('Profiles');
  dsh.getRange('K1:L1').setValues([['Status', 'Profile ID']]).setFontWeight('bold');
  dsh.getRange('K2:K1000').setDataValidation(SpreadsheetApp.newDataValidation().requireValueInList(['Pending', 'Approved', 'Rejected'], true).build());
  var dpub = dirSS.getSheets().filter(function (s) { return !s.getFormUrl(); })[0] || dirSS.insertSheet();
  dpub.setName('Published');

  ScriptApp.newTrigger('onSubscribe').forForm(sub).onFormSubmit().create();
  ScriptApp.newTrigger('onManage').forForm(man).onFormSubmit().create();
  ScriptApp.newTrigger('onProfile').forForm(dir).onFormSubmit().create();
  ScriptApp.newTrigger('weeklyDigest').timeBased().onWeekDay(ScriptApp.WeekDay.MONDAY).atHour(7).inTimezone('Europe/Madrid').create();

  P.setProperties({SUB_SS: subSS.getId(), DIR_SS: dirSS.getId(), MANAGE_URL: man.getPublishedUrl(),
                   MANAGE_TOKEN_ENTRY: String(qTok.getId()), MANAGE_ACTION_ENTRY: String(qAct.getId())});
  var subPrefill = sub.createResponse().withItemResponse(qKw.createResponse('KW')).withItemResponse(qCalls.createResponse('CALLID')).toPrefilledUrl();
  var manPrefill = man.createResponse().withItemResponse(qTok.createResponse('TOKEN')).withItemResponse(qAct.createResponse('Confirm my subscription')).toPrefilledUrl();
  var unsPrefill = man.createResponse().withItemResponse(qTok.createResponse('TOKEN')).withItemResponse(qAct.createResponse('Unsubscribe')).toPrefilledUrl();
  P.setProperty('MANAGE_PREFILL', manPrefill);
  P.setProperty('UNSUB_PREFILL', unsPrefill);
  Logger.log('ALERTS_FORM=' + sub.getPublishedUrl());
  Logger.log('ALERTS_PREFILL=' + subPrefill);
  Logger.log('MANAGE_PREFILL=' + manPrefill);
  Logger.log('DIRECTORY_FORM=' + dir.getPublishedUrl());
  Logger.log('SUB_SS=' + subSS.getUrl());
  Logger.log('DIR_SS_ID=' + dirSS.getId());
}

function header_(sh) { return sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0]; }
function col_(h, name) { for (var i = 0; i < h.length; i++) if (String(h[i]).indexOf(name) === 0) return i + 1; return -1; }
function manageLink_(token, action) {
  var P = PropertiesService.getScriptProperties();
  return P.getProperty(action === 'Unsubscribe' ? 'UNSUB_PREFILL' : 'MANAGE_PREFILL').replace('TOKEN', encodeURIComponent(token));
}

function onSubscribe(e) {
  var ss = SpreadsheetApp.openById(PropertiesService.getScriptProperties().getProperty('SUB_SS'));
  var sh = ss.getSheetByName('Subscribers'), h = header_(sh), row = sh.getLastRow();
  var token = Utilities.getUuid().replace(/-/g, '').slice(0, 16);
  sh.getRange(row, col_(h, 'Status')).setValue('Pending');
  sh.getRange(row, col_(h, 'Token')).setValue(token);
  var email = sh.getRange(row, col_(h, 'Email')).getValue();
  var html = '<p>Hello,</p><p>Please confirm your Ullswater Investments EU funding alerts:</p>' +
    '<p><a href="' + manageLink_(token, 'Confirm') + '" style="background:#c9a646;color:#233567;padding:10px 18px;border-radius:6px;text-decoration:none;font-weight:bold">Confirm my subscription</a></p>' +
    '<p>On the page that opens, just press <b>Submit</b>. If you did not request these alerts, ignore this email.</p><p>Ullswater Investments · EU Funding Advisors<br>' + SITE + '</p>';
  MailApp.sendEmail({to: email, subject: 'Confirm your EU funding alerts', htmlBody: html, name: 'Ullswater Investments'});
}

function onManage(e) {
  var r = e.response.getItemResponses(), token = '', action = '';
  r.forEach(function (x) { var t = x.getItem().getTitle(); if (t === 'Subscription code') token = String(x.getResponse()).trim(); if (t === 'Action') action = x.getResponse(); });
  var ss = SpreadsheetApp.openById(PropertiesService.getScriptProperties().getProperty('SUB_SS'));
  var sh = ss.getSheetByName('Subscribers'), h = header_(sh), data = sh.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    if (String(data[i][col_(h, 'Token') - 1]) === token) {
      sh.getRange(i + 1, col_(h, 'Status')).setValue(action === 'Unsubscribe' ? 'Unsubscribed' : 'Confirmed');
    }
  }
}

function onProfile(e) {
  var ss = SpreadsheetApp.openById(PropertiesService.getScriptProperties().getProperty('DIR_SS'));
  var sh = ss.getSheetByName('Profiles'), row = sh.getLastRow();
  var id = 'ORG-' + Utilities.formatDate(new Date(), 'Europe/Madrid', 'yyMMdd') + '-' + row;
  sh.getRange(row, 11, 1, 2).setValues([['Pending', id]]);
  var v = sh.getRange(row, 1, 1, 10).getValues()[0];
  MailApp.sendEmail(OWNER_EMAIL, 'New directory profile ' + id + ' – ' + v[1],
    v[1] + ' (' + v[2] + ', ' + v[3] + ')\nWebsite: ' + v[4] + '\nRole: ' + v[7] + '\nKeywords: ' + v[6] + '\nContact: ' + v[8] + '\n\n' + v[5] +
    '\n\nTo publish it, set Status = Approved: ' + ss.getUrl());
}

function norm_(s) { return String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); }

function weeklyDigest() {
  var P = PropertiesService.getScriptProperties();
  var calls = JSON.parse(UrlFetchApp.fetch(SITE + '/data/calls.json?t=' + Date.now()).getContentText()).calls;
  var spain = [];
  try { spain = JSON.parse(UrlFetchApp.fetch(SITE + '/data/spain.json?t=' + Date.now()).getContentText()).calls; } catch (err) {}
  var board = [];
  try { board = Utilities.parseCsv(UrlFetchApp.fetch(BOARD_CSV + '&t=' + Date.now()).getContentText()); } catch (err) {}
  var seen = JSON.parse(P.getProperty('SEEN') || '[]'), seenSet = {};
  seen.forEach(function (id) { seenSet[id] = 1; });
  var firstRun = seen.length === 0;
  var today = new Date();
  var ss = SpreadsheetApp.openById(P.getProperty('SUB_SS')), sh = ss.getSheetByName('Subscribers'), h = header_(sh), data = sh.getDataRange().getValues();
  var sent = 0;
  for (var i = 1; i < data.length; i++) {
    var r = data[i];
    if (r[col_(h, 'Status') - 1] !== 'Confirmed') continue;
    var email = r[col_(h, 'Email') - 1], kws = String(r[col_(h, 'Keywords') - 1]).split(',').map(function (k) { return norm_(k).trim(); }).filter(String);
    var progs = String(r[col_(h, 'Programmes') - 1]), follow = String(r[col_(h, 'Calls to follow') - 1] || '').toUpperCase().split(/[,\s]+/).filter(String);
    var codes = Object.keys(PROG_CODES).filter(function (p) { return progs.indexOf(p) > -1; }).map(function (p) { return PROG_CODES[p]; });
    var wantCascade = progs.indexOf('Cascade') > -1, wantSpain = progs.indexOf('Spain') > -1;
    function match(text) { var t = norm_(text); return kws.some(function (k) { return t.indexOf(k) > -1; }); }
    var fresh = calls.filter(function (c) {
      if (!firstRun && seenSet[c.id] && r[col_(h, 'Last sent') - 1]) return false;
      var progOk = (c.kind === 'cascade') ? wantCascade : codes.indexOf(c.programme) > -1;
      return progOk && match(c.title + ' ' + (c.summary || '') + ' ' + (c.tags || []).join(' '));
    }).slice(0, 15);
    var soon = calls.filter(function (c) {
      if (!c.deadline) return false;
      var d = (new Date(c.deadline + 'T00:00:00') - today) / 864e5;
      return d >= 0 && d <= 21 && (follow.indexOf(c.id.toUpperCase()) > -1 || (codes.indexOf(c.programme) > -1 && match(c.title)));
    }).slice(0, 10);
    var es = wantSpain ? spain.filter(function (c) { return match(c.title); }).slice(0, 8) : [];
    var reqs = board.slice(1).filter(function (b) { return follow.indexOf(String(b[1]).toUpperCase()) > -1; });
    if (!fresh.length && !soon.length && !es.length && !reqs.length) continue;
    var link = function (c) { return SITE + '/call/' + c.id.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') + '/'; };
    var html = '<div style="font-family:Arial,sans-serif;max-width:640px;color:#1f2937"><h2 style="color:#233567">Your EU funding alerts</h2>';
    if (fresh.length) html += '<h3 style="color:#233567">New calls matching your interests</h3><ul>' + fresh.map(function (c) { return '<li><a href="' + link(c) + '">' + c.title + '</a><br><small>' + c.id + ' · ' + (c.status === 'open' ? 'Open' : 'Forthcoming') + (c.deadline ? ' · deadline ' + c.deadline : '') + '</small></li>'; }).join('') + '</ul>';
    if (soon.length) html += '<h3 style="color:#b42318">Deadlines in the next 3 weeks</h3><ul>' + soon.map(function (c) { return '<li><a href="' + link(c) + '">' + c.title + '</a> – <b>' + c.deadline + '</b></li>'; }).join('') + '</ul>';
    if (reqs.length) html += '<h3 style="color:#233567">Partner requests for the calls you follow</h3><ul>' + reqs.map(function (b) { return '<li>' + b[3] + ' (' + b[4] + ') – ' + b[2] + ' · ' + b[1] + '</li>'; }).join('') + '</ul><p><a href="' + SITE + '/partners/">See the partner board</a></p>';
    if (es.length) html += '<h3 style="color:#233567">Spain – national and regional calls</h3><ul>' + es.map(function (c) { return '<li><a href="' + c.bdns + '">' + c.title + '</a><br><small>' + c.body + (c.end ? ' · until ' + c.end : '') + '</small></li>'; }).join('') + '</ul>';
    html += '<p style="margin-top:24px"><a href="' + SITE + '/finder/" style="background:#c9a646;color:#233567;padding:9px 16px;border-radius:6px;text-decoration:none;font-weight:bold">Find more calls for your project</a></p>' +
      '<p style="font-size:12px;color:#6b7280">Ullswater Investments · EU Funding Advisors · Calle Ramírez de Arellano 17, 28043 Madrid<br>' +
      '<a href="' + manageLink_(r[col_(h, 'Token') - 1], 'Unsubscribe') + '">Unsubscribe</a></p></div>';
    MailApp.sendEmail({to: email, subject: 'EU funding alerts – ' + Utilities.formatDate(today, 'Europe/Madrid', 'd MMM yyyy'), htmlBody: html, name: 'Ullswater Investments'});
    sh.getRange(i + 1, col_(h, 'Last sent')).setValue(today);
    sent++;
  }
  P.setProperty('SEEN', JSON.stringify(calls.map(function (c) { return c.id; })));
  Logger.log('Digests sent: ' + sent + ' (remaining daily mail quota: ' + MailApp.getRemainingDailyQuota() + ')');
}
