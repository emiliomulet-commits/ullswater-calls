/**
 * Ullswater · "Apply with us" support requests (Google Apps Script) — Nov 2026.
 * Creates the public request form (prefilled with the call or event by calls/events/news pages),
 * a private spreadsheet with the answers and an email to Ullswater for every new request
 * (reply-to = the applicant, so you can answer straight from the inbox).
 * Run setupSupportRequests() once and copy the URL and entry IDs from the log into the sites.
 */
var LEAD_EMAILS = 'eufunding@ullswaterinvestments.com,emilio.mulet@ullswaterinvestments.com';

function setupSupportRequests() {
  var form = FormApp.create('Ullswater Investments · Apply to an EU call with our support');
  form.setDescription(
    'Tell us which call or event you are interested in and what you need. A senior EU funding advisor of Ullswater Investments ' +
    '(Madrid and Brussels) will reply within 2 working days with a first view of fit, consortium and next steps. Free and without commitment.');
  form.setCollectEmail(false);
  form.setAllowResponseEdits(false);
  form.setConfirmationMessage('Thank you. We have received your request and will reply within 2 working days.');

  var qCall = form.addTextItem().setTitle('Call or event').setHelpText('Filled in automatically when you come from a call or event page.').setRequired(true);
  var qPage = form.addTextItem().setTitle('Page');
  form.addTextItem().setTitle('Your name').setRequired(true);
  form.addTextItem().setTitle('Email').setValidation(FormApp.createTextValidation().requireTextIsEmail().build()).setRequired(true);
  form.addTextItem().setTitle('Phone (optional)');
  form.addTextItem().setTitle('Organisation').setRequired(true);
  form.addTextItem().setTitle('Country').setRequired(true);
  form.addListItem().setTitle('Organisation type')
    .setChoiceValues(['SME', 'Start-up', 'Large company', 'University', 'Research or technology centre', 'Public body', 'Association / NGO', 'Other']).setRequired(true);
  form.addCheckboxItem().setTitle('How can we help?')
    .setChoiceValues(['Check whether we are eligible and a good fit', 'Find partners / build the consortium', 'Write the proposal', 'Budget and financial planning', 'Join an existing consortium', 'Other'])
    .setRequired(true);
  form.addParagraphTextItem().setTitle('Your project or idea in a few lines');
  form.addCheckboxItem().setTitle('Consent').setChoiceValues([
    'I agree that Ullswater Investments S.L. stores these details to answer my request and contact me about it.']).setRequired(true);

  var ss = SpreadsheetApp.create('Ullswater · Support requests (private)');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());
  ScriptApp.newTrigger('onSupportRequest').forForm(form).onFormSubmit().create();

  var pre = form.createResponse()
    .withItemResponse(qCall.createResponse('CALL'))
    .withItemResponse(qPage.createResponse('PAGE')).toPrefilledUrl();
  Logger.log('FORM_URL: ' + form.getPublishedUrl());
  Logger.log('PREFILLED: ' + pre);
  Logger.log('SHEET: ' + ss.getUrl());
}

function onSupportRequest(e) {
  var v = {}, rows = [];
  e.response.getItemResponses().forEach(function (r) {
    var t = r.getItem().getTitle(), a = r.getResponse();
    if (Array.isArray(a)) a = a.join(', ');
    v[t] = a;
    if (t !== 'Consent') rows.push('<tr><td style="padding:4px 12px 4px 0;color:#4b5563;vertical-align:top">' + t + '</td><td style="padding:4px 0"><b>' + String(a).replace(/</g, '&lt;') + '</b></td></tr>');
  });
  var html = '<h2 style="color:#233567;font-family:Arial">New support request</h2><table style="font-family:Arial;font-size:14px">' + rows.join('') + '</table>' +
    '<p style="font-family:Arial;font-size:13px;color:#4b5563">Reply to this email to answer the applicant directly.</p>';
  MailApp.sendEmail({to: LEAD_EMAILS, replyTo: v['Email'] || '', name: 'Ullswater · EU calls',
    subject: 'Support request: ' + (v['Call or event'] || '') + ' – ' + (v['Organisation'] || ''), htmlBody: html});
}

// Prints the URLs of the form already created by setupSupportRequests() (found through its trigger).
function showSupportFormUrls() {
  var t = ScriptApp.getProjectTriggers().filter(function (x) { return x.getHandlerFunction() === 'onSupportRequest'; })[0];
  var form = FormApp.openById(t.getTriggerSourceId());
  var items = form.getItems();
  var call = items.filter(function (i) { return i.getTitle() === 'Call or event'; })[0].asTextItem();
  var page = items.filter(function (i) { return i.getTitle() === 'Page'; })[0].asTextItem();
  Logger.log('FORM_URL: ' + form.getPublishedUrl());
  Logger.log('PREFILLED: ' + form.createResponse().withItemResponse(call.createResponse('CALL')).withItemResponse(page.createResponse('PAGE')).toPrefilledUrl());
  Logger.log('SHEET: ' + SpreadsheetApp.openById(form.getDestinationId()).getUrl());
}
