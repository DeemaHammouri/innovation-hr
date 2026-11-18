# Contributing

## Branches

Work on a branch, never directly on `main`. Name it `<type>/<short-topic>`:

- `feat/recurring-day-rules`
- `fix/lockout-counter-race`
- `docs/readme-rewrite`
- `test/e2e-lead-journey`
- `chore/pin-requirements`

## Commits

One logical change per commit, and every commit leaves the tests passing. The subject says what the system does now, in plain words, and names the audit item or area when there is one:

```
Notifications are rendered in the reader's current language: kind and parameters are stored (P16)
Recurrence engine, step 2: rules store a day rule and weekend policy (P31)
```

Explain *why* in the body when it is not obvious. Do not commit `.env` files, `db.sqlite3`, `*.backup`, uploaded files or credentials (`python scripts/secret_scan.py` checks).

## Run the tests

Backend (Python 3.11+, from `backend/` with the virtualenv active):

```bash
pip install -r requirements.txt -r requirements-dev.txt
python manage.py test --noinput          # whole suite on SQLite (python -m pytest -q runs the same tests)
python manage.py makemigrations --check --dry-run
```

To check the database-specific parts (row locks, unique-index races, triggers) run the same command against PostgreSQL by setting `DB_ENGINE=postgres` and the `DB_*` variables from `backend/.env.example`.

Frontend (Node 20+, from `frontend/`):

```bash
npm install
npx tsc --noEmit && npm run lint && npm run i18n:check
npm test                                  # Vitest
npm run e2e                               # Playwright in Chrome; uses ports 8100 and 3100
```

## Rules of the house

- Every user-visible string goes in `frontend/src/locales/en.json` **and** `ar.json`; `npm run i18n:check` must pass. Use logical Tailwind classes (`ms-`, `pe-`) so Arabic RTL works.
- Every endpoint declares the capabilities it needs and fails closed; add a denial test. Operation roles must never receive prices, contract values or payments.
- A bug fix starts with a test that reproduces it.
- Settings go through environment variables and are documented in `backend/.env.example` and `docs/DEPLOYMENT.md`.

## Pull requests

Fill in the template. Keep the PR to one topic. Link the audit item (`docs/AUDIT_REPORT.md`) it addresses, if any.
