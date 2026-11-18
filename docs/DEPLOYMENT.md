# Deployment

Two processes: the Django API (`backend`) and the Next.js web app (`frontend`). Put both behind one reverse proxy that ends TLS. To host on Render instead, skip to section 7.

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
| `DJANGO_ALLOWED_HOSTS` | the API host name(s), comma-separated. The container healthcheck sends the first name as its Host header |
| `CORS_ALLOWED_ORIGINS` | the `https://` address of the web app |
| `PRIVATE_MEDIA_ROOT` | a folder outside the code, e.g. `D:\innovation\files` |
| `SECURE_PROXY_SSL` | `1` when the proxy sets `X-Forwarded-Proto` |
| `DEFAULT_PHONE_REGION` | country (ISO code) of phone numbers typed without a country code. Default `JO`. Stored numbers are not rewritten when it changes |
| `RECURRING_DAYS_AHEAD` | create recurring tasks this many days before they are due (0 to 30). Default `0`: on the due date. A task created early keeps its real due date |
| `TRUSTED_PROXY_COUNT` | how many of your proxies sit between the caller and Django and append the address they saw to `X-Forwarded-For` (see below). `0` ignores the header |

First run:

```
python manage.py migrate
python manage.py collectstatic --noinput
set CEO_EMAIL=ceo@yourcompany.com & set CEO_PASSWORD=<strong password> & set CEO_NAME="Full Name"
python manage.py seed
set DJANGO_SUPERUSER_PASSWORD=<strong password>
python manage.py createsuperuser --noinput --email admin@yourcompany.com --full_name "System Admin"
```

`seed` creates the departments and the CEO account (`createsuperuser` makes the Super Admin, who has no department and is invisible to the CEO), and does nothing if the CEO already exists (lookups, leave types and the checklist template come with the migrations). Change the CEO password after first sign-in from Profile. Serve with any WSGI server: `pip install waitress` then `waitress-serve --port 8000 config.wsgi:application` (Windows), or `gunicorn config.wsgi` (Linux; gunicorn is in `requirements.txt`). `GET /api/v1/health/` returns `{"status":"ok"}` (503 `{"status":"down"}` if the database is unreachable) for monitoring.

## 2. Frontend

```
cd frontend
set BACKEND_URL=http://backend-host:8000
npm ci && npm run build && npm start -- -p 3000
```

`BACKEND_URL` is the address the web app's server uses to reach Django (the browser never calls it; it only calls the web app, which forwards `/api/*`). It is read when the server starts, so changing it needs a restart, not a rebuild. Production adds HSTS and a Content-Security-Policy whose `connect-src` is the web app itself.

## 3. Database: PostgreSQL

SQLite is fine for a small team. To switch:

```
# the PostgreSQL driver (psycopg[binary]) is already installed by requirements.txt
DB_ENGINE=postgres  DB_NAME=innovation  DB_USER=...  DB_PASSWORD=...  DB_HOST=...  DB_PORT=5432
python manage.py migrate
```

To move existing data: `python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.permission > data.json` on SQLite, switch the variables, `migrate`, then `loaddata data.json`. Do this once, with the app stopped, and keep the SQLite file.

## 4. Scheduled jobs

**With `docker compose` nothing to do: the `scheduler` service runs all five** (`python manage.py run_scheduler`: `process_notifications` every 5 minutes, the other four once a day, a failed job is retried on the next round). On a bare server, schedule all five yourself. All are safe to run any number of times. If a daily job is missed, the same work runs on the first request of the day; `process_notifications` is the only one that must run every few minutes, because the 60-minute urgent alerts depend on it.

| Job | Command |
|---|---|
| Create due recurring tasks | `python manage.py generate_recurring_tasks` |
| Instalment overdue status and reminders | `python manage.py check_overdue_payments` |
| Overdue alerts for general tasks (one per deadline) | `python manage.py general_task_alerts` |
| Lead follow-up reminders (daily) | `python manage.py lead_reminders` |
| Reminders, urgent 60-minute alerts, appointments (**every 5 minutes**) | `python manage.py process_notifications` |

Windows Task Scheduler (daily 06:00): Action "Start a program", Program `C:\path\backend\.venv\Scripts\python.exe`, Arguments `manage.py generate_recurring_tasks`, Start in `C:\path\backend`. Repeat for the other jobs. Set `DJANGO_SETTINGS_MODULE` and the other variables for the task (or use a small `.bat` that sets them).

