// Phase 4 browser proof, objectives 18-19 (handover, Operations privacy, versioned KYC with expiry, project staffing).
//   PROOF_SEED=<proof2 json> PROOF_OUT=<folder> node phase4a.js en
// 375 and 768 check layout and console errors; 1280 walks the flow with screenshots.
const { mk } = require('./jlib');
const fs = require('fs');
const SEED = JSON.parse(fs.readFileSync(process.env.PROOF_SEED, 'utf8'));
const OUT = process.env.PROOF_OUT;
const lang = process.argv[2] || 'en';
const S = SEED[lang];
fs.mkdirSync(OUT, { recursive: true });
const PDFFILE = `${OUT}/${lang}-kyc-sample.pdf`;
fs.writeFileSync(PDFFILE, '%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n');
const PDF2 = `${OUT}/${lang}-kyc-sample-2.pdf`;
fs.writeFileSync(PDF2, '%PDF-1.4\n1 0 obj<<>>endobj\n2 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n');

const setLang = async (page) => {
  const name = lang === 'ar' ? 'عربي' : 'EN';
  const sw = page.getByRole('radio', { name }).first();
  if (await sw.count() && (await sw.getAttribute('aria-checked')) !== 'true') { await sw.click(); await page.waitForTimeout(900); await page.waitForLoadState('networkidle').catch(() => {}); }
};
const noOverflow = (page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
const dlg = (p) => p.locator('[role=dialog]');

(async () => {
  let fails = 0;
  for (const width of [375, 768, 1280]) {
    const j = await mk(lang, width, OUT);
    const T = j.T; const tag = `${lang} ${width}`;
    const check = (name, cond, extra) => { if (!cond) fails++; j.ok(`${tag} ${name}`, cond, extra); };
    const clean = (page, label) => { check(`${label}: no console error`, page.errs.length === 0, page.errs.join(' ; ')); page.errs.length = 0; };
    const sheetBtn = (page, key) => dlg(page).getByRole('button', { name: T(key) }).last();
    const view = async (page, path, name, expect) => {
      await j.go(page, path); await setLang(page); await j.settle(page);
      check(`${name}: no horizontal scroll`, await noOverflow(page));
      if (expect) check(`${name}: shows "${expect}"`, (await j.text(page)).includes(expect));
      await j.shot(page, name); clean(page, name);
    };
    const cm = await j.as('commercial.member@demo.test'); await setLang(cm);
    const oh = await j.as('operation.head@demo.test'); await setLang(oh);
    const om = await j.as('operation.member@demo.test'); await setLang(om);
    const ceo = await j.as('ceo@innovation.test'); await setLang(ceo);
    const A = S.handovers[0], B = S.handovers[1];
    const kycName = lang === 'ar' ? S.kyc_item_ar : S.kyc_item_en;

    await view(cm, `/handovers/${A.id}`, 'handover-new', A.company);
    await view(oh, '/handovers', 'handovers-list');
    await view(oh, '/projects', 'projects');
    await view(oh, `/operation/${S.kyc}`, 'kyc-checklist', kycName);
    if (width !== 1280) { for (const p of Object.values(j.sessions)) await p.close(); await j.browser.close(); continue; }

    // Objective 18: fill in, submit, return with a note, fix, submit again, accept -> project
    await j.go(cm, `/handovers/${A.id}`);
    await cm.getByRole('button', { name: T('ho.edit') }).click(); await j.settle(cm);
    await j.shot(cm, 'fill-sheet-empty');
    await sheetBtn(cm, 'common.save').click(); await j.settle(cm);   // a draft may be saved empty
    await cm.getByRole('button', { name: T('ho.submit') }).click(); await j.settle(cm);
    check('submitting an empty handover is refused', await cm.getByRole('button', { name: T('ho.submit') }).count() === 1);
    await j.shot(cm, 'submit-refused');
    await cm.getByRole('button', { name: T('ho.edit') }).click(); await j.settle(cm);
    await dlg(cm).getByLabel(T('ho.services'), { exact: false }).first().fill('Monthly bookkeeping and VAT');
    await dlg(cm).getByLabel(T('ho.scope'), { exact: false }).first().fill('Two branches, 40 invoices a month');
    await dlg(cm).getByLabel(T('ho.contacts'), { exact: false }).first().fill('Sam, accountant');
    await j.shot(cm, 'fill-sheet');
    await sheetBtn(cm, 'common.save').click(); await j.settle(cm);
    check('the handover shows what was written', (await j.text(cm)).includes('Monthly bookkeeping and VAT'));
    await cm.getByRole('button', { name: T('ho.submit') }).click(); await j.settle(cm);
    check('submitted to Operation', (await j.text(cm)).includes(T('ho.submittedAt')) && await cm.getByRole('button', { name: T('ho.submit') }).count() === 0);
    await j.shot(cm, 'submitted');
    const ohText = async () => { await j.go(oh, `/handovers/${A.id}`); return j.text(oh); };
    let tx = await ohText();
    check('Operation sees the handover with no price or payment words', tx.includes('Monthly bookkeeping') && !/JOD|price|payment terms|السعر|الدفع/i.test(tx.replace(T('ho.noPrices'), '')));
    await j.shot(oh, 'ops-handover');
    await oh.getByRole('button', { name: T('ho.return') }).click(); await j.settle(oh);
    await sheetBtn(oh, 'ct.return.save').click(); await j.settle(oh);
    check('return: an empty note is refused', await dlg(oh).count() === 1);
    await dlg(oh).getByLabel(T('ct.return.comment')).fill('Add the start date');
    await sheetBtn(oh, 'ct.return.save').click(); await j.settle(oh);
    await j.go(cm, `/handovers/${A.id}`);
    check('Commercial sees the returned notes', (await j.text(cm)).includes('Add the start date'));
    await j.shot(cm, 'returned-notes');
    await cm.getByRole('button', { name: T('ho.edit') }).click(); await j.settle(cm);
    await dlg(cm).getByLabel(T('ho.startDate')).fill('2027-01-04');
    await sheetBtn(cm, 'common.save').click(); await j.settle(cm);
    await cm.getByRole('button', { name: T('ho.submit') }).click(); await j.settle(cm);
    await j.go(oh, `/handovers/${A.id}`);
    check('Operation head cannot edit the handover', await oh.getByRole('button', { name: T('ho.edit') }).count() === 0);
    await oh.getByRole('button', { name: T('ho.accept') }).click(); await j.settle(oh);
    check('accepted: the project is created and linked', (await j.text(oh)).includes(T('ho.projectCreated')));
    await j.shot(oh, 'accepted-project');
    clean(cm, 'handover (Commercial)'); clean(oh, 'handover (Operation)');

    // escalation to the CEO (handover B)
    await j.go(cm, `/handovers/${B.id}`);
    await cm.getByRole('button', { name: T('ho.edit') }).click(); await j.settle(cm);
    await dlg(cm).getByLabel(T('ho.services'), { exact: false }).first().fill('Payroll');
    await dlg(cm).getByLabel(T('ho.scope'), { exact: false }).first().fill('Twenty staff');
    await sheetBtn(cm, 'common.save').click(); await j.settle(cm);
    await cm.getByRole('button', { name: T('ho.submit') }).click(); await j.settle(cm);
    check('Commercial cannot escalate', await cm.getByRole('button', { name: T('ho.escalate') }).count() === 0);
    await j.go(oh, `/handovers/${B.id}`);
    await oh.getByRole('button', { name: T('ho.escalate') }).click(); await j.settle(oh);
    await dlg(oh).getByLabel(T('ho.escalateReason')).fill('Operation has not answered for a week');
    await sheetBtn(oh, 'ho.escalateSave').click(); await j.settle(oh);
    await j.go(ceo, `/handovers/${B.id}`);
    check('the CEO sees the escalation note', (await j.text(ceo)).includes('Operation has not answered for a week'));
    await j.shot(ceo, 'ceo-escalated');
    clean(ceo, 'escalation');

    // Operations privacy: no commercial pages, no prices, from the menu, the address bar and the API
    await j.go(om, '/');
    const nav = await om.locator('nav').first().innerText();
    check('Operation menu has no Quotations, Contracts, Leads or Payments', ![T('nav.quotations'), T('nav.contracts'), T('nav.leads'), T('nav.payments')].some((w) => nav.includes(w)));
    await j.go(om, '/quotations'); check('typing /quotations does not show quotations', !(await j.text(om)).includes('QT-'));
    await j.shot(om, 'no-quotations');
    const codes = [];
    for (const u of ['/quotations/', '/contracts/', '/payments/', '/leads/']) codes.push(await om.evaluate(async (x) => (await fetch('/api/v1' + x)).status, u));
    check('the API refuses Operation on quotations, contracts, payments and leads', codes.every((c) => c === 403 || c === 404), codes.join(','));
    const hoApi = await oh.evaluate(async (id) => JSON.stringify(await (await fetch(`/api/v1/handovers/${id}/`)).json()), A.id);
    check('the handover API carries no price field', !/price|amount|total|payment|currency/i.test(hoApi.replace(/special_requirements/g, '')));
    clean(om, 'privacy');

    // Project staffing: one primary, replacing needs a reason, support people
    await j.go(oh, '/projects');
    await oh.getByRole('button', { name: T('prj.staff') }).first().click(); await j.settle(oh);
    await dlg(oh).getByLabel(T('prj.person')).first().selectOption({ index: 1 });
    await j.shot(oh, 'staff-sheet');
    await dlg(oh).getByRole('button', { name: T('prj.assignPrimary') }).click(); await j.settle(oh);
    await j.settle(oh); check('first primary employee needs no reason', await dlg(oh).count() === 1 && !(await dlg(oh).innerText()).includes(T('prj.noPrimary')) && (await dlg(oh).innerText()).includes('Demo Operation'));
    await j.settle(oh);
    if (await dlg(oh).count() === 0) { await oh.getByRole('button', { name: T('prj.staff') }).first().click(); await j.settle(oh); }
    await oh.waitForTimeout(800);
    await dlg(oh).getByLabel(T('prj.person')).first().selectOption({ index: 1 });
    await dlg(oh).getByRole('button', { name: T('prj.replacePrimary') }).click(); await j.settle(oh);
    check('replacing the primary without a reason is refused', (await dlg(oh).innerText()).includes(T('prj.err.reason')) || (await dlg(oh).innerText()).includes(T('prj.reasonRequired')));
    await j.shot(oh, 'replace-needs-reason');
    await dlg(oh).getByLabel(T('prj.reason')).fill('On leave');
    await dlg(oh).getByRole('button', { name: T('prj.replacePrimary') }).click(); await j.settle(oh);
    await j.shot(oh, 'primary-replaced');
    clean(oh, 'staffing');

    // Objective 19: KYC with expiry and versions
    await j.go(oh, `/operation/${S.kyc}`);
    const item = oh.locator('li', { hasText: kycName }).first();
    await item.getByRole('button', { name: T('op.item.documents') }).click(); await j.settle(oh);
    await oh.locator('input[type=file]').first().setInputFiles(PDFFILE); await j.settle(oh);
    await j.shot(oh, 'kyc-uploaded');
    await sheetBtn(oh, 'common.done').click(); await j.settle(oh);
    check('the item says verifying needs the expiry date', (await item.innerText()).includes(T('op.expiry.needed')));
    await item.getByRole('button', { name: T('op.item.verify') }).click(); await j.settle(oh);
    await sheetBtn(oh, 'op.item.verify').click(); await j.settle(oh);
    check('verify without an expiry date is refused', await dlg(oh).count() === 1);
    await j.shot(oh, 'expiry-sheet');
    const nextYear = new Date(); nextYear.setFullYear(nextYear.getFullYear() + 1);
    await dlg(oh).getByLabel(T('op.expiry.date')).fill(nextYear.toISOString().slice(0, 10));
    await sheetBtn(oh, 'op.item.verify').click(); await j.settle(oh);
    check('verified, with the expiry date shown', (await oh.locator('li', { hasText: kycName }).first().innerText()).includes(T('op.expiry.on', { date: '' }).split(' ')[0]));
    await j.shot(oh, 'verified-with-expiry');
    await oh.locator('li', { hasText: kycName }).first().getByRole('button', { name: T('op.item.documents') }).click(); await j.settle(oh);
    await oh.locator('input[type=file]').first().setInputFiles(PDF2); await j.settle(oh);
    await sheetBtn(oh, 'common.done').click(); await j.settle(oh);
    const again = oh.locator('li', { hasText: kycName }).first();
    if (await again.getByRole('button', { name: T('op.item.verify') }).count()) {   // a new file puts the item back to "uploaded": verify it again, which keeps version 1 and makes version 2
      await again.getByRole('button', { name: T('op.item.verify') }).click(); await j.settle(oh);
      const later = new Date(); later.setFullYear(later.getFullYear() + 2);
      await dlg(oh).getByLabel(T('op.expiry.date')).fill(later.toISOString().slice(0, 10));
      await sheetBtn(oh, 'op.item.verify').click(); await j.settle(oh);
    }
    await oh.locator('li', { hasText: kycName }).first().getByRole('button', { name: T('op.item.documents') }).click(); await j.settle(oh);
    const vt = await dlg(oh).innerText();
    check('the second verification makes version 2 and keeps version 1 as replaced', vt.includes(T('op.version', { n: 2 })) && vt.includes(T('op.version', { n: 1 })) && vt.includes(T('op.version.superseded')), vt.replace(/\s+/g, ' ').slice(0, 160));
    await j.shot(oh, 'versions');
    clean(oh, 'KYC');
    for (const p of Object.values(j.sessions)) await p.close(); await j.browser.close();
  }
  console.log(`DONE ${lang}: ${fails} failure(s)`);
  process.exit(fails ? 1 : 0);
})().catch((e) => { console.log('SCRIPT ERROR', e.message.split('\n').slice(0, 4).join(' | ')); process.exit(2); });
