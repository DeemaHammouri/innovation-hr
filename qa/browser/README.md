# Browser proofs

Playwright scripts that drive the real app in Chrome. They are evidence tools, not part of the unit suites.

Run against a throwaway database, never `db.sqlite3`:

1. Backend: `DJANGO_DB_PATH=<temp>.sqlite3 python manage.py migrate && ... runserver 8000 --noreload`, then create a CEO (`ceo@innovation.test`).
2. Frontend: `npm run build && npm run start` (port 3000).
3. From this folder: `npm i playwright-core` once, then `node phase1.js` and `node cookies.js`.

`jlib.js` holds the helper (sign in, screenshots, pass/fail lines). It points at a local Chrome and at `frontend/src/locales`; edit the two paths at its top for another machine.
