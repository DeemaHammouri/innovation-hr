// Phase 5 browser proof, objective 22 (general tasks): run once per language.
//   PROOF_SEED=<seed json> PROOF_OUT=<folder> node phase5.js en
// 375 and 768 check layout and console errors; 1280 walks the flow with screenshots.
const { mk } = require('./jlib');
const fs = require('fs');
const SEED = JSON.parse(fs.readFileSync(process.env.PROOF_SEED, 'utf8'));
const OUT = process.env.PROOF_OUT;
const lang = process.argv[2] || 'en';
const S = SEED[lang];
fs.mkdirSync(OUT, { recursive: true });
const REAL = `${OUT}/${lang}-task-file.pdf`;
const FAKE = `${OUT}/${lang}-task-fake.pdf`;
fs.writeFileSync(REAL, '%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n');
fs.writeFileSync(FAKE, 'MZ this is a program renamed to pdf');

const setLang = async (page) => {
  const name = lang === 'ar' ? 'عربي' : 'EN';
  const sw = page.getByRole('radio', { name }).first();
  if (await sw.count() && (await sw.getAttribute('aria-checked')) !== 'true') { await sw.click(); await page.waitForTimeout(900); await page.waitForLoadState('networkidle').catch(() => {}); }
};
const noOverflow = (page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
const dlg = (p) => p.locator('[role=dialog]');
const row = (page, title) => page.locator('li', { hasText: title }).first();
const G = {};
const act = async (page, title, name) => {   // the list reloads now and then; retry until the menu stays open
  for (let i = 0; i < 4; i++) {
    await page.waitForTimeout(500);
    await row(page, title).getByRole('button', { name: G.T('common.actions') }).click();
    try { await page.getByRole('menuitem', { name }).first().click({ timeout: 4000 }); return; } catch { await page.keyboard.press('Escape'); }
  }
  throw new Error('menu item not clickable: ' + name);
};
const iso = (days) => { const d = new Date(); d.setDate(d.getDate() + days); return d.toLocaleDateString('en-CA'); };

(async () => {
  let fails = 0;
  for (const width of [375, 768, 1280]) {
    const j = await mk(lang, width, OUT);
    const T = j.T; G.T = T; const tag = `${lang} ${width}`;
    const check = (name, cond, extra) => { if (!cond) fails++; j.ok(`${tag} ${name}`, cond, extra); };
    const clean = (page, label) => { check(`${label}: no console error`, page.errs.length === 0, page.errs.join(' ; ')); page.errs.length = 0; };
    const api = (page, path) => page.evaluate(async (p) => { const r = await fetch('/api/v1' + p); return { status: r.status, body: await r.json().catch(() => null) }; }, path);
    const view = async (page, path, name, expect) => {
      await j.go(page, path); await setLang(page); await j.settle(page);
      check(`${name}: no horizontal scroll`, await noOverflow(page));
      if (expect) check(`${name}: shows "${expect}"`, (await j.text(page)).includes(expect));
      await j.shot(page, name); clean(page, name);
    };
    const ceo = await j.as('ceo@innovation.test'); await setLang(ceo);
    const oh = await j.as('operation.head@demo.test'); await setLang(oh);
    const om = await j.as('operation.member@demo.test'); await setLang(om);
    const cm = await j.as('commercial.member@demo.test'); await setLang(cm);

    await view(ceo, '/tasks?view=team', 'tasks-ceo', S.titles.open);
    await view(oh, '/tasks?view=team', 'tasks-head', S.titles.open);
    await view(om, '/tasks?show=all', 'tasks-member', S.titles.late);
    await j.go(ceo, '/tasks'); await ceo.getByRole('button', { name: T('gt.new') }).click(); await j.settle(ceo);
    check('new-task sheet: no horizontal scroll', await noOverflow(ceo));
    await j.shot(ceo, 'new-task-sheet'); clean(ceo, 'new-task sheet');
    await dlg(ceo).getByRole('button', { name: T('common.cancel') }).click(); await j.settle(ceo);
    if (width !== 1280) { for (const p of Object.values(j.sessions)) await p.close(); await j.browser.close(); continue; }

    // ---- giving a task: the CEO, with the form refusing what is missing
    await ceo.getByRole('button', { name: T('gt.new') }).click(); await j.settle(ceo);
    await dlg(ceo).getByRole('button', { name: T('common.save') }).click(); await j.settle(ceo);
    const refused = await dlg(ceo).innerText();
    check('empty form: title, person and deadline are all refused', [T('gt.err.title'), T('gt.err.assignee'), T('gt.err.deadline')].every((m) => refused.includes(m)));
    await j.shot(ceo, 'new-task-refused');
    const title = 'Proof: prepare the VAT file';
    await dlg(ceo).getByLabel(T('gt.title.field'), { exact: false }).first().fill(title);
    await dlg(ceo).getByLabel(T('gt.details')).fill('Use the March figures.');
    const sel = dlg(ceo).getByLabel(T('gt.assignee'), { exact: false }).first();
    const optValue = await sel.evaluate((el) => [...el.options].find((o) => o.text.includes('Demo Operation Member'))?.value);
    check('the CEO can pick someone from any department', !!optValue && (await sel.evaluate((el) => [...el.options].some((o) => o.text.includes('Demo Commercial Member')))));
    await sel.selectOption(optValue);
    await dlg(ceo).getByLabel(T('gt.deadline'), { exact: false }).first().fill(iso(3));
    await j.shot(ceo, 'new-task-filled');
    await dlg(ceo).getByRole('button', { name: T('common.save') }).click(); await j.settle(ceo);
    await j.go(ceo, '/tasks?view=given');
    check('the task appears under "given by me"', (await j.text(ceo)).includes(title));
    await j.shot(ceo, 'given-by-ceo');
    check('the CEO has no "Mark as done" on a task given to someone else', await row(ceo, title).getByRole('button', { name: T('gt.markDone') }).count() === 0);
    clean(ceo, 'giving');

    // ---- the department head: sees the team, gives only inside the department
    await j.go(oh, '/tasks?view=team');
    check('the head sees the CEO\'s task for their department\'s person', (await j.text(oh)).includes(title));
    check('the head does not see another department\'s task', !(await j.text(oh)).includes(S.titles.other));
    await oh.getByRole('button', { name: T('gt.new') }).click(); await j.settle(oh);
    const headOptions = await dlg(oh).getByLabel(T('gt.assignee'), { exact: false }).first().evaluate((el) => [...el.options].map((o) => o.text));
    check('the head can pick only people of their own department', headOptions.some((o) => o.includes('Demo Operation Member')) && !headOptions.some((o) => o.includes('Commercial') || o.includes('HR ') || o.includes('Marketing')), headOptions.join(' | '));
    await j.shot(oh, 'head-new-task');
    await dlg(oh).getByRole('button', { name: T('common.cancel') }).click(); await j.settle(oh);
    // change the deadline of an open task
    await act(oh, S.titles.open, T('common.edit')); await j.settle(oh);
    await dlg(oh).getByLabel(T('gt.deadline'), { exact: false }).first().fill(iso(9));
    await j.shot(oh, 'edit-deadline');
    await dlg(oh).getByRole('button', { name: T('common.save') }).click(); await j.settle(oh);
    check('the deadline change is saved and shown', (await row(oh, S.titles.open).innerText()).length > 0 && (await api(oh, `/tasks/${S.ids.open}/`)).body.deadline === iso(9));
    clean(oh, 'head');

    // ---- the member: sees only their own, finishes them, cannot give
    await j.go(om, '/tasks');
    const mt = await j.text(om);
    check('the member sees their tasks', mt.includes(title) && mt.includes(S.titles.late));
    check('the member sees no other department\'s task', !mt.includes(S.titles.other));
    check('the member has no "New task" button and no team views', await om.getByRole('button', { name: T('gt.new') }).count() === 0 && await om.getByRole('radio', { name: T('gt.view.team') }).count() === 0);
    check('an overdue task is marked as overdue', (await row(om, S.titles.late).innerText()).includes(T('gt.overdue')));
    await j.shot(om, 'member-tasks');
    const apiOther = await api(om, `/tasks/${S.ids.other}/`);
    check('the API answers 404 for another department\'s task', apiOther.status === 404, String(apiOther.status));
    const apiGive = await om.evaluate(async () => { const r = await fetch('/api/v1/tasks/', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': (document.cookie.match(/(?:^|; )csrf_token=([^;]*)/) || [])[1] || '' }, body: JSON.stringify({ title: 'x', assignee: 1, deadline: '2999-01-01' }) }); return r.status; });
    check('the API refuses a member who tries to give a task', apiGive === 403, String(apiGive));
    // notes and files: a program renamed to .pdf is refused, a real PDF is accepted
    await act(om, S.titles.open, T('gt.details.open')); await j.settle(om);
    await dlg(om).getByRole('tab', { name: T('record.tab.files') }).click(); await j.settle(om);
    await dlg(om).locator('input[type=file]').first().setInputFiles(FAKE); await j.settle(om);
    check('a fake PDF is refused (checked by its first bytes)', !(await dlg(om).innerText()).includes(`${lang}-task-fake.pdf`));
    await j.shot(om, 'file-fake-refused');
    await dlg(om).locator('input[type=file]').first().setInputFiles(REAL); await j.settle(om);
    check('a real PDF is accepted and listed', (await dlg(om).innerText()).includes(`${lang}-task-file.pdf`));
    await j.shot(om, 'file-accepted');
    await dlg(om).getByRole('tab', { name: T('record.tab.activity') }).click(); await j.settle(om);
    check('the history shows who gave the task', (await dlg(om).innerText()).includes(T('activity.gtask_created')));
    await j.shot(om, 'task-history');
    await dlg(om).getByRole('button', { name: T('common.done') }).last().click(); await j.settle(om);
    // finish the late one: it becomes "Done late"
    await row(om, S.titles.late).getByRole('button', { name: T('gt.markDone') }).click(); await j.settle(om);
    await j.go(om, '/tasks?show=all');
    check('the late task is shown as "Done late"', (await row(om, S.titles.late).innerText()).includes(T('gt.doneLate')));
    await j.shot(om, 'done-late');
    // counters on screen equal the counters from the server
    const server = (await api(om, '/tasks/counters/')).body.mine;
    const tiles = {};
    for (const k of ['open', 'due_today', 'overdue', 'done', 'done_late']) tiles[k] = Number((await om.locator('section[aria-label] > div', { has: om.getByText(T(`gt.k.${k}`), { exact: true }) }).first().locator('p.tnum').first().innerText()).replace(/[^\d]/g, ''));
    check('the five counters on screen equal the server\'s numbers', Object.keys(tiles).every((k) => tiles[k] === server[k]), JSON.stringify([tiles, server]));
    // My Work lists the task on the home page
    await j.go(om, '/');
    const mw = (await api(om, '/my-work/')).body;
    const mine = JSON.stringify(mw).includes(S.titles.today) && JSON.stringify(mw).includes('"kind":"gtask"');
    check('My Work (API) lists the task due today, and the Tasks menu entry carries a count', mine && (await om.locator('nav a[href="/tasks"], aside a[href="/tasks"]').first().innerText()).replace(/\D/g, '') !== '', JSON.stringify(mw).slice(0, 80));
    await j.shot(om, 'my-work');
    clean(om, 'member');
    // the other-department person never sees these tasks
    await j.go(cm, '/tasks?show=all');
    check('a Commercial member sees only their own task', !(await j.text(cm)).includes(title) && (await j.text(cm)).includes(S.titles.other));
    clean(cm, 'commercial');
    for (const p of Object.values(j.sessions)) await p.close(); await j.browser.close();
  }
  console.log(`DONE ${lang}: ${fails} failure(s)`);
  process.exit(fails ? 1 : 0);
})().catch((e) => { console.log('SCRIPT ERROR', e.message.split('\n').slice(0, 4).join(' | ')); process.exit(2); });
