# Deployment

Two processes: the Django API (`backend`) and the Next.js web app (`frontend`). Put both behind one reverse proxy that ends TLS.

## 1. Backend

```
cd backend
python -m venv .venv && .venv\Scripts\activate      (Linux: source .venv/bin/activate)
pip install -r requirements.txt
```

Set the environment (names are in `backend/.env.example`; the app does not read a `.env` file by itself):

| Variable | Production value |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` (refuses to start with a guessable secret, DEBUG on, `*` hosts or missing values) |
| `DJANGO_SECRET_KEY` | 50+ random characters |
| `DJANGO_ALLOWED_HOSTS` | the API host name(s), comma-separated |
| `CORS_ALLOWED_ORIGINS` | the `https://` address of the web app |
| `PRIVATE_MEDIA_ROOT` | a folder outside the code, e.g. `D:\innovation\files` |
| `SECURE_PROXY_SSL` | `1` when the proxy sets `X-Forwarded-Proto` |
| `TRUST_X_FORWARDED_FOR` | `1` only when the proxy sets the client address (login lockout uses it) |

First run:

```
python manage.py migrate
python manage.py collectstatic --noinput
set CEO_EMAIL=ceo@yourcompany.com & set CEO_PASSWORD=<strong password> & set CEO_NAME="Full Name"
python manage.py seed
```

`seed` creates the departments and the CEO account, and does nothing if the CEO already exists (lookups, leave types and the checklist template come with the migrations). Change the CEO password after first sign-in from Profile. Serve with any WSGI server: `pip install waitress` then `waitress-serve --port 8000 config.wsgi:application` (Windows), or `pip install gunicorn` then `gunicorn config.wsgi` (Linux). `GET /api/health/` returns `{"status":"ok"}` (503 `{"status":"down"}` if the database is unreachable) for monitoring.

## 2. Frontend

```
cd frontend
set NEXT_PUBLIC_API_URL=https://api.yourcompany.com/api
npm ci && npm run build && npm start -- -p 3000
```

`NEXT_PUBLIC_API_URL` is read at build time. Production adds HSTS and a Content-Security-Policy that allows only that API address.

## 3. Database: PostgreSQL

SQLite is fine for a small team. To switch:

```
pip install "psycopg[binary]"
DB_ENGINE=postgres  DB_NAME=innovation  DB_USER=...  DB_PASSWORD=...  DB_HOST=...  DB_PORT=5432
python manage.py migrate
```

To move existing data: `python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.permission > data.json` on SQLite, switch the variables, `migrate`, then `loaddata data.json`. Do this once, with the app stopped, and keep the SQLite file.

## 4. Scheduled jobs

Run all three once a day (early morning). All are safe to run any number of times. If you forget, the same work runs on the first request of each day.

| Job | Command |
|---|---|
| Create due recurring tasks | `python manage.py generate_recurring_tasks` |
| Instalment overdue status and reminders | `python manage.py check_overdue_payments` |
| Overdue alerts for general tasks (one per deadline) | `python manage.py general_task_alerts` |

Windows Task Scheduler (daily 06:00): Action "Start a program", Program `C:\path\backend\.venv\Scripts\python.exe`, Arguments `manage.py generate_recurring_tasks`, Start in `C:\path\backend`. Repeat for the other jobs. Set `DJANGO_SETTINGS_MODULE` and the other variables for the task (or use a small `.bat` that sets them).

Linux cron: `0 6 * * * cd /srv/innovation/backend && .venv/bin/python manage.py generate_recurring_tasks && .venv/bin/python manage.py check_overdue_payments && .venv/bin/python manage.py general_task_alerts`

## 5. Backup

Back up two things **together**, because records point at files: the database (SQLite file, or `pg_dump`) and the `PRIVATE_MEDIA_ROOT` folder. Daily is the minimum; keep at least 14 days and test a restore. Uploaded files are never served without signing in, so do not expose that folder through the web server.

## 6. Notes

- Login lockout and the cache use files under `DJANGO_CACHE_DIR`, which is correct for one server. For several servers, point `CACHES` at a shared Redis.
- Static files (`STATIC_ROOT`) are only the Django admin/API assets; serve them from the proxy or leave them to the app.
- Logs go to the console with passwords, tokens and authorization headers scrubbed.
- Upgrades: pull, `pip install -r requirements.txt`, `python manage.py migrate`, restart. Migrations are additive.
