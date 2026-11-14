# Innovation: internal system (Task 1)

Login, forced password change, home, Users (CEO only) and Clients (Operation head and CEO).

- **Backend:** Django + Django REST Framework + JWT (`/backend`)
- **Frontend:** Next.js (App Router) + TypeScript + Tailwind (`/frontend`)

They are fully separate and talk over a REST API at `http://localhost:8000/api`.

## Run it

You need Python 3.11+ and Node 20+.

### 1. Backend (http://localhost:8000)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate        # run again after every update: new apps add tables and seed the default lists

# Create the 5 departments and the CEO account (change the values)
# Windows PowerShell:
$env:CEO_EMAIL="ceo@innovation.test"; $env:CEO_PASSWORD="ChangeMe-123"; $env:CEO_NAME="Your Name"
# macOS/Linux:
# export CEO_EMAIL=ceo@innovation.test CEO_PASSWORD=ChangeMe-123 CEO_NAME="Your Name"
python manage.py seed

python manage.py runserver 8000
```

`seed` is safe to run again: it does nothing if the CEO already exists.

The CEO account is a normal account with no forced password change, so pick a strong `CEO_PASSWORD`.

Uploaded files are stored in `backend/private_media/` (override with `PRIVATE_MEDIA_ROOT`). They are never served as public URLs. Back this folder up with the database.
The time zone for "today" and attendance is `Asia/Amman`; set `DJANGO_TIME_ZONE` to change it.

### 2. Frontend (http://localhost:3000)

```bash
cd frontend
npm install
npm run dev
```

If the API is somewhere else, copy `.env.example` to `.env.local` and set `NEXT_PUBLIC_API_URL`.

### Tests

```bash
cd backend
python manage.py test        # 70 tests: Task 1 rules plus audit, notifications, files, comments, lookups, My Work and the eight-role permission harness
```

## Try the full flow

1. Sign in as the CEO.
2. **Users → Add user**: Operation department, role Head, select **Generate** for a temporary password. Copy the details shown.
3. Sign out, then sign in as that person with the temporary password. You are sent to **Set your new password**.
4. Choose a new password. You land on Home, and **Clients** is now in the menu.
5. **Clients → Add client**.

## Languages: English and Arabic (RTL)

- Switch with the **EN | عربي** control in the top bar (on the sign-in and set-password screens it sits in the top corner), or in **Settings**.
  The choice is saved in a `lang` cookie, so the server renders the right `<html lang dir>` on first paint, even before sign-in.
  URLs are the same in both languages.
- Text lives in `frontend/src/locales/en.json` and `ar.json`. In code use `const t = useT()` then `t("users.add")`. Add every new
  string to both files. Backend messages (English) are mapped to keys in `frontend/src/lib/i18n.tsx`; an unmapped backend message shows a
  generic translated error in Arabic.
- Stored values never change. Department and role names are translated for display only.
- Use logical Tailwind classes (`ms-`, `me-`, `ps-`, `pe-`, `start-`, `end-`, `text-start`, `border-s`, `rounded-s`), never left/right.
  Wrap emails, phone numbers and passwords in `<Ltr>`. Flip direction-only icons with `rtl:-scale-x-100`.
- Dates and numbers use `Intl` with the active language, always with Western digits (0-9).
- Arabic uses IBM Plex Sans Arabic through `next/font/google`.

The account stores `preferred_language` (set from Profile > Settings, or by the CEO when creating a user) and it is applied at sign-in.
After pulling this version run `python manage.py migrate` once (adds that column).

Design: see `frontend/DESIGN.md` (tokens, type, spacing, motion, components). Review screenshots live in `frontend/.design-review/`.
Profile (`/profile`, tabs Overview and Settings) replaces the old Settings page; `/settings` redirects to `/profile?tab=settings`.

## API (all under `/api`)

| Endpoint | Who |
|---|---|
| `POST auth/login/`, `POST auth/refresh/` | anyone |
| `POST auth/logout/`, `GET auth/me/`, `PATCH auth/me/` (only `preferred_language`), `POST auth/change-password/` | signed in (these work even while a password change is pending) |
| `GET dashboard/summary/` | signed in; the content depends on the role (CEO, Operation head, everyone else) |
| `GET/POST users/`, `GET/PATCH users/{id}/`, `POST users/{id}/deactivate/`, `activate/`, `reset-password/` | CEO |
| `GET departments/` | CEO |
| `GET/POST clients/`, `GET/PATCH clients/{id}/` | Operation head, CEO |

Every endpoint other than the ones marked "signed in" returns **403** while `must_change_password` is true.

## Database

SQLite by default. For Postgres set `DB_ENGINE=postgres` plus `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
and `pip install "psycopg[binary]"`. Other env vars: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG` (`1`/`0`),
`DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` (comma separated).

## Attendance log

`accounts_actionlog` has one row per login or logout: `user`, `action` (`login`/`logout`), `timestamp`, `ip_address`,
indexed on `(user, timestamp)` and `(action, timestamp)`. Failed logins are not logged.

## Decisions where the brief was open (simplest option picked)

- **Rules live in the model.** `User.save()` checks the department rules, so no code path can skip them. The API turns
  failures into plain field errors.
- **Seats count inactive users too.** A deactivated Operation head still holds the head seat. To replace them, change
  their role to Member first. This stops a reactivation from creating a second head.
- **Marketing "exactly one"** is enforced as "at most one". Nothing can force the seat to be filled. Its one person can
  be either role.
- **Administration** accepts only one user, who must be a head (the CEO). The CEO can't change their own department or
  role, and can't deactivate themselves.
- **CEO** means: Administration department and role head.
- **Forced change needs no old password**, because the person has just signed in with the temporary one. The new password
  must differ from the temporary one, be at least 8 characters, and match the confirm field. That endpoint only works while
  a change is pending.
- **Temporary passwords** are never stored or shown again. After "Add user" or "Reset password" the CEO sees them once in
  a panel with a Copy button. "Generate" avoids look-alike characters (0/O, 1/l/I).
- **Failed login** gives one message for an unknown email, a wrong password and a deactivated account.
- **Tokens** are kept in `localStorage` (access 30 min, refresh 1 day). Sign out blacklists the refresh token and does a
  full page reload so nothing from the last person stays in memory. A hardened version would use httpOnly cookies.
- **No pagination** on the Users and Clients lists, since both are small for an internal tool. Search is server side.
- **Emails** are stored lowercase, and uniqueness ignores case.
- **No dark mode, no login throttling**, to keep this task small.
- The Next.js scaffold's `cacheComponents` setting is switched off in `next.config.ts`. It adds nothing to a
  client-rendered app behind a login.


## Business workflow build (in progress)

The full lead-to-cash workflow is being added phase by phase. See `docs/ARCHITECTURE.md` for the modules, state machines, permission matrix and API list.

- **Phase 1 (done):** activity trail, in-app notifications (bell), private file uploads, comments with @mentions, CEO Settings (rejection reasons, services, legal checklist, work hours, follow-up rules), My Work on Home with sidebar badges, role-aware navigation with a More sheet on phones, and the eight-role permission test harness.