Linux cron: `0 6 * * * cd /srv/innovation/backend && .venv/bin/python manage.py generate_recurring_tasks && .venv/bin/python manage.py check_overdue_payments && .venv/bin/python manage.py general_task_alerts`

## 5. Backup

Back up two things **together**, because records point at files: the database (SQLite file, or `pg_dump`) and the `PRIVATE_MEDIA_ROOT` folder. Daily is the minimum; keep at least 14 days and test a restore. Uploaded files are never served without signing in, so do not expose that folder through the web server.

## 6. Notes

- **Client address and the sign-in throttle.** Django sees the address of the web app container, not the caller's. The web app passes `X-Forwarded-For` through unchanged, so the caller's address is whatever your TLS reverse proxy puts in it. Set `TRUSTED_PROXY_COUNT=1` when one reverse proxy sits in front of the web app and appends the address it saw (nginx `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`, Caddy does this by default). Django reads the header from the right, so entries a caller invents on the left are ignored. Add one for every further hop that appends (a CDN in front of the proxy: 2). Never set a count higher than your real chain: with `0` (the default) the header is ignored and **every caller shares the web app's address**, so the per-address limit (20 wrong passwords in 5 minutes) then locks everyone out at once. That is also what you get when port 3000 is published without a proxy. Run behind the proxy and set the count.
- The sign-in lockout counters are rows in the database (`accounts_loginfailure`), updated atomically, so they are exact and shared by every worker and container. Expired rows are removed on the next failed sign-in. The cache under `DJANGO_CACHE_DIR` is no longer used for them.
- The audit trail table (`audit_auditentry`) has database triggers that refuse every UPDATE and DELETE, on SQLite and PostgreSQL, so even raw SQL cannot change history. A database owner can still drop a trigger: on PostgreSQL also run `REVOKE UPDATE, DELETE, TRUNCATE ON audit_auditentry FROM <the application role>;` and connect the app with a role that does not own the table.
- Static files (`STATIC_ROOT`) are only the Django admin/API assets; serve them from the proxy or leave them to the app.
- Logs go to the console with passwords, tokens and authorization headers scrubbed.
- Upgrades: pull, `pip install -r requirements.txt`, `python manage.py migrate`, restart. Migrations are additive.

## 7. Render

`render.yaml` at the repository root is a Blueprint for four pieces, all in the Frankfurt region (the internal names only work inside one region; change `region:` in every block to move):

| Piece | Render type | Notes |
|---|---|---|
| `innovation-hr-db` | PostgreSQL 16, `basic-256mb` | no public access |
| `innovation-hr-api` | **private** service, Docker (`backend/Dockerfile`) | no public address, like the compose `backend`; 5 GB persistent disk at `/data/private_media` (`PRIVATE_MEDIA_ROOT`) |
| `innovation-hr-web` | web service, Docker (`frontend/Dockerfile`) | the only public address; calls the API at `http://innovation-hr-api:8000` |
| `innovation-hr-scheduler` | background worker, Docker (same image, `python manage.py run_scheduler`) | the five scheduled jobs of section 4; needs no disk |

The API is a private service rather than a public web service so that the internet can only reach the web app. If you want a public API address anyway, change `type: pserv` to `type: web` and add the public host name to `DJANGO_ALLOWED_HOSTS`.

### Steps

1. Push the repository to GitHub or GitLab. In Render: **New > Blueprint**, pick the repository, and Render reads `render.yaml`.
2. Render asks for the values marked `sync: false` (table below). Leave `CORS_ALLOWED_ORIGINS` and `PORTAL_URL` for now if you do not know the web address yet: it is `https://innovation-hr-web.onrender.com` unless Render added a suffix because the name was taken (see the service page after the first deploy), or your custom domain.
3. Apply. The API runs `migrate` on every start, so the database is built on the first deploy. The worker may log failed jobs until that finishes; it retries on the next round.
4. Once the web address is known, set `CORS_ALLOWED_ORIGINS` (and `PORTAL_URL`) on `innovation-hr-api` and save: it redeploys. The worker copies these values from the API service, so they are typed once.
5. Create the first accounts from **innovation-hr-api > Shell** (section 1, "First run"): `CEO_EMAIL`, `CEO_PASSWORD`, `CEO_NAME` then `python manage.py seed`, then `DJANGO_SUPERUSER_PASSWORD` and `python manage.py createsuperuser --noinput --email ... --full_name ...`. Use `export` in the Shell, not `set`, and do not store these as dashboard variables.
6. Open the web address and sign in as the CEO; change the password from Profile.

