const { mk } = require('./jlib');
(async () => {
  const J = await mk('en', 1280, 'ck');
  const p = await J.as('ceo@innovation.test', 'QaCeo-12345');
  const seen = await p.evaluate(() => ({ cookie: document.cookie, ls: Object.keys(localStorage), ss: Object.keys(sessionStorage), url: location.pathname, h1: document.querySelector('h1')?.textContent }));
  console.log('page sees:', JSON.stringify(seen));
  const ctxCookies = await p.context().cookies();
  console.log('browser jar:', ctxCookies.map(c => `${c.name} httpOnly=${c.httpOnly} sameSite=${c.sameSite} path=${c.path}`).join(' | '));
  J.ok('page script cannot read access/refresh tokens', !/access_token|refresh_token/.test(seen.cookie));
  J.ok('nothing token-like in localStorage/sessionStorage', seen.ls.length + seen.ss.length === 0 || ![...seen.ls, ...seen.ss].some(k => /token|access|refresh/i.test(k)), JSON.stringify([...seen.ls, ...seen.ss]));
  J.ok('token cookies are HttpOnly', ctxCookies.filter(c => /_token$/.test(c.name) && c.name !== 'csrf_token').every(c => c.httpOnly));
  const noCsrf = await p.evaluate(async () => (await fetch('/api/v1/auth/me/', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: '{"preferred_language":"ar"}', credentials: 'same-origin' })).status);
  J.ok('PATCH without the CSRF header is refused (403)', noCsrf === 403, String(noCsrf));
  const withCsrf = await p.evaluate(async () => { const t = document.cookie.match(/csrf_token=([^;]+)/)[1]; return (await fetch('/api/v1/auth/me/', { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': t }, body: '{"preferred_language":"en"}', credentials: 'same-origin' })).status; });
  J.ok('PATCH with the CSRF header works (200)', withCsrf === 200, String(withCsrf));
  // reload keeps the session (cookies, no storage)
  await p.reload(); await p.waitForTimeout(1500);
  J.ok('session survives a reload', !(await p.url()).includes('/login'), p.url());
  // refresh rotation through the browser
  const before = (await p.context().cookies()).find(c => c.name === 'refresh_token').value;
  const r = await p.evaluate(async () => { const t = document.cookie.match(/csrf_token=([^;]+)/)[1]; return (await fetch('/api/v1/auth/refresh/', { method: 'POST', headers: { 'X-CSRF-Token': t }, credentials: 'same-origin' })).status; });
  const after = (await p.context().cookies()).find(c => c.name === 'refresh_token').value;
  J.ok('refresh rotates the refresh cookie', r === 200 && before !== after, String(r));
  // sign out through the UI path
  await p.evaluate(async () => { const t = document.cookie.match(/csrf_token=([^;]+)/)[1]; await fetch('/api/v1/auth/logout/', { method: 'POST', headers: { 'X-CSRF-Token': t }, credentials: 'same-origin' }); });
  const me = await p.evaluate(async () => (await fetch('/api/v1/auth/me/', { credentials: 'same-origin' })).status);
  J.ok('after logout /auth/me/ is 401', me === 401, String(me));
  console.log('errors:', JSON.stringify(p.errs));
  await J.browser.close();
})();
