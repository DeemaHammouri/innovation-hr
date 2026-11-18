# Browser suite (Playwright)

Repeatable end-to-end tests that drive the real app in the installed Google Chrome (`channel: "chrome"`, no browser download).

    cd frontend
    npm run e2e                      # everything, English then Arabic
    npx playwright test e2e/04-accessibility.spec.ts --project=en-scan-a11y   # one file, one language. Projects: en-setup, en-leads, en-demo, en-keyboard, en-console, en-scan-a11y, en-scan-responsive, and the same with ar-. A project waits for the ones before it; add --no-deps to skip that on a database that is already set up (E2E_DB_DIR)

## What `npm run e2e` does

1. **Global setup** (`e2e/global-setup.ts`) makes a temporary folder with `e2e.sqlite3` (never `backend/db.sqlite3`), runs `migrate`, `seed` (departments, CEO) and `createsuperuser`, starts Django on **8100** (`runserver --noreload`), builds the app once into `frontend/.next-e2e` (rebuilt only when a source file is newer) and starts `next start` on **3100** with `BACKEND_URL=http://127.0.0.1:8100` (the `/api` proxy reads it at run time, so nothing is baked into the build).
2. Specs run in one worker, in file order, first as project `en`, then as project `ar` (the `lang` cookie is set; every account is switched to that language). Arabic runs on the database English left behind, which also proves the suite is repeatable on existing data.
3. **Global teardown** kills both servers and deletes the temporary folder.

Ports 8100 and 3100 must be free (the suite stops with a message if not). Ports 8000, 3000 and 8011 are never touched.

## Settings (environment variables)

| Variable | Meaning | Default |
| --- | --- | --- |
| `E2E_PYTHON` | Python that runs Django | `backend/.venv/Scripts/python.exe` (or `.venv/bin/python`) |
| `E2E_CHROME` | Path of a `chrome.exe` to use instead of the installed Chrome channel | unset |
| `E2E_DB_DIR` | Keep and reuse this folder for the database (not deleted at the end). Use it to repeat the suite on the same data | a fresh temporary folder |
| `E2E_REBUILD=1` | Force `next build` | rebuild only when sources changed |
| `E2E_EVIDENCE_DIR` | Where screenshots go | `docs/evidence/acceptance/e2e` |

## The specs

| File | Covers |
| --- | --- |
| `01-setup-journey.spec.ts` | Super Admin and CEO sign in; stamp upload; CEO creates the seven other staff accounts through Users, Add user; each signs in with the temporary password and is forced to choose a new one (weak refused, strong accepted); a second head, second Marketing, second Administration and forbidden roles are refused; the CEO cannot see the Super Admin. |
| `02-lead-journey.spec.ts` | Marketing imports a CSV (valid, invalid, duplicate rows; the preview shows them) and adds one lead; the Commercial head assigns; the Commercial member sets Waiting (date required), Rejected (reason required) and Initial acceptance; the converted lead is locked. |
| `03-demo-data.spec.ts` | Loads the development demo records into the throwaway database so later screens have data. |
| `04-accessibility.spec.ts` | axe-core (wcag2a, wcag2aa, wcag21aa), zero violations on every main screen each role can reach, the command palette, a modal, the language switcher, the login page. |
| `05-keyboard.spec.ts` | Keyboard only: login, global search (Ctrl+K, type, arrow, Enter), a form (tab order, error focus), a modal (focus trap, Escape returns focus), in both directions. |
| `06-responsive.spec.ts` | No horizontal page scroll at 375, 768 and 1280 px on every main screen of every role. |
| `07-console-hygiene.spec.ts` | Proves the guard below works. |

**Console hygiene applies to every test.** An automatic fixture fails a test on any `console.error`, uncaught page error or HTTP 5xx in any of its browser contexts. (A 4xx answer is allowed: negative tests provoke them on purpose.)

## Repeatability

- The setup journey creates an account the first time and, if it already exists, uses *Reset password* in the UI to get a new temporary password, then runs the same forced-change steps.
- Leads, companies and phone numbers carry a per-run suffix.
- Run order matters: `01` creates the accounts and `02` the leads that `03` to `06` use. Run a later file alone only on a database that already went through `01` to `03` (`E2E_DB_DIR`).

## Evidence

Screenshots are written to `docs/evidence/acceptance/e2e/<lang>-<width>-<name>.png` at 375, 768 and 1280 px. The HTML report is in `frontend/playwright-report`, traces of failures in `frontend/test-results`.

Test accounts (made by the suite, throwaway database only): `e2e-<role>@e2e.test`, password in `support/env.ts`.
