/**
 * Ullswater · Partner board — one-off setup (Google Apps Script).
 * Creates: the public request form, the private moderation spreadsheet,
 * a "Published" tab with approved, public fields only, and an email alert per new request.
 * Run setup() once. The log prints the URLs needed by calls.ullswaterinvestments.com.
 */
var ALERT_EMAIL = 'emilio.mulet@ullswaterinvestments.com';

function setup() {
  var form = FormApp.create('Ullswater Investments · EU call partner request');
  form.setDescription(
    'Publish a partner request or offer for an EU funding call on calls.ullswaterinvestments.com.\n' +
    'Ullswater Investments reviews every request before publishing it. Only your organisation details and description are published; ' +
    'your email is never shown and is used only to put you in touch with matching organisations.');
  form.setCollectEmail(false);
  form.setAllowResponseEdits(false);
  form.setConfirmationMessage('Thank you. We will review your request and publish it on the call page, usually within 2 working days.');

  var qCall = form.addTextItem().setTitle('Call / topic ID')
    .setHelpText('As shown on the call page, e.g. HORIZON-CL4-2027-01-MAT-PROD-17').setRequired(true);
  form.addMultipleChoiceItem().setTitle('What do you want to publish?')
    .setChoiceValues(['We are looking for partners', 'We want to join a consortium']).setRequired(true);
  form.addTextItem().setTitle('Organisation name').setRequired(true);
  form.addTextItem().setTitle('Country').setRequired(true);
  form.addListItem().setTitle('Organisation type')
    .setChoiceValues(['University', 'Research organisation', 'SME', 'Large company', 'Public body', 'Association / NGO', 'Other']).setRequired(true);
  form.addTextItem().setTitle('Website');
  form.addListItem().setTitle('Role')
    .setChoiceValues(['Coordinator', 'Work-package leader', 'Partner', 'Associated partner / third party', 'Open to discuss']).setRequired(true);
  form.addParagraphTextItem().setTitle('What you are looking for or what you offer')
    .setHelpText('Public. Expertise, role in the project, pilot sites, etc. Max 600 characters.')
    .setValidation(FormApp.createParagraphTextValidation().requireTextLengthLessThanOrEqualTo(600).build())
    .setRequired(true);
  form.addTextItem().setTitle('Contact email (not published)')
    .setValidation(FormApp.createTextValidation().requireTextIsEmail().build()).setRequired(true);
  form.addCheckboxItem().setTitle('Consent')
    .setChoiceValues(['I agree that Ullswater Investments publishes the organisation details and description above (not my email) on calls.ullswaterinvestments.com and contacts me about possible partners for this call.'])
    .setRequired(true);

  var ss = SpreadsheetApp.create('Ullswater · Partner board (moderation)');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());
  SpreadsheetApp.flush();
  Utilities.sleep(3000);

  // Responses sheet (its name depends on the account language)
  var resp = ss.getSheets().filter(function (s) { return s.getFormUrl(); })[0];
  resp.setName('Requests');
  // Columns A..K come from the form; L = Status (moderation), M = public ID
  resp.getRange('L1:M1').setValues([['Status', 'Request ID']]).setFontWeight('bold');
  resp.getRange('L2:L1000').setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(['Pending', 'Approved', 'Rejected'], true).build());
  resp.setFrozenRows(1);

  var pub = ss.getSheets().filter(function (s) { return !s.getFormUrl(); })[0] || ss.insertSheet();
  pub.setName('Published');
  pub.getRange('A1').setFormula(
    '=QUERY(Requests!A:M;"select M, B, C, D, E, F, G, H, I, A where L = \'Approved\' label M \'id\', B \'call\', C \'kind\', D \'organisation\', ' +
    'E \'country\', F \'type\', G \'website\', H \'role\', I \'description\', A \'submitted\'";1)');
  pub.getRange('A1').setNote('Do not edit: this tab is published as CSV and feeds calls.ullswaterinvestments.com. Only approved requests and public fields appear here.');

  ScriptApp.newTrigger('onRequest').forForm(form).onFormSubmit().create();

  var prefill = form.createResponse().withItemResponse(qCall.createResponse('TOPICID')).toPrefilledUrl();
  Logger.log('FORM_URL=' + form.getPublishedUrl());
  Logger.log('PREFILL_URL=' + prefill);
  Logger.log('SHEET_URL=' + ss.getUrl());
  Logger.log('SHEET_ID=' + ss.getId());
}

/** New request: mark it Pending, give it an ID and alert Ullswater. */
function onRequest(e) {
  var ss = SpreadsheetApp.openById(e.source.getDestinationId());
  var sh = ss.getSheetByName('Requests');
  var row = sh.getLastRow();
  var id = 'PR-' + Utilities.formatDate(new Date(), 'Europe/Madrid', 'yyMMdd') + '-' + row;
  sh.getRange(row, 12, 1, 2).setValues([['Pending', id]]);
  var v = sh.getRange(row, 1, 1, 11).getValues()[0];
  MailApp.sendEmail(ALERT_EMAIL, 'New partner request ' + id + ' – ' + v[1],
    'Call: ' + v[1] + '\n' + v[2] + '\nOrganisation: ' + v[3] + ' (' + v[4] + ', ' + v[5] + ')\nRole: ' + v[7] +
    '\nWebsite: ' + v[6] + '\nContact: ' + v[9] + '\n\n' + v[8] +
    '\n\nTo publish it, set Status = Approved: ' + ss.getUrl());
}
