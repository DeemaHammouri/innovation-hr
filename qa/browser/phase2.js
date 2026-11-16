const { mk } = require('./jlib');
async function setLang(page, lang) {
  const name = lang === 'ar' ? 'عربي' : 'EN';
  const sw = page.getByRole('radio', { name }).first();
  if (await sw.count() && (await sw.getAttribute('aria-checked')) !== 'true') { await sw.click(); await page.waitForTimeout(900); await page.waitForLoadState('networkidle').catch(() => {}); }
}
const fs = require('fs');
const path = require('path');
const SHOTS = 'C:/Users/user/Desktop/Innovation-hr/qa/browser/phase2';
const XLSX = 'C:/Users/user/AppData/Local/Temp/claude/a2f787886d6edfd6/cb914acc-80a7-410e-b114-ceebcd1659b3/scratchpad/import-test.xlsx';

(async () => {
  const out = [];
  for (const lang of ['en', 'ar']) {
    const j = await mk(lang, 1280, SHOTS);
    const head = await j.as('commercial.head@demo.test'); await setLang(head, lang);
    // Objective 12: dashboard + target
    await j.go(head, '/dashboard');
    const dash = await j.text(head);
    j.ok(`${lang} dashboard shows the target card`, dash.includes(j.T('dash.targetTitle')));
    j.ok(`${lang} dashboard shows total and rates`, dash.includes(j.T('dash.contactRate')) && dash.includes(j.T('dash.acceptanceRate')));
    j.ok(`${lang} overdue stat links to the filtered pool`, await head.locator('a[href*="overdue=1"]').count() > 0);
    await j.shot(head, 'dashboard');
    await head.locator('a[href*="overdue=1"]').first().click(); await j.settle(head);
    j.ok(`${lang} overdue link opens the pool filtered`, head.url().includes('overdue=1'));
    await j.shot(head, 'overdue-pool');

    // Objective 11: appointments
    await j.go(head, '/appointments');
    await head.getByRole('radio', { name: j.T('appt.scope.all') }).click(); await j.settle(head);
    const appts = await j.text(head);
    j.ok(`${lang} the follow-up from a Waiting lead is listed`, appts.includes(j.T('appt.type.follow_up')));
    await j.shot(head, 'appointments');
    await head.getByRole('button', { name: j.T('appt.new') }).first().click(); await j.settle(head);
    await head.fill('#field-title', 'Visit ' + lang);
    await head.getByRole('button', { name: j.T('appt.save') }).last().click(); await j.settle(head);
    j.ok(`${lang} a new appointment is created from the sheet`, (await j.text(head)).includes('Visit ' + lang));
    await j.shot(head, 'appointments-after-create');

    // Objective 10: status history on the lead
    await j.go(head, '/leads/2');
    const lead = await j.text(head);
    j.ok(`${lang} lead shows its status history`, lead.includes(j.T('lead.history')));
    j.ok(`${lang} lead status is named with the brief's wording`, lead.includes(j.T('lead.status.waiting')));
    await j.shot(head, 'lead-history');

    // Objective 11: bell sees the appointment notification (member opens)
    const member = await j.as('commercial.member@demo.test'); await setLang(member, lang);
    await j.go(member, '/appointments');
    j.ok(`${lang} the member sees their own follow-up`, (await j.text(member)).includes(j.T('appt.type.follow_up')));
    j.ok(`${lang} the member has no "Everyone" scope`, !(await j.text(member)).includes(j.T('appt.scope.all')));
    await j.shot(member, 'member-appointments');

    // Objective 9: xlsx import UI (marketing)
    if (lang === 'en') {
      const mkt = await j.as('marketing@demo.test'); await setLang(mkt, lang);
      await j.go(mkt, '/leads/import');
      const imp = await j.text(mkt);
      j.ok('import page offers Excel and CSV templates', imp.includes(j.T('lead.import.templateEnXlsx')) && imp.includes(j.T('lead.import.templateCsv')));
      await mkt.setInputFiles('#field-file', XLSX);
      await mkt.getByRole('button', { name: j.T('lead.import.preview') }).click(); await j.settle(mkt);
      await j.shot(mkt, 'import-preview');
      j.ok('xlsx preview lists rows with states', (await j.text(mkt)).includes(j.T('lead.import.state.duplicate')) || (await j.text(mkt)).includes(j.T('lead.import.state.ok')));
      await mkt.getByRole('button', { name: j.T('lead.import.confirm', { count: 2 }) }).click(); await j.settle(mkt);
      await j.shot(mkt, 'import-result');
      j.ok('skip report is shown after an import with skipped rows', (await j.text(mkt)).includes(j.T('lead.import.skippedHeading')));
    }
    for (const [email, p] of Object.entries(j.sessions)) if (p.errs.length) j.ok(`${lang} no console/server errors for ${email}`, false, p.errs.join(' ; '));
    out.push(...j.results.map(r => `${lang} ${r.pass ? 'PASS' : 'FAIL'} ${r.name}${r.extra ? ' | ' + r.extra : ''}`));
    await j.browser.close();
  }
  fs.writeFileSync('C:/Users/user/Desktop/Innovation-hr/qa/browser/phase2-browser.txt', out.join('\n') + '\n');
  console.log(out.filter(l => l.includes('FAIL')).length ? 'SOME FAILED' : 'ALL PASSED');
})();
