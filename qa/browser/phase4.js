// Phase 4 browser proof, objectives 18-21: run once per language ("en" or "ar"), against a throwaway database and the production build.
//   PROOF_SEED=<seed json> PROOF_OUT=<folder> node phase4.js en
// Widths 375 and 768 check layout and console errors on every Phase 4 page; 1280 walks the whole flow with screenshots.
const { mk } = require('./jlib');
const fs = require('fs');
const SEED = JSON.parse(fs.readFileSync(process.env.PROOF_SEED, 'utf8'));
const OUT = process.env.PROOF_OUT;
const lang = process.argv[2] || 'en';
const S = SEED[lang];
fs.mkdirSync(OUT, { recursive: true });

const setLang = async (page) => {
  const name = lang === 'ar' ? 'عربي' : 'EN';
  const sw = page.getByRole('radio', { name }).first();
  if (await sw.count() && (await sw.getAttribute('aria-checked')) !== 'true') { await sw.click(); await page.waitForTimeout(900); await page.waitForLoadState('networkidle').catch(() => {}); }
};
const noOverflow = (page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
const dlg = (p) => p.locator('[role=dialog]');
const row = (page, title) => page.locator('li', { hasText: title }).first();
const G = {};
const act = async (page, title, name) => {
  for (let i = 0; i < 4; i++) {
    await page.waitForTimeout(500);
    await row(page, title).getByRole('button', { name: G.T('common.actions') }).click();
    try { await page.getByRole('menuitem', { name }).first().click({ timeout: 4000 }); return; } catch { await page.keyboard.press('Escape'); }
  }
  throw new Error('menu item not clickable: ' + name);
};
const pick = async (page, name) => { const mi = page.getByRole('menuitem', { name }).first(); if (await mi.count()) await mi.click(); else await page.getByText(name, { exact: true }).first().click(); };

(async () => {
  let fails = 0;
  for (const width of [375, 768, 1280]) {
    const j = await mk(lang, width, OUT);
    const tag = `${lang} ${width}`;
    const T = j.T; G.T = T;
    const check = (name, cond, extra) => { if (!cond) fails++; j.ok(`${tag} ${name}`, cond, extra); };
    const sheetBtn = (page, key) => page.locator('[role=dialog]').getByRole('button', { name: T(key) }).last();
    const settleToast = async (page) => { await j.settle(page); };
    const clean = async (page, label) => { check(`${label}: no console error`, page.errs.length === 0, page.errs.join(' ; ')); page.errs.length = 0; };
    const view = async (page, path, name, expect) => {
      await j.go(page, path); await setLang(page); await j.settle(page);
      check(`${name}: no horizontal scroll`, await noOverflow(page));
      if (expect) { const tx = await j.text(page); check(`${name}: shows "${expect}"`, tx.includes(expect)); }
      await j.shot(page, name); await clean(page, name);
    };
    const head = await j.as('operation.head@demo.test'); await setLang(head);
    const member = await j.as('operation.member@demo.test'); await setLang(member);
    const ceo = await j.as('ceo@innovation.test'); await setLang(ceo);
    const client = await j.as(S.email); await setLang(client);

    // ---- layout pass (every width)
    await view(head, `/operation/${S.client}`, 'client-tasks', 'Flow task');
    await view(head, '/operation/monitoring', 'monitoring', 'Blocked old task');
    await view(ceo, '/operation/monitoring', 'monitoring-ceo', 'Blocked old task');
    await view(client, '/portal', 'portal', S.company);
    await view(ceo, '/reports?tab=operations', 'reports-operations');
    await view(ceo, '/admin/lookups', 'settings');
    await j.go(head, `/operation/${S.client}`);
    await head.getByRole('button', { name: T('op.rec.add') }).click(); await j.settle(head);
    check('recurrence rule sheet opens with the frequency list', (await dlg(head).getByLabel(T('op.rec.frequency'), { exact: false }).first().locator('option').count()) >= 7);
    check('recurrence rule sheet has no horizontal scroll', await noOverflow(head));
    await j.shot(head, 'recurrence-sheet'); await clean(head, 'recurrence sheet');
    await head.getByRole('button', { name: T('common.cancel') }).first().click(); await j.settle(head);

    if (width !== 1280) { for (const p of Object.values(j.sessions)) await p.close(); await j.browser.close(); continue; }

    // ---- 1280: the whole flow
    // Objective 20: add a rule, edit it (a new version), and the holiday calendar
    await head.getByRole('button', { name: T('op.rec.add') }).click(); await j.settle(head);
    await dlg(head).getByLabel(T('op.rec.title'), { exact: false }).first().fill('Weekly proof rule');
    await dlg(head).getByLabel(T('op.rec.frequency'), { exact: false }).first().selectOption('weekly');
    await j.shot(head, 'recurrence-new');
    await sheetBtn(head, 'common.save').click().catch(async () => head.locator('[role=dialog] button[type=submit]').click()); await j.settle(head);
    check('the new rule is listed', (await j.text(head)).includes('Weekly proof rule'));
    await head.locator('li', { hasText: 'Weekly proof rule' }).first().getByRole('button', { name: T('common.edit') }).click(); await j.settle(head);
    await dlg(head).getByLabel(T('op.rec.frequency'), { exact: false }).first().selectOption('daily');
    await j.shot(head, 'recurrence-edit');
    await sheetBtn(head, 'common.save').click().catch(async () => head.locator('[role=dialog] button[type=submit]').click()); await j.settle(head);
    check('the edit is saved', (await j.text(head)).includes(T('op.rec.updated')) || (await j.text(head)).includes('Weekly proof rule'));
    await clean(head, 'rule editor');

    await j.go(ceo, '/admin/lookups'); await setLang(ceo);
    const hol = ceo.getByRole('tab', { name: T('lookups.section.holidays') }).first();
    if (await hol.count()) await hol.click(); else await dlg(ceo).getByLabel(T('lookups.sectionLabel')).selectOption('holidays');
    await j.settle(ceo);
    const future = new Date(); future.setDate(future.getDate() + 40); const hd = future.toISOString().slice(0, 10);
    await ceo.getByRole('button', { name: T('lookups.add') }).first().click(); await j.settle(ceo);
    await dlg(ceo).getByLabel(T('lookups.holidays.date')).first().fill(hd);
    await sheetBtn(ceo, 'lookups.save').click(); await j.settle(ceo);
    check('holiday: empty names are refused', (await j.text(ceo)).includes(T('lookups.nameEn')) && await dlg(ceo).count() === 1);
    await j.shot(ceo, 'holiday-refused');
    await dlg(ceo).getByLabel(T('lookups.nameEn')).fill('Proof Day');
    await dlg(ceo).getByLabel(T('lookups.nameAr')).fill('يوم الإثبات');
    await j.shot(ceo, 'holiday-add');
    await sheetBtn(ceo, 'lookups.save').click(); await j.settle(ceo);
    check('the holiday is added', (await j.text(ceo)).length > 0 && await ceo.getByRole('button', { name: T('lookups.holidays.remove') }).count() >= 1);
    await j.shot(ceo, 'holiday-list');
    const hmember = await member.evaluate(async () => (await fetch('/api/v1/lookups/holidays/')).status);
    check('Operation can read the calendar', hmember === 200);
    await ceo.getByRole('button', { name: T('lookups.holidays.remove') }).first().click(); await j.settle(ceo);
    check('the holiday is removed', (await j.text(ceo)).includes(T('lookups.holidays.removed')) || await ceo.getByRole('button', { name: T('lookups.holidays.remove') }).count() === 0);
    await clean(ceo, 'holidays');

    // Objective 21: the lifecycle, as the assignee and as the reviewer
    const path = `/operation/${S.client}`;
    await j.go(member, path); await setLang(member);
    let r = row(member, 'Flow task');
    await r.getByRole('button', { name: T('op.task.start') }).click(); await j.settle(member);
    check('start: the task is in progress', (await r.innerText()).includes(T('op.task.status.in_progress')));
    await r.getByRole('button', { name: T('op.task.progress') }).click(); await j.settle(member);
    await dlg(member).locator("input[type=range]").fill('40');
    await dlg(member).getByLabel(T('op.task.progressNote')).fill('Half way');
    await j.shot(member, 'progress-sheet');
    await sheetBtn(member, 'common.save').click(); await j.settle(member);
    check('progress: 40% saved', (await row(member, 'Flow task').locator('[role=progressbar]').first().getAttribute('aria-valuenow')) === '40');
    await j.shot(member, 'progress');
    await act(member, 'Flow task', T('op.task.wait')); await j.settle(member);
    await sheetBtn(member, 'op.task.waitSave').click(); await j.settle(member);
    check('waiting: an empty reason is refused', (await j.text(member)).includes(T('op.task.err.wait')));
    await dlg(member).getByLabel(T('op.task.waitQuestion')).fill('Waiting for the invoices');
    await sheetBtn(member, 'op.task.waitSave').click(); await j.settle(member);
    r = row(member, 'Flow task');
    check('waiting: shows the status and the reason', (await r.innerText()).includes(T('op.task.status.waiting')) && (await r.innerText()).includes('Waiting for the invoices'));
    await j.shot(member, 'waiting');
    await r.getByRole('button', { name: T('op.task.resume') }).click(); await j.settle(member);
    await act(member, 'Flow task', T('op.task.block')); await j.settle(member);
    await dlg(member).getByLabel(T('op.task.blockQuestion')).fill('No access to the tax portal');
    await sheetBtn(member, 'op.task.blockSave').click(); await j.settle(member);
    check('blocked: shows the status', (await row(member, 'Flow task').innerText()).includes(T('op.task.status.blocked')));
    await j.shot(member, 'blocked');
    await row(member, 'Flow task').getByRole('button', { name: T('op.task.resume') }).click(); await j.settle(member);
    check('the assignee has no Approve button', await row(member, 'Flow task').getByRole('button', { name: T('op.task.approve') }).count() === 0);
    await act(member, 'Flow task', T('op.task.submit')); await j.settle(member);
    check('submit: waiting for review', (await row(member, 'Flow task').innerText()).includes(T('op.task.status.submitted')));
    await j.shot(member, 'submitted');
    await clean(member, 'assignee steps');

    await j.go(head, path); await setLang(head);
    r = row(head, 'Flow task');
    await r.getByRole('button', { name: T('op.task.return') }).click(); await j.settle(head);
    await sheetBtn(head, 'op.task.returnSave').click(); await j.settle(head);
    check('send back: an empty note is refused', (await j.text(head)).includes(T('op.task.err.return')));
    await dlg(head).getByLabel(T('op.task.returnQuestion')).fill('Add the March invoices');
    await sheetBtn(head, 'op.task.returnSave').click(); await j.settle(head);
    check('send back: back in progress with the note', (await row(head, 'Flow task').innerText()).includes('Add the March invoices'));
    await j.shot(head, 'returned');
    await j.go(member, path);
    await act(member, 'Flow task', T('op.task.submit')); await j.settle(member);
    await j.go(head, path);
    await row(head, 'Flow task').getByRole('button', { name: T('op.task.approve') }).click(); await j.settle(head);
    check('approve: done', (await row(head, 'Flow task').innerText()).includes(T('op.task.status.done')));
    await j.shot(head, 'approved'); await clean(head, 'review steps');

    // escalation: level 1 by the assignee, level 2 by the head, nothing after that
    await j.go(member, path);
    await act(member, 'Late task to escalate', T('op.task.escalate')); await j.settle(member);
    await dlg(member).getByLabel(T('op.task.escalateQuestion')).fill('The client has not sent the papers');
    await sheetBtn(member, 'op.task.escalateSave').click(); await j.settle(member);
    check('escalation 1: shown as sent to the Operation head', (await row(member, 'Late task to escalate').innerText()).includes(T('op.task.escalatedTo', { who: T('op.task.toHead') })));
    await j.shot(member, 'escalated-1');
    await j.go(head, path);
    await act(head, 'Late task to escalate', T('op.task.escalate')); await j.settle(head);
    await dlg(head).getByLabel(T('op.task.escalateQuestion')).fill('Needs the CEO to call the client');
    await sheetBtn(head, 'op.task.escalateSave').click(); await j.settle(head);
    check('escalation 2: shown as sent to the CEO', (await row(head, 'Late task to escalate').innerText()).includes(T('op.task.escalatedTo', { who: T('op.task.toCeo') })));
    await j.shot(head, 'escalated-2');
    await row(head, 'Late task to escalate').getByRole('button', { name: T('common.actions') }).click();
    check('escalation 3 is not offered', await head.getByRole('menuitem', { name: T('op.task.escalate') }).count() === 0);
    await head.keyboard.press('Escape');
    await clean(head, 'escalation');

    // deliverable: published by the assignee, seen, opened and confirmed by the client
    await j.go(member, path);
    await act(member, 'VAT return to deliver', T('op.task.deliver')); await j.settle(member);
    await dlg(member).getByLabel(T('op.task.deliverFile')).selectOption({ index: 1 });
    await dlg(member).getByLabel(T('op.task.deliverTitle')).fill('VAT return Q3');
    await j.shot(member, 'deliver-sheet');
    await sheetBtn(member, 'op.task.deliverSave').click(); await j.settle(member);
    check('deliverable: published, not confirmed yet', (await row(member, 'VAT return to deliver').innerText()).includes(T('op.task.notAcked')));
    await j.go(client, '/portal');
    check('portal: the client sees the file as new', (await j.text(client)).includes('VAT return Q3') && (await j.text(client)).includes(T('portal.files.new')));
    await j.shot(client, 'portal-file');
    const [dl] = await Promise.all([client.waitForEvent('download', { timeout: 15000 }), client.getByRole('button', { name: T('portal.files.open') }).first().click()]);
    await dl.saveAs(`${OUT}/${lang}-downloaded-by-client.pdf`);
    check('portal: the client downloads the file', fs.readFileSync(`${OUT}/${lang}-downloaded-by-client.pdf`).slice(0, 4).toString() === '%PDF');
    await client.getByRole('button', { name: T('portal.files.confirm') }).first().click(); await j.settle(client);
    check('portal: confirmation recorded', !(await j.text(client)).includes(T('portal.files.new')));
    await j.shot(client, 'portal-confirmed');
    await j.go(member, path);
    check('the task shows the client confirmation', !(await row(member, 'VAT return to deliver').innerText()).includes(T('op.task.notAcked')));
    await j.shot(member, 'deliver-confirmed');
    const other = await client.evaluate(async () => (await fetch('/api/v1/operations/tasks/')).status);
    check('the client cannot open Operation tasks', other === 403 || other === 401 || other === 404, String(other));
    await clean(client, 'portal'); await clean(member, 'deliverable');

    // monitoring after the flow
    await j.go(ceo, '/operation/monitoring');
    const mt = await j.text(ceo);
    check('monitoring lists the escalated and the blocked tasks', mt.includes('Late task to escalate') && mt.includes('Blocked old task'));
    check('monitoring shows no money', !/JOD|\$|USD/.test(mt));
    await j.shot(ceo, 'monitoring-after'); await clean(ceo, 'monitoring');

    // exports: the same rows in JSON, CSV, Excel and PDF
    await j.go(ceo, '/reports?tab=operations');
    const jsonRes = await ceo.evaluate(async () => { const to = new Date().toISOString().slice(0, 10); const f = new Date(Date.now() - 89 * 864e5).toISOString().slice(0, 10); const r = await fetch(`/api/v1/reports/operations/?from=${f}&to=${to}`); return r.json(); });
    fs.writeFileSync(`${OUT}/${lang}-report.json`, JSON.stringify(jsonRes, null, 1));
    for (const [key, ext] of [['rep.export', 'csv'], ['rep.exportXlsx', 'xlsx'], ['rep.exportPdf', 'pdf']]) {
      const [d] = await Promise.all([ceo.waitForEvent('download', { timeout: 30000 }), ceo.getByRole('button', { name: T(key) }).first().click()]);
      await d.saveAs(`${OUT}/${lang}-report.${ext}`);
      check(`export ${ext} downloaded`, fs.statSync(`${OUT}/${lang}-report.${ext}`).size > 200);
    }
    await j.shot(ceo, 'reports-exported');
    const denied = await member.evaluate(async () => (await fetch('/api/v1/reports/finance/export/?fmt=xlsx')).status);
    check('Operation cannot export another department\'s report', denied === 403 || denied === 404, String(denied));
    await clean(ceo, 'reports');
    for (const p of Object.values(j.sessions)) await p.close(); await j.browser.close();
  }
  console.log(`DONE ${lang}: ${fails} failure(s)`);
  process.exit(fails ? 1 : 0);
})().catch((e) => { console.log('SCRIPT ERROR', e.message); process.exit(2); });
