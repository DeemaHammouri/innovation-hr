# Browser proofs

Playwright scripts that drive the real app in Chrome. They are evidence tools, not part of the unit suites.

Run against a throwaway database, never `db.sqlite3`:

1. Backend: `DJANGO_DB_PATH=<temp>.sqlite3 python manage.py migrate && ... runserver 8000 --noreload`, then create a CEO (`ceo@innovation.test`).
2. Frontend: `npm run build && npm run start` (port 3000).
3. From this folder: `npm i playwright-core` once, then `node phase1.js` and `node cookies.js`.

`jlib.js` holds the helper (sign in, screenshots, pass/fail lines). It points at a local Chrome and at `frontend/src/locales`; edit the two paths at its top for another machine.

Phase 4 proofs (objectives 18-21, English and Arabic at 375, 768 and 1280): `sh run-phase4.sh <suffix> <scratch folder>` seeds fresh data into the throwaway database (scripts `seed_proof.py` and `seed_proof2.py` live in the scratch folder), runs `phase4a.js` (objectives 18-19) and `phase4.js` (objectives 20-21), and `compare_exports.py` checks that the JSON, CSV, Excel and PDF of the Operation report carry the same numbers. Output and screenshots go to `docs/evidence/phase4/`.