### Environment variables to set in the dashboard

Only names; the values are yours. All are on `innovation-hr-api` (the worker copies them).

| Name | What it is |
|---|---|
| `DJANGO_SECRET_KEY` | 50+ random characters: `python -c "import secrets;print(secrets.token_urlsafe(64))"`. Not Render's "generate value" (too short, the app refuses to start) |
| `CORS_ALLOWED_ORIGINS` | the web app's public `https://` address, no trailing slash. The app refuses `http://` |
| `PORTAL_URL` | `<web address>/portal`, written into the client welcome email |
| `EMAIL_HOST` | SMTP server (with `EMAIL_PORT`, default 587, and `EMAIL_USE_TLS`, default 1, if yours differ) |
| `EMAIL_HOST_USER` | SMTP user |
| `EMAIL_HOST_PASSWORD` | SMTP password |
| `DEFAULT_FROM_EMAIL` | the From address on system emails |

Already set by `render.yaml`, change only if you know why: `PORT` (8000), `PRIVATE_MEDIA_ROOT`, `DJANGO_ALLOWED_HOSTS` (the internal service name `innovation-hr-api`), `SECURE_PROXY_SSL` (1), `TRUSTED_PROXY_COUNT` (1), `SECURE_SSL_REDIRECT` (0, because the web app calls the API over plain HTTP inside Render's network; TLS ends at Render's edge), `DJANGO_TIME_ZONE`, `DB_ENGINE` and the five `DB_*` values (taken from the database), `DJANGO_EMAIL_BACKEND` (SMTP). On the web service: `BACKEND_URL`. Optional, any time: `DEFAULT_PHONE_REGION`, `RECURRING_DAYS_AHEAD`, `URGENT_*_MINUTES` (add them to the API and the worker).

If you rename a service in `render.yaml`, update `DJANGO_ALLOWED_HOSTS` and `BACKEND_URL` to match.

### Check after the first deploy

- `https://<web address>/login` opens, and signing in works (a wrong password answers 401 and a correct one stays signed in).
- Upload a file to a client, redeploy, and download it again: the disk kept it.
- Sign in wrongly a few times from two networks: `TRUSTED_PROXY_COUNT=1` assumes the last address Render's edge puts in `X-Forwarded-For` is the visitor's. If the audit trail shows the same address for everyone, or the 20-failures address lock hits all users at once, the count is wrong for your path (a CDN or Cloudflare in front of Render adds a hop: use 2).
- The worker's log shows `process_notifications` finishing every 5 minutes.
- The API has no `healthCheckPath` in the Blueprint: Render's checker may send an address as the Host header, which `DJANGO_ALLOWED_HOSTS` rightly rejects. Render still waits for the port to open.

### What does not work on the free plan

Checked against Render's pricing when this was written; look at render.com/pricing before relying on it.

- **No persistent disk.** Uploaded files (quotations, contracts, client documents, the company stamp) live only on a disk, and a free service has none: they vanish at every deploy and restart.
- **No private service and no background worker.** The API (`pserv`) and the scheduler (`worker`) need a paid instance, and cron jobs have no free tier either. Without the scheduler no appointment reminder and no 60-minute urgent alert is ever sent. Running the API as a free *web* service without a disk would work for a demo, but it would be public and lose its uploads.
- **Free web services sleep after about 15 minutes without traffic** and take around a minute to wake. A sleeping service runs nothing, so even a free "scheduler" web service would not fire the 5-minute jobs. The free web service would be fine only for the frontend (`plan: free`), at the price of a slow first page.
- **The free PostgreSQL database expires** (30 days, then deleted after a short grace period), is small (1 GB) and has no backups. Do not hold real data in it.
- **No Shell on free instances**, so `seed` and `createsuperuser` could not be run from the dashboard.

On paid plans: the disk means one instance only (no scaling out) and a few seconds of downtime on every deploy of the API; back up the disk (Render takes disk snapshots daily, keep your own `pg_dump` and file copy as well, section 5).
