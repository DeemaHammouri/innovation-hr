const { mk } = require('./jlib');
const fs = require('fs');
const SEED = JSON.parse(fs.readFileSync('C:/Users/user/AppData/Local/Temp/claude/a2f787886d6edfd6/cb914acc-80a7-410e-b114-ceebcd1659b3/scratchpad/p3a.json', 'utf8'));
const SHOTS = 'C:/Users/user/Desktop/Innovation-hr/qa/browser/phase3-obj13';
const NEWPW = 'Portal-Secret-2026!';

async function setLang(page, lang) {
  const name = lang === 'ar' ? 'عربي' : 'EN';
  const sw = page.getByRole('radio', { name }).first();
  if (await sw.count() && (await sw.getAttribute('aria-checked')) !== 'true') { await sw.click(); await page.waitForTimeout(900); await page.waitForLoadState('networkidle').catch(() => {}); }
}
const noOverflow = (page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
const apiCall = (page, method, url, body) => page.evaluate(async ([m, u, b]) => {
  const r = await fetch('/api/v1' + u, { method: m, headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': (document.cookie.match(/(?:^|; )csrf_token=([^;]*)/) || [])[1] || '' }, body: b ? JSON.stringify(b) : undefined });
  let j = null; try { j = await r.json(); } catch {}
  return { status: r.status, body: j };
}, [method, url, body]);

(async () => {
  let failed = 0;
  for (const lang of ['en', 'ar']) {
    const S = SEED[lang];
    for (const width of [1280, 768, 375]) {
      const j = await mk(lang, width, SHOTS);
      const tag = `${lang} ${width}`;
      // ---- the client signs in
      let client;
      if (width === 1280) {
        client = await j.as(S.a.email, S.a.password);               // first sign-in with the emailed temporary password
        j.ok(`${tag} first sign-in is sent to set a new password`, client.url().includes('/set-password'));
        await setLang(client, lang);
        await j.shot(client, 'client-set-password');
        await client.getByLabel(j.T('setpw.new'), { exact: false }).first().fill(NEWPW);
        await client.getByLabel(j.T('setpw.confirm'), { exact: false }).first().fill(NEWPW);
        await client.getByRole('button', { name: j.T('setpw.save') }).click();
        await client.waitForURL(u => !u.pathname.startsWith('/set-password'), { timeout: 15000 }); await j.settle(client);
      } else {
        client = await j.as(S.a.email, NEWPW);
      }
      j.ok(`${tag} the client lands on /portal`, new URL(client.url()).pathname.startsWith('/portal'), client.url());
      await setLang(client, lang);
      const txt = await j.text(client);
      j.ok(`${tag} the portal shows their own company`, txt.includes(S.a.company));
      j.ok(`${tag} the portal shows no other client's company`, !txt.includes(S.b.company) && !txt.includes(S.none.company));
      j.ok(`${tag} the client has no staff navigation`, !(await client.getByRole('link', { name: j.T('nav.leads') }).count()) && !(await client.getByRole('link', { name: j.T('nav.clients') }).count()));
      j.ok(`${tag} no horizontal scroll on the portal`, await noOverflow(client));
      await j.shot(client, 'client-portal');
      await j.go(client, '/leads');
      j.ok(`${tag} a client typing /leads is sent back to /portal`, new URL(client.url()).pathname.startsWith('/portal'), client.url());
      await j.go(client, `/clients/${S.b.client}`);
      j.ok(`${tag} a client opening another client's page is sent back to /portal`, new URL(client.url()).pathname.startsWith('/portal'), client.url());
      const other = await apiCall(client, 'GET', `/clients/${S.b.client}/`);
      j.ok(`${tag} the API refuses a client asking for another client`, other.status === 403 || other.status === 404, String(other.status));
      const me = await apiCall(client, 'GET', '/portal/me/');
      j.ok(`${tag} /portal/me returns only their own company`, me.status === 200 && me.body.client.id === S.a.client, JSON.stringify(me.body).slice(0, 80));

      // ---- staff: converted lead is locked
      const head = await j.as('commercial.head@demo.test'); await setLang(head, lang);
      await j.go(head, `/leads/${S.a.lead}`);
      const lt = await j.text(head);
      j.ok(`${tag} the converted lead shows it is now a client`, lt.includes(j.T('lead.converted')));
      j.ok(`${tag} no edit control on the converted lead`, !(await head.getByRole('button', { name: j.T('lead.edit') }).count()) && !(await head.getByRole('link', { name: j.T('lead.edit') }).count()));
      await j.shot(head, 'lead-converted');
      if (width === 1280) {
        for (const [m, u, b] of [['PATCH', `/leads/${S.a.lead}/`, { company_name: 'Hacked' }], ['POST', `/leads/${S.a.lead}/archive/`, { reason: 'x' }], ['POST', `/leads/${S.a.lead}/interactions/`, { type: 'call', outcome: 'rejected' }]]) {
          const r = await apiCall(head, m, u, b);
          j.ok(`${tag} ${m} ${u} -> 409 lead_converted`, r.status === 409 && r.body && r.body.error && r.body.error.code === 'lead_converted', JSON.stringify(r.body).slice(0, 100));
        }
      }

      // ---- staff: portal status on the client record (sent / no email / email in use)
      const ceo = await j.as('ceo@demo.test'); await setLang(ceo, lang);
      for (const [k, st] of [['b', 'sent'], ['none', 'no_email'], ['used', 'email_in_use']]) {
        await j.go(ceo, `/clients/${S[k].client}`);
        const ct = await j.text(ceo);
        j.ok(`${tag} client record (${k}) says: ${st}`, ct.includes(j.T(`clients.portal.${st}`)));
        j.ok(`${tag} client record (${k}) no horizontal scroll`, await noOverflow(ceo));
        if (k !== 'b') await j.shot(ceo, `client-${st}`);
      }
      // ---- internal user management never lists clients
      await j.go(ceo, '/users');
      const ut = await j.text(ceo);
      j.ok(`${tag} client accounts are not in the users page`, !ut.includes(S.a.email) && !ut.includes(S.b.email));
      const list = await apiCall(ceo, 'GET', '/users/?page_size=500');
      const rows = Array.isArray(list.body) ? list.body : list.body.results;
      j.ok(`${tag} the users API lists no client account`, rows.length > 0 && !rows.some(u => [S.a.email, S.b.email].includes(u.email) || u.role_key === 'client'));
      const roles = await apiCall(ceo, 'GET', '/roles/');
      j.ok(`${tag} the role list has no client role`, !roles.body.some(r => r.key === 'client'));
      await j.shot(ceo, 'users');
      for (const p of Object.values(j.sessions)) if (p.errs.length) { j.ok(`${tag} no console or 5xx errors`, false, p.errs.join(' | ')); }
      failed += j.results.filter(r => !r.pass).length;
      await j.browser.close();
    }
  }
  console.log(failed ? `FAILED ${failed}` : 'ALL PASSED');
})();
