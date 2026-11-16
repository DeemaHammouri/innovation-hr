# Innovation Accounting Solutions: internal workflow platform

Lead-to-cash workflow for five departments (Administration/CEO, Marketing, Commercial, HR, Operation), a client portal, English and Arabic (RTL).

- **Backend:** Django 5.2 + Django REST Framework, JWT in HttpOnly cookies (`/backend`)
- **Frontend:** Next.js (App Router) + TypeScript + Tailwind (`/frontend`)
- They are separate processes. The browser talks to Next.js, which proxies `/api/*` to Django.

Needs Python 3.11+ and Node 20+. PostgreSQL 16 is used in Docker; SQLite is the default for local development.

## Run it locally

### 1. Backend (http://localhost:8000)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate        # also creates the 5 departments, 9 roles, capabilities, default lists
```

Create the two accounts that start the system (change the values):

```bash
# Windows PowerShell
$env:CEO_EMAIL="ceo@innovation.test"; $env:CEO_PASSWORD="ChangeMe-123-strong"; $env:CEO_NAME="Your Name"
$env:DJANGO_SUPERUSER_PASSWORD="Another-strong-1"
# macOS/Linux: export CEO_EMAIL=... CEO_PASSWORD=... CEO_NAME=... DJANGO_SUPERUSER_PASSWORD=...

python manage.py seed           # the CEO (Administration head). Does nothing if the CEO exists
python manage.py createsuperuser --noinput --email admin@innovation.test --full_name "System Admin"   # the Super Admin
python manage.py runserver 8000
```

- The **Super Admin** has no department and holds every capability; it is invisible to the CEO. Only the CEO creates users, from **Users → Add user**.
- Check the result any time: `python manage.py list_users` (read-only, no passwords).
- Uploaded files go to `backend/private_media/` (override `PRIVATE_MEDIA_ROOT`). They are never public URLs. Back the folder up with the database.
- "Today", attendance and recurrence use `Asia/Amman` (override `DJANGO_TIME_ZONE`).
- API documentation (Swagger at `/api/v1/docs/`, ReDoc at `/api/v1/redoc/`, raw schema at `/api/v1/schema/`) is served only to people with the `settings.manage` capability (CEO, Super Admin).

### 2. Frontend (http://localhost:3000)

```bash
cd frontend
npm install
npm run dev                     # production check: npm run build && npm start
```

If the API is elsewhere, copy `frontend/.env.example` to `.env.local` and set `NEXT_PUBLIC_API_URL` (read at build time).

### 3. First walk-through

1. Sign in as the CEO. Open the company page (`/admin/company`) and upload the company stamp (needed before anything can be signed).
2. **Users → Add user**: create each role (Marketing, Commercial head/member, HR head/member, Operation head/member). Choose **Generate** for a temporary password and copy it: it is shown once.
3. Each new person signs in with the temporary password and is sent to **Set your new password**.
4. Marketing imports or adds leads; the pipeline continues as described in `docs/USER_GUIDE.md`.

Development only: `python manage.py seed_demo_data` creates one demo user per role (`*@demo.test`, password `Demo-12345`). It refuses to run when `DJANGO_ENV=production` or DEBUG is off.

## Scheduled jobs (required in production)

| Job | Command | Cadence |
|---|---|---|
| Due reminders, 60-minute urgent alerts, appointments | `python manage.py process_notifications` | every 5 minutes |
| Recurring client tasks, overdue task reminders | `python manage.py generate_recurring_tasks` | daily, early morning |
| Overdue instalments | `python manage.py check_overdue_payments` | daily |
| General-task overdue alerts | `python manage.py general_task_alerts` | daily |
| Lead follow-up reminders | `python manage.py lead_reminders` | daily |

All are idempotent. If one is missed, the daily ones also run on the first request of the day. Details in `docs/DEPLOYMENT.md`.

## Tests and checks

```bash
cd backend
python -m pytest -q                      # whole backend suite (python manage.py test runs the same tests)
python manage.py makemigrations --check --dry-run
python manage.py spectacular --validate --fail-on-warn --file NUL     # OpenAPI must generate with no warning
cd ../frontend
npx tsc --noEmit && npm run lint && npm run i18n:check && npm run build
cd .. && python scripts/secret_scan.py
```

Browser proofs (real Chrome, EN and AR, 375/768/1280px) live in `qa/browser` and `frontend/e2e`; see their READMEs.

## Docker

```bash
cp .env.example .env            # fill in DB_PASSWORD and DJANGO_SECRET_KEY (50+ random characters)
docker compose up --build       # PostgreSQL, Gunicorn Django, Next.js; only the frontend is published
```

Then create the CEO and Super Admin inside the backend container (`docker compose exec backend python manage.py seed`, and `createsuperuser --noinput`, with the environment variables above).

## Languages

English (LTR) and Arabic (RTL). Switch with **EN | عربي** in the top bar or in Profile → Settings; the `lang` cookie lets the server render the right `<html lang dir>` on first paint. Text lives in `frontend/src/locales/{en,ar}.json`; `npm run i18n:check` fails on any missing or extra key. Use logical Tailwind classes (`ms-`, `me-`, `ps-`, `pe-`, `start-`, `end-`). Dates and numbers use Western digits.

## Security model in one paragraph

Tokens live only in HttpOnly SameSite=Lax cookies (Secure in production); unsafe requests need the `X-CSRF-Token` header; refresh tokens rotate and are blacklisted; deactivating a user or changing their role or password cuts off old tokens at once; five failed sign-ins in five minutes lock the account, with a per-IP throttle; every error uses one envelope `{error: {code, message, fields?}}`; every endpoint declares the capabilities it needs and fails closed. Operation users never see prices, contract values, payments or contract files. Temporary passwords are never stored or logged.

## Documents

`docs/ARCHITECTURE.md` (modules and state machines), `docs/PERMISSIONS.md` (role × endpoint matrix, generated and tested), `docs/DEPLOYMENT.md`, `docs/USER_GUIDE.md`, `docs/OBJECTIVES_MATRIX.md`, `docs/ACCEPTANCE_MATRIX.md` and `docs/ACCEPTANCE_REPORT.md` (this audit).
