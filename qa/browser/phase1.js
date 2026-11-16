const { mk } = require('./jlib');
const BASE = 'http://localhost:3000';
(async () => {
  const J = await mk('en', 1280, 'p1');
  // 1. the server renders lang and dir before any script runs
  const html = async (cookie) => (await (await fetch(BASE + '/login', { headers: cookie ? { cookie } : {} })).text()).match(/<html[^>]*>/)[0];
  const en = await html('lang=en'), ar = await html('lang=ar');
  J.ok('server HTML: English is lang=en dir=ltr', /lang="en"/.test(en) && /dir="ltr"/.test(en), en);
  J.ok('server HTML: Arabic is lang=ar dir=rtl', /lang="ar"/.test(ar) && /dir="rtl"/.test(ar), ar);

  // 2. CEO signs in, makes a user (server-made temporary password), sets a username on another
  const ceo = await J.as('ceo@innovation.test', 'QaCeo-12345');
  const call = (p, method, url, body) => p.evaluate(async ([method, url, body]) => {
    const t = document.cookie.match(/csrf_token=([^;]+)/)?.[1] ?? '';
    const r = await fetch('/api/v1' + url, { method, headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': t }, credentials: 'same-origin', body: body ? JSON.stringify(body) : undefined });
    return { status: r.status, body: await r.json().catch(() => null) };
  }, [method, url, body]);
  const depts = (await call(ceo, 'GET', '/departments/')).body;
  const hr = depts.find(d => d.name === 'HR').id;
  const stamp = Date.now() % 100000;
  const email = `p1user${stamp}@demo.test`;
  const made = await call(ceo, 'POST', '/users/', { full_name: 'Phase One', email, department: hr, role: 'hr_member', username: `P1User${stamp}` });
  J.ok('create returns 201 and a 16-character temporary password', made.status === 201 && made.body.temporary_password?.length === 16, `${made.status}`);
  const temp = made.body.temporary_password;
  const again = await call(ceo, 'GET', `/users/${made.body.id}/`);
  J.ok('the password is not shown again', !JSON.stringify(again.body).includes(temp));

  // 3. new person signs in by USERNAME in other case; forced change; weak then strong
  const fresh = await J.browser.newContext({ viewport: { width: 1280, height: 900 } });
  const p = await fresh.newPage();
  await p.goto(BASE + '/login');
  await p.fill('input[autocomplete=username]', `P1USER${stamp}`.toLowerCase().toUpperCase());
  await p.fill('input[type=password]', temp);
  await p.click('button[type=submit]');
  await p.waitForURL(u => u.pathname.startsWith('/set-password'), { timeout: 15000 });
  J.ok('username (any case) signs in and lands on the forced password change', true, p.url());
  const blocked = await call(p, 'GET', '/leads/');
  J.ok('other endpoints are closed until the password is changed (403)', blocked.status === 403 && blocked.body.error?.code === 'permission_denied', JSON.stringify(blocked.body));
  const weak = await call(p, 'POST', '/auth/change-password/', { new_password: 'Short-1a', confirm_password: 'Short-1a' });
  J.ok('an 8-character password is refused with the envelope + field error', weak.status === 400 && weak.body.error.fields?.new_password, JSON.stringify(weak.body));
  await p.fill('input[autocomplete=new-password] >> nth=0', 'Phase-One-Strong-77');
  await p.fill('input[autocomplete=new-password] >> nth=1', 'Phase-One-Strong-77');
  await p.click('button[type=submit]');
  await p.waitForURL(u => u.pathname === '/', { timeout: 15000 });
  J.ok('a strong password unlocks the app', true);
  await p.waitForTimeout(800);

  // 4. language: switch to Arabic in the UI, layout flips, saved on the profile
  const dirBefore = await p.evaluate(() => document.documentElement.dir);
  const sideBefore = await p.evaluate(() => { const a = document.querySelector('aside,nav'); return a ? a.getBoundingClientRect().left : -1; });
  await p.getByRole('radio', { name: 'العربية' }).first().click();
  await p.waitForTimeout(1200);
  const dirAfter = await p.evaluate(() => document.documentElement.dir);
  const sideAfter = await p.evaluate(() => { const a = document.querySelector('aside,nav'); return a ? a.getBoundingClientRect().left : -1; });
  J.ok('switching to Arabic flips dir to rtl', dirBefore === 'ltr' && dirAfter === 'rtl', `${dirBefore} -> ${dirAfter}`);
  J.ok('the sidebar moves to the other side', sideBefore < 100 && sideAfter > 400, `${sideBefore} -> ${sideAfter}`);
  await p.screenshot({ path: 'p1/ar-home.png' });
  const prof = await call(p, 'GET', '/auth/me/');
  J.ok('language is saved on the profile', prof.body.preferred_language === 'ar', prof.body.preferred_language);

  // 5. a FRESH browser (no cookies) signs in and gets Arabic from the profile
  await call(p, 'POST', '/auth/logout/');
  const other = await J.browser.newContext({ viewport: { width: 1280, height: 900 } });
  const q = await other.newPage();
  await q.goto(BASE + '/login');
  const before = await q.evaluate(() => document.documentElement.dir);
  await q.fill('input[autocomplete=username]', email);
  await q.fill('input[type=password]', 'Phase-One-Strong-77');
  await q.click('button[type=submit]');
  await q.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 15000 });
  await q.waitForTimeout(1200);
  const after = await q.evaluate(() => ({ lang: document.documentElement.lang, dir: document.documentElement.dir }));
  J.ok('fresh browser: starts English, becomes Arabic/RTL after sign-in', before === 'ltr' && after.lang === 'ar' && after.dir === 'rtl', `${before} -> ${JSON.stringify(after)}`);
  await q.screenshot({ path: 'p1/fresh-ar.png' });
  // 6. lockout in the browser: 5 wrong, then the right password is refused
  const w = await other.newPage();
  await w.goto(BASE + '/login');
  const codes = await w.evaluate(async (id) => { const out = []; for (let i = 0; i < 6; i++) { const r = await fetch('/api/v1/auth/login/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ identifier: id, password: i < 5 ? 'wrong-wrong-wrong' : 'Phase-One-Strong-77' }) }); out.push(r.status); } return out; }, email);
  J.ok('5 wrong passwords, then the right one is blocked (401 x5, 429)', JSON.stringify(codes) === '[401,401,401,401,401,429]', JSON.stringify(codes));
  console.log('errors:', JSON.stringify(ceo.errs), JSON.stringify(p.errs || []));
  const fails = J.results.filter(r => !r.pass);
  console.log(fails.length ? `FAILED ${fails.length}` : `ALL ${J.results.length} PASSED`);
  await J.browser.close();
})();
