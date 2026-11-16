const { chromium } = require('playwright-core');
const fs = require('fs');
const loc = { en: require('C:/Users/user/Desktop/Innovation-hr/frontend/src/locales/en.json'), ar: require('C:/Users/user/Desktop/Innovation-hr/frontend/src/locales/ar.json') };
exports.mk = async (lang, width = 1280, shotDir = 'j') => {
  fs.mkdirSync(shotDir, { recursive: true });
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
  const interp = (text, v) => text.replace(/\{(\w+)((?:\|[^|{}]*){2,4})\}/g, (whole, k, rest) => { const forms = rest.slice(1).split('|'); const shown = String(v[k] ?? ''); const n = Number(shown.replace(/,/g, '')); if (Number.isNaN(n)) return whole; let pick = forms[forms.length - 1]; if (forms.length === 2) pick = n === 1 ? forms[0] : forms[1]; else if (forms.length === 4) pick = lang === 'ar' ? (n === 1 ? forms[0] : n === 2 ? forms[1] : (n % 100 >= 3 && n % 100 <= 10) ? forms[2] : forms[3]) : (n === 1 ? forms[0] : forms[3]); return pick.replace(/#/g, shown); }).replace(/\{(\w+)\}/g, (_, n) => v[n] ?? '');
  const T = (k, v = {}) => interp(loc[lang][k] ?? loc.en[k] ?? k, v);
  const results = []; const sessions = {};
  const ok = (name, cond, extra = '') => { results.push({ name, pass: !!cond, extra }); console.log((cond ? 'PASS ' : 'FAIL ') + name + (extra ? ' | ' + extra : '')); };
  async function as(email, pw = 'Demo-12345') {
    if (sessions[email]) return sessions[email];
    const ctx = await browser.newContext({ viewport: { width, height: 900 } });
    await ctx.addCookies([{ name: 'lang', value: lang, url: 'http://localhost:3000' }]);
    const page = await ctx.newPage(); page.errs = [];
    page.on('console', m => { if (m.type() === 'error' && !/status of 4\d\d/.test(m.text())) page.errs.push(m.text().slice(0, 160)); });
    page.on('pageerror', e => page.errs.push('PAGEERROR ' + e.message.slice(0, 160)));
    page.on('response', r => { if (r.status() >= 500) page.errs.push('HTTP ' + r.status() + ' ' + r.url()); });
    await page.goto('http://localhost:3000/login');
    await page.fill('input[autocomplete=username]', email); await page.fill('input[type=password]', pw);
    await page.click('button[type=submit]');
    await page.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 15000 });
    await settle(page);
    return (sessions[email] = page);
  }
  const settle = async (page) => { await page.waitForLoadState('networkidle').catch(() => {}); await page.waitForTimeout(400); };
  const go = async (page, path) => { api.last = page; await page.goto('http://localhost:3000' + path); await settle(page); };
  const btn = (page, key, vars) => page.getByRole('button', { name: T(key, vars), exact: false }).first();
  const click = async (page, key, vars) => { await btn(page, key, vars).click(); await settle(page); };
  const dump = async (page) => console.log('BUTTONS:', await page.$$eval('button:visible, a[role=button]:visible, main a:visible', els => els.map(e => (e.getAttribute('aria-label') || e.innerText || '').trim().replace(/\s+/g, ' ')).filter(Boolean).slice(0, 40).join(' || ')));
  const shot = (page, name) => page.screenshot({ path: `${shotDir}/${lang}-${width}-${name}.png` });
  const text = (page) => page.evaluate(() => document.body.innerText);
  const L = (en) => { const k = Object.keys(loc.en).find(x => loc.en[x] === en); if (!k) throw new Error('no key for ' + en); return loc[lang][k] ?? en; };
  const api = { L, browser, T, ok, as, go, btn, click, dump, shot, text, settle, results, sessions, lang };
  return api;
};
