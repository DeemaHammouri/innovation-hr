# Audit report: Innovation-hr against the 24 objectives

Baseline: `docs/objectives.txt` (Nov 15, 2026). Nothing in the repo (README, `OBJECTIVES_MATRIX.md`, commit messages) was trusted: every status below was reproduced by a command, a request, or by reading the code that enforces it.

**Status of this report: complete. Step 0 and Phases 1 to 6 are done.** Sections 3 to 5 are filled in as the phases finish.

Rule kept since Phase 2: no request is sent to port 8000 (something else listens there). Phases 2 and 3 used Django's in-process test client against throw-away SQLite files, so no server was started at all (the one PostgreSQL server in Phase 3 listens on port 60446).

## Summary: all 24 objectives

Details and evidence are in sections 1 to 1f. Status counts the Done-when items of the objective: PASS only when none fails.

| Obj | Subject | Done-when items | Overall | Problems |
|---|---|---|---|---|
| 1 | Skeleton and environment | 2 PASS, 1 FAIL (compose health) | **FAIL** | P1, P12 |
| 2 | Organisation | 2 PASS, 1 PARTIAL | PARTIAL | P7 |
| 3 | Cookie authentication | 3 PASS | PASS | |
| 4 | RBAC | 2 PASS, 1 CANNOT-VERIFY (answered by the generated denial tests in Obj 23) | PASS | |
| 5 | Users and first login | 2 PASS, 1 PARTIAL | PARTIAL | P8, P9, P10 |
| 6 | Revocation, lockout, audit, envelope | 2 PASS, 1 FAIL in production | **FAIL** | P2, P3, P5, P11 |
| 7 | Bilingual shell | 1 FAIL (i18n gate), 1 PARTIAL, 1 CANNOT-VERIFY | **FAIL** | P4, P13, P39 |
| 8 | Leads pool, duplicates | 3 PASS | PASS | P18, P19 |
| 9 | Excel import | 3 PASS | PASS | |
| 10 | Statuses and history | 2 PASS, 1 PARTIAL | PARTIAL | P17 |
| 11 | Appointments, notifications | 2 PASS, 1 PASS with open race | PARTIAL | P14, P15, P16 |
| 12 | Targets and dashboard | 3 PASS | PASS | |
| 13 | Lead to client, portal | 3 PASS | PASS | P24 |
| 14 | Quotation workflow | 3 PASS, 1 FAIL (numbering path crashes on PostgreSQL) | **FAIL** | P20, P22 |
| 15 | Document generation | 3 PASS, 1 PARTIAL (Arabic in `both`) | PARTIAL | P21 |
| 16 | Meeting reports, contracts | 3 PASS on SQLite | PASS on SQLite, blocked on PostgreSQL | P20, P23 |
| 17 | Tracking and SLA alerts | 2 PASS | PASS | P25 |
| 18 | Handover and confidentiality | 1 PASS, 1 PARTIAL | PARTIAL | P26, P29, P30 |
| 19 | KYC, projects, assignment | 3 PASS, 1 PARTIAL | PARTIAL | D12 |
| 20 | Recurring generator | PASS on SQLite, FAIL on PostgreSQL; kinds PARTIAL | **FAIL on PostgreSQL** | P26, P27, P31 |
| 21 | Execution, review, monitoring | reports PASS; escalation FAIL on PostgreSQL; log PARTIAL | PARTIAL | P26, P28, P31 |
| 22 | Work tasks with attachments | 6 PASS, 1 PARTIAL | PARTIAL | P32, P33 |
| 23 | Testing | 3 FAIL (suites, repeatable E2E, suite not in repo), 2 PARTIAL | **FAIL** | P20, P27, P34 to P39 |
| 24 | Documentation and deployment | 1 FAIL, 2 PARTIAL, 1 PASS | **FAIL** | P3, P6, P34 to P36, P40, P41 |

## 0. How the audit was run

| Item | Value |
|---|---|
| Code audited | `git clone` of `HEAD` (9959db2) into the session scratch folder. The working tree, `db.sqlite3` and the uncommitted files were not touched. |
| Backend interpreter | **Python 3.11.16** (uv build), fresh virtualenv, `requirements.txt` + `requirements-dev.txt`. |
| Frontend | Node v24.14.1, npm 11.9.0, `npm ci` from the lockfile, `next build` and `next start` run locally. |
| Database | SQLite scratch files for Phases 1 and 2. **From Phase 3 on, a real PostgreSQL 16.2 server is also available**: the `pgserver` pip package (an embedded PostgreSQL build) started in a scratch folder on port 60446, with the IANA time-zone files copied in from the `tzdata` package because that build ships none. It is not Docker and not your production version, but it is a genuine PostgreSQL engine, so row locks, `FOR UPDATE` and unique-index races behave as they will in compose. There is still no Docker on this machine. |
| Side effects | A temporary `R:` drive (`subst`) points at the scratch clone because `npm ci` failed on Windows long paths (48 `TAR_ENTRY_ERROR`). Local servers I started (ports 3100, 3101, 8001) were stopped. **Port 8000 already had a listener that is not mine** (probably your dev server); I only sent it one `GET /api/v1/health/` by accident and left it alone. |
| Python dependence | The Phase 1 probes use Django behaviour that does not change between 3.11 and 3.12. They were **not** run on 3.12 (the Docker image) or on 3.15. Phase 6 test results will be stated for 3.11.16 only. |

### Step 0: hygiene

| # | Finding | Severity | Evidence | Fix |
|---|---|---|---|---|
| H1 | `backend/db.sqlite3.backup` is untracked and **not ignored**. | Medium | `git check-ignore -v backend/db.sqlite3.backup` prints nothing. `*.sqlite3` does not match `.backup`. | Add `*.backup` / `*.sqlite3.backup` to `.gitignore`; move the file out of the repo. |
| H2 | `README.md:106` links `docs/ACCEPTANCE_MATRIX.md` and `docs/ACCEPTANCE_REPORT.md`; neither exists, now or in any commit. | Medium (Obj 24) | `ls docs`; `git log --all -- docs/ACCEPTANCE_*.md` empty. | Write them or remove the links. |
| H3 | `gunicorn` and `psycopg` are not in `requirements.txt`. Only `backend/Dockerfile:6` installs them (ad hoc). | Medium (Obj 1, 24) | `requirements.txt:6` is a comment; `Dockerfile:6`. | Pin both in a requirements file the Dockerfile and README both use. |
| H4 | Two virtualenvs: `backend/venv` and `backend/.venv`. See section 6. | Low | | Delete `backend/venv`. |
| H5 | The development `SECRET_KEY` fallback is committed (`base.py:13`). | Low | `production.py:25-26` rejects it (reproduced: production refuses a short or `dev-only` key). | None needed. |

Passed: no database, backup, `.env`, virtualenv, `node_modules` or `private_media` is tracked (only the three `.env.example` files). No `*.sqlite3*` in any of the 43 commits (`git log --all`). `scripts/secret_scan.py`: 0 findings. History grep for `SECRET_KEY`, `PASSWORD=`, `BEGIN PRIVATE KEY`, `sk-` found only placeholders, variable names and doc examples ("ChangeMe-123" in old README text).

## 1. Phase 1: Foundation (objectives 1 to 7)

Legend: PASS, FAIL, PARTIAL, CANNOT-VERIFY. "Repro" names the script or command in the scratch folder.

### Obj 1: skeleton and environment

| Done when | Status | Evidence |
|---|---|---|
| `docker compose up --build` brings all three services healthy | **FAIL (reproduced, Docker run pending)** | See P1. The backend healthcheck sends `Host: 127.0.0.1:8000`; compose and `.env.example` set `DJANGO_ALLOWED_HOSTS=localhost,backend`. Under production settings with those values: `Host 127.0.0.1:8000 -> 400 DisallowedHost`, `localhost:8000 -> 200`, `backend:8000 -> 200`. The backend stays unhealthy and `frontend` has `depends_on: backend: service_healthy`, so it never starts. |
| `GET /api/v1/health/` returns OK | PASS | `{"status":"ok"}` 200; POST gives 405. It runs `SELECT 1` and returns 503 when the DB is down (`core/views.py`). |
| No secret committed | PASS | Step 0. Caveat: H1 (the backup file is not ignored yet). |

Other facts: settings are split base/development/production/test. `wsgi.py` and `asgi.py` default to production, the Dockerfile sets `DJANGO_SETTINGS_MODULE=config.settings.production`, and `manage.py` defaults to development (`config.settings`) except `manage.py test`. So suspicion 4 is **mostly rejected**: `DJANGO_DEBUG` defaults to `1` only in base/development, and production forces `DEBUG=False`. Compose sets `SECURE_SSL_REDIRECT=0` and `SECURE_PROXY_SSL=0` while `production.py:40` defaults redirect to 1; inside the container redirect is therefore off (needed for the healthcheck) and cookies are still `Secure=True` (`production.py:36`). A browser accepts Secure cookies on `http://localhost:3000` (Chrome, Firefox); **Safari and any non-localhost HTTP address (LAN IP) will drop them**, so sign-in silently fails there. Not testable without a browser and Docker: Unverified U2. Compose publishes `3000:3000` with no TLS proxy.

### Obj 2: organisation

| Done when | Status | Evidence |
|---|---|---|
| Seed twice, no duplicates or errors | PASS | `seed_organization` x2 then x3: `5 departments, 10 roles, 69 capabilities` each time (the 10th role is the system `client` role; nine staff roles as in the brief). |
| Grant a capability without changing view code | PASS | `marketing` gets `GET /users/` 403; after `Role.capabilities.add(user.manage)` in the database only: 200; after removing it: 403. |
| Super Admin is "marked full access" and automatically receives every capability | **PARTIAL** | `Role` has no full-access flag (fields: key, department, is_head, names, capabilities). Super Admin gets everything only because `ensure_organization()` and migrations call `capabilities.set(all)`. Creating a `Capability` row directly: Super Admin does **not** have it until the seed runs again. See P7. |

### Obj 3: cookie authentication

| Done when | Status | Evidence |
|---|---|---|
| Tokens cannot be read from JavaScript | PASS (headers) | Production settings: `access_token`, `refresh_token` are `HttpOnly; Secure; SameSite=Lax`; `csrf_token` is readable and Secure by design. The login body has only `user`; no token-shaped string. A real browser check is left to the Phase 6 E2E. |
| A used refresh token is rejected | PASS | Refresh #1 200, replay of the old cookie 401 (blacklisted). Rotation works. |
| POST without CSRF header is rejected | PASS | 403 `csrf_failed`. |

Also: login by email or username in any case works (`CEO@A.TEST`, `ceo@a.test`, `THECEO`), and `/auth/me/` returns the user and capabilities. Refresh is allowed while a password change is pending (see Obj 5).

### Obj 4: RBAC

| Done when | Status | Evidence |
|---|---|---|
| Forbidden endpoint called directly returns 403 | PASS | Crawl (`crawl.py`): all 261 (path, method) pairs under `/api/v1/` as anonymous, each of the 10 roles, and a pending-password user: **3,132 requests, 0 violations, 0 server errors**. A role lacking a declared capability always got 403/401/405; anonymous never got 2xx. |
| A view with no declared capability is unreachable | PASS | 91 view classes: only `LoginView`, `LogoutView`, `RefreshView`, `HealthView` bypass `HasCapability` (all intentional). The one undeclared view, DRF `APIRootView`, returns 403. 40 pairs use dynamic `get_required_capabilities` (`reports.views.ReportView/ReportExport`); they were exercised for 4xx/5xx but their per-role logic is Phase 4. |
| Tests cover one allowed and one denied case per role | CANNOT-VERIFY yet | Counted in Phase 6. |

Note: the crawl compares each response with the view's *declared* capabilities. It proves enforcement matches the declaration, not that every declaration is the right policy; that is checked against `docs/PERMISSIONS.md` in Phase 6.

### Obj 5: user management and first login

| Done when | Status | Evidence |
|---|---|---|
| Temporary password never in logs, audit log or DB | PASS | Created a user: 16-character password returned once; stored as `argon2$...`; a scan of **every column of every table** for the plaintext found **0 hits**; captured root-logger output 0 hits; 296 `SecurityEvent` rows hold no token or password; `GET /users/{id}/` has no `temporary_password`. |
| Forged "CEO creates a Super Admin" is rejected | PASS | `role=super_admin` (also with `is_superuser`, `is_staff`): 400, nothing created. Extra `role_ref` / `is_superuser` fields are ignored (created user is a normal member, `is_superuser=False`). The CEO gets 404 on list, GET, PATCH, deactivate and reset-password for the Super Admin. |
| Role choices depend on the department | **PARTIAL** | The form (`components/users/UserForm.tsx:15`) hard-codes `["member","head"]` (`["head"]` for Administration). The backend `/roles/?department=` endpoint is not used. The API still rejects a role from another department, so this is a UI-duplication risk, not a hole. |

Other checks: the password policy rejects 11-character, common, same-as-temporary and "same as current" passwords (400). Nobody can change their own role or department (400), deactivate or reset themselves. Pending-password user: `/auth/me/` 200; every other business endpoint 403 (`password_change_required` or `permission_denied`); `/auth/refresh/` returns 200 while pending, which is wider than the brief's "only me, change password, logout". Low.

### Obj 6: revocation, lockout, audit, envelope

| Done when | Status | Evidence |
|---|---|---|
| Deactivated user is logged out on the next request | PASS | Old cookies: `/me` 401; refresh 401; login 401. |
| 6th wrong password is blocked even with the right one | PASS | 5 x 401, 6th 429, 7th (right password) 429. |
| Every error uses the envelope; no stack traces | **FAIL in production, PASS in development** | See P2. Development: 400/401/403/404/405 all `{"error":{...}}`. **Production settings:** only 404 is wrapped; `401`, `403`, `405`, `400` return raw DRF bodies such as `{"detail":"Authentication credentials were not provided."}`. Triggered a real 500 in production: `{"error":{"code":"server_error","message":"Something went wrong..."}}`, no traceback and no exception text. |

Lockout design problems: P3 (shared client IP / spoofable `X-Forwarded-For`) and P5 (file cache race). Audit: `SecurityEvent` records login, failure, block, user changes and language change with IP and user agent; `record_event` rejects token-shaped or `password`-named values.

### Obj 7: bilingual shell

| Done when | Status | Evidence |
|---|---|---|
| Switching to Arabic flips layout, icons, spacing | CANNOT-VERIFY visually | Server render with `lang=ar`: `<html lang="ar" dir="rtl">`; `lang=en` or no cookie or `lang=fr`: `en`/`ltr`. Code uses logical classes (`ps-`, `me-`, ...); one physical `pr-12` has an `rtl:` override; 13 `rtl:` variants, icons use `rtl:-scale-x-100`/`rtl:rotate-180`. Visual proof belongs to the Playwright run in Phase 6. |
| Language persists on a fresh browser after sign-in | PARTIAL | `auth.tsx:41-44` applies `preferred_language` after `/auth/me/` on the client, so the first paint of a fresh browser is English and flips after hydration. The cookie is then set. |
| Every UI string exists in en.json and ar.json | **FAIL (gate)** | `npm run i18n:check` **exits 1 at HEAD**: it scans `src/lib/i18n.test.tsx`, which deliberately uses the missing key `no.such.key` (added by commit 9959db2). The two dictionaries themselves have no missing or extra keys and no placeholder mismatch. See P4. |

`next-intl` is not used; `src/lib/i18n.tsx` is a hand-written provider (see deviations). The same-origin proxy exists (`src/app/api/[...path]/route.ts`). Production response headers include CSP, HSTS, `X-Frame-Options: DENY`; CSP allows `script-src 'unsafe-inline'` (Low).

## 1b. Phase 2: Leads (objectives 8 to 12)

All results below were produced on a fresh migrated SQLite database with the in-process client (scripts `obj8_9.py`, `obj10_11.py`, `obj12.py` in the scratch folder).

### Obj 8: leads pool with duplicate protection

| Done when | Status | Evidence |
|---|---|---|
| `0797707154` and `+962797707154` are the same lead | PASS | All of `0797707154`, `+962797707154`, `00962797707154`, `962797707154`, `+962 79 770 7154`, `079-770-7154`, Arabic-Indic digits normalise to `+962797707154`. Created the first, then each other spelling: 201, then 400 `duplicate: ["LD-0001"]` every time. Email is lower-cased (`Hello@Example.com` then `hello@example.COM` gives 400). A lead with neither phone nor email gets 400. |
| Two simultaneous inserts of the same phone: one lead, one clean error | **PASS** (re-run on PostgreSQL 16.2 during Phase 3; was CANNOT-VERIFY) | `DB_ENGINE=postgres ... python manage.py test leads.tests_lead_model.ConcurrentInsertTests -v 2` on PostgreSQL 16.2: `test_two_simultaneous_inserts_make_one_lead_and_one_clean_error ... ok`. One run is a weak sample, so U5 still asks for 20 repeats. Earlier SQLite evidence: The schema is right: partial unique indexes `uniq_open_lead_phone` and `uniq_open_lead_email` exist in the database (`WHERE archived_at IS NULL AND phone_key <> ''`), and a raw `bulk_create` of a second `phone_key` / `email_key` raises `IntegrityError`. `services.create_lead` catches `IntegrityError` and returns the same clean `duplicate` error. The repo's own test `leads.tests_lead_model.ConcurrentInsertTests` passes here (26 tests OK), but SQLite serialises writers, so it proves little. Exact PostgreSQL command: U5. |
| List supports search, filters, ordering, pagination | PASS | Search by company, by local phone (`0795500007`) and by `+962...` finds the same lead; `?ordering=company_name` and `-company_name`; `?status=new`; pages of 25, `page_size` capped at 100 (`core/pagination.py`). Only the `lead.create` capability (Marketing) can add leads (Commercial head gets 403). |

Notes: the unique constraint is on `phone_key`/`email_key`, which Python fills in `Lead.save()`. A write that skips `save()` (`QuerySet.update`) can leave the key stale; the importer sets the keys itself (P18). Every number that does not start with `+` or `00` is read as Jordanian (`leads/normalize.py`, `DEFAULT_REGION = "JO"`): `0501234567` becomes `+962501234567` (P19).

### Obj 9: Excel import

| Done when | Status | Evidence |
|---|---|---|
| Mixed valid, invalid and duplicate rows import only the valid ones | PASS | 10-row file: preview `ok 4, errors 4, duplicates 2`; confirm imported exactly 4 (4 new rows in the DB). Rows covered: no contact, no company, 2-digit phone, bad email, duplicate of an existing lead (`0797707154`), duplicate of an earlier row in the same file (`+962 78 100 0009` vs `0781000009`), Arabic-Indic digits (accepted). |
| Report shows row number and reason for each skipped row | PASS | Stored on the batch: `[(4,error),(5,error),(6,error),(7,error),(8,duplicate),(10,duplicate)]`; each carries its messages, `duplicate_of` (`LD-0001`) or `duplicate_in_file` (row 9). Rows are numbered like Excel (header = row 1). |
| Wrong type or oversize file rejected with a clear message | PASS | `.exe`: "Upload an Excel (.xlsx) or CSV (.csv) file..." ; `.exe` content renamed `.xlsx`: "We couldn't open this Excel file. Check that it is a real .xlsx file (not renamed from another type)..."; renamed `.csv`: "We couldn't read this file. Save it as CSV (UTF-8)..."; 6 MB: "This file is over 5 MB..."; 5,001 rows rejected, 5,000 rows accepted (140 KB, 0.8 s preview); a zip that is not a workbook rejected. |

Also: English and Arabic headers (`اسم الشركة`, `الهاتف`...) and mixed `Company / الشركة` headers all map; both templates (`en`, `ar`) download (200); a non-Marketing user gets 403. CSV is accepted as well as `.xlsx` (more than the brief asks).

### Obj 10: statuses and history

| Done when | Status | Evidence |
|---|---|---|
| Each sub-status enforces its required field | PASS | Waiting: no date, today, yesterday and +400 days are all 400 with specific messages; only a future date (up to a year) passes. Rejected without a reason: 400. Outcome before the first contact: 400. A closed (rejected) lead refuses a new outcome ("already closed"). |
| Waiting to Rejected cancels the follow-up appointment | PASS | Waiting +3 days created one `follow_up` appointment at 09:00 company time for the assignee. Waiting again with a new date cancelled the old one and made one new one. Rejecting cancelled the open one (`cancel_reason: Lead rejected`) and cleared `next_follow_up`. |
| History shows every change in order | **PARTIAL** | Order was `- > new, new > contacted, contacted > waiting, waiting > waiting, waiting > rejected, rejected > contacted (reopen)`. But the "contacted" row takes the contact's `occurred_at`, so a first contact logged "5 days ago" is sorted before the lead's own creation row (history showed `new>contacted` dated 2026-11-12 before `-> new` dated 2026-11-17). See P17. |

Transaction check: with `appointments.services.sync_follow_up` forced to fail after the status change, the request returned 500 and the `Interaction` count and the status-history count were both unchanged (1 and 3), so the outcome rolled back as one unit. (Status stayed `waiting` because the lead was already waiting; the proof is the rolled-back interaction row.)

### Obj 11: appointments and notifications

| Done when | Status | Evidence |
|---|---|---|
| A reminder is sent once however many times the command runs | PASS sequentially, **race open** | Appointment 30 minutes ahead: `process_notifications` three times printed `sent 1`, `0`, `0`; an appointment 3 hours ahead got none. But `notify()` is check-then-insert and `Notification.dedupe_key` has no database constraint: with 6 simultaneous callers per key, **33 of 40 rounds created duplicates** (SQLite threads). Two overlapping cron runs can double-send (P15). |
| Rescheduling a follow-up also updates the lead's follow-up date | PASS | Rescheduling a follow-up appointment to +10 days set `lead.next_follow_up` to the same company-time date (2026-11-27). A rescheduled normal appointment reminds again at its new time (by design). |
| Users can mark one or all notifications as read | PASS | One: 204. Someone else's notification: 404. All: 204, unread count 0. |

Other checks: users see their own appointments, the Commercial head can see everyone's and give one to someone else (201), a member trying to assign to someone else gets 403. Notifications are rendered in the recipient's language when created (Arabic title `أسند إليك chead موعدًا` for an Arabic reader, English for an English reader) but are stored as text, so after a user switches language old notifications stay in the old language (P16). The bell reads `/notifications/unread-count/`.

**Scheduler gap (P14):** `docker-compose.yml` has no service that runs `process_notifications`. `docs/DEPLOYMENT.md:62` says it "must run every few minutes" and has no request-time fallback, so in the shipped Docker stack no appointment reminder and no 60-minute urgent alert is ever sent unless the operator adds cron.

### Obj 12: marketing targets and leads dashboard

| Done when | Status | Evidence |
|---|---|---|
| Dashboard numbers match a manual count in the database | PASS | Nine leads placed exactly around local midnights (UTC+3): 23:59:59.999 on the 16th, 00:00:00 on the 17th, 23:59:59.999 on the 17th, 00:00 on the 18th, plus the 7-day and month edges. Dashboard `today / last 7 days / this month` = `(3, 5, 7)`; an independent filter in Python on the stored UTC times gives the same `(3, 5, 7)`. The same data with `TIME_ZONE=UTC` gives `(3, 6, 7)`, so the boundary leads do exercise the zone logic. (My first manual SQL disagreed only because of a string-compare artefact on SQLite timestamps; the Python check settled it.) |
| Progress is correct at first and last day of the range | PASS | Target 10 for 16 to 18 Nov: day before start `upcoming, elapsed 0, left 3`; first day `active, added 1, elapsed 1, expected 3.3, required/day 4.5`; last day `elapsed 3, left 0, added 5` (leads on the 16th, 17th and 18th all count, both end dates included); day after `ended`. |
| Clicking "overdue" opens the pool filtered to those leads | PASS (API and wiring) | Dashboard `overdue: 2, due today: 1`; `GET /leads/?overdue=1` returns exactly those 2. The dashboard link is `/pipeline?overdue=1` (or `/leads?...`) and `LeadsBrowser.tsx:54` sends it to the API. Click-through in a browser is left to Phase 6. |

Targets: the Commercial head can set one (201); an overlapping range is refused; a target for a non-Marketing user is refused; Marketing cannot set their own (403) but sees their own; a member without `lead.dashboard` gets 403 on the dashboard.

#### If the company time zone were Asia/Riyadh instead of Asia/Amman

- **Day boundaries and counts: no difference today.** Both zones are UTC+3 all year in tzdata 2026 (offsets checked for January, April, July and November). I ran the same boundary data under `TIME_ZONE=Asia/Amman` and `Asia/Riyadh`: identical dashboard numbers `(3, 5, 7)`, identical per-day series and identical target progress. Stored times are UTC either way.
- **Risk that only Amman has:** Jordan used daylight saving until October 2022 (Amman was UTC+2 in January 2021, UTC+3 in July 2021). If a container or machine has tzdata older than 2022, "today" and every midnight boundary would be an hour off in winter or summer. Riyadh has no such history. Keep tzdata current in the image (U4).
- **What changes for a Riyadh company** (the code does not follow `TIME_ZONE` for these): `DEFAULT_REGION = "JO"` in `leads/normalize.py` (a local Saudi mobile `0501234567` is stored as `+962501234567`, and would not match the same person's `+966501234567`, so duplicates are missed); public-holiday data used by leave and recurring work (Phase 4) is a Jordanian calendar; `WEEKEND_DAYS = (4, 5)` (Friday and Saturday) is also the Saudi weekend, so it stays correct; the follow-up time of 09:00 is company time in either case.
- **To switch:** set `DJANGO_TIME_ZONE=Asia/Riyadh` (compose passes it through); change the phone default region and holidays; no migration is needed.

## 1c. Phase 3: Clients, quotations, documents, contracts, tracking (objectives 13 to 17)

Scripts (scratch folder): `obj13_16_17.py`, `qmatrix.py`, `docs_probe.py`, `mr_flow.py`, `pg_lock_sites.py`, `seq_pg.py`. Everything ran in-process against throw-away SQLite files, except the PostgreSQL items, which ran on PostgreSQL 16.2 (section 0).

**Headline: on PostgreSQL the quotation, contract, meeting-report, appointment, leave and operations transitions crash (P20, Blocker).** SQLite hides it. Everything below that says PASS was run on SQLite unless it says PostgreSQL. Obj 13 also has one small finding, P24.

### Obj 13: lead to client conversion and portal

| Done when | Status | Evidence |
|---|---|---|
| A converted lead cannot be edited, deleted or have its status changed | PASS | Accepting a lead (`outcome: accepted`, status `qualified`) created exactly one client (`prospect`, contact data copied) and one portal account. Accepting again: 409. As the Commercial head, on the converted lead: PATCH, outcome, reopen, assign, interaction, archive all return **409 `lead_converted`**. DELETE returns 405 because no delete route exists at all. Code: `clients/services.py:28 forbid_if_converted`, called at 7 sites in `leads/services.py`. |
| The client can sign in to the portal and sees only their own data | PASS | The welcome email (captured with the locmem backend) contains the temporary password; logging in with it returns 200 with `must_change_password: true`, and until it is changed `/portal/contracts/` answers 403 `password_change_required`. Portal user on `/leads/`, `/users/`, `/quotations/`, `/clients/`, `/admin/tracking/`: 403 each. A second client's portal user asking for the first client's quotation or contract: 404 on the portal URLs, 403 on the staff URLs. The right client sees their sent/signed quotation and contract (200) but not a draft one (404). Every portal query starts from `Client.objects.get(portal_user=request.user)` (`clients/portal.py:25`), so there is no id to change. |
| Client accounts never appear in internal user management | PASS | The CEO's `/users/` list does not contain the portal user's email. |

Missing and duplicate email: no email gives a client with `portal_status: no_email` and no user; an email equal to a staff email in a different case gives `email_in_use`, no user and the staff account untouched; SMTP down (`send_mail` raising) still converts, with `portal_status: failed` and the user created, and "resend" by the Operation head then answers `sent`. Duplicate lead emails are blocked earlier by the lead uniqueness rule.

### Obj 14: quotation workflow

Number allocation, read from `core/models.py` (`YearSequence.next_number`): `select_for_update().get_or_create(key, year)`, `last += 1`, `save`, formatted `PREFIX/YYYY/M/NNNN` with `timezone.localdate()` (company time, not UTC). It says "call inside `transaction.atomic()`" and both callers do: `quotations/services.py:410-416 mark_sent` and `contracts/services.py:send_to_client` take the number in the same `atomic()` block as the status change.

| Done when | Status | Evidence |
|---|---|---|
| Every illegal transition is rejected by the API | PASS | 10 states x 9 actions x 10 roles = 900 calls, each rolled back. Result: **43 successes, every one a legal (state, role) pair; 0 successes outside the legal set; 0 legal pairs refused.** Codes: 403 650, 400 187, 404 20. Sending an unsigned draft (`in_preparation`): 400; `sign` at `requested`: 400; `submit` at `signed`: 400; `cancel` at `cancelled`: 400; `outcome` at `confirmed`: 400. A Commercial member who is not on the lead gets 404 (not 403) when sending someone else's quotation. Table below. |
| Numbers are sequential with no gaps or duplicates, even under concurrent sends | **FAIL** | (a) **The allocator itself is correct on PostgreSQL**: 12 simultaneous callers on a brand-new key got 1 to 12 (the `get_or_create` race is settled by the unique constraint), 12 more on the existing row got 13 to 24, and when 4 of 12 callers raised after taking a number the 8 that committed got 25 to 32 and the counter ended at 32, so **the number is rolled back with the transaction and there is no gap**. A new year restarts at 1 (`QT/2027/1/0001`). (b) **But the repo's own parallel tests error on PostgreSQL**: `quotations.tests_phase3.ConcurrentNumberTests` and both tests of `contracts.tests_numbering.ConcurrentContractNumberTests` raise `NotSupportedError: FOR UPDATE cannot be applied to the nullable side of an outer join` inside `_locked()` (P20), so no send can run on PostgreSQL at all. (c) On SQLite the same two parallel tests fail with `OperationalError: database table is locked` (P22). (d) Real send path on SQLite with `record()` forced to fail after the number was taken: status stayed `signed`, number `None`, counter row not created; the retry got `QT/2026/11/0001`. The "one test passed" in the PostgreSQL run is the lead test (Obj 8). |
| Returned quotations go back to the preparer with the notes visible | PASS | `request-changes` without a comment: 400; with "Add a second visit": status `changes_requested`, the preparer's `GET` shows `review_comment: "Add a second visit"`; the preparer then starts again, which opens a new version (3 in total), and draft, submit, sign and send give number `QT/2026/11/0001`. A drawn signature that is not a real PNG: 400. A second send: 400. |

Who can do what (2xx cells only; CEO, MKT, OH, OM never succeed; HH = HR head, HM = HR member, CH = Commercial head, CM = assigned Commercial member, SA = Super Admin):

| State | assign | start | draft | submit | request-changes | sign | cancel | send | outcome |
|---|---|---|---|---|---|---|---|---|---|
| requested | HH,SA | HH,HM,SA | | | | | CH,SA | | |
| in_preparation | | | HH,HM,SA | HH,HM,SA | | | CH,SA | | |
| in_review | | | | | CH,SA | CH,SA | CH,SA | | |
| changes_requested | HH,SA | HH,HM,SA | | | | | CH,SA | | |
| signed | | | | | | | CH,SA | CH,CM,SA | |
| sent / waiting | | | | | | | CH,SA | | CH,CM,SA |
| confirmed, rejected, cancelled | | | | | | | | | |

### Obj 15: document generation

Rendered 36 files (quotation, contract, meeting report; final and draft; PDF and DOCX; `en`, `ar`, `both`) through the real endpoints, saved them, converted the PDF pages to PNG with PyMuPDF and looked at them. There is no LibreOffice or Word on this machine, so the Word files were checked at XML level only.

| Done when | Status | Evidence |
|---|---|---|
| Arabic renders correctly (connected letters, right to left) in PDF and Word | **PARTIAL** | PDF, `lang=ar`: letters are joined (reshaper + bidi + the bundled IBM Plex Sans Arabic), the page runs right to left, tables mirror, mixed Arabic/English/number lines come out in a sensible order (client name, totals, the bilingual payment-terms line). Fonts embedded: Plex Regular and Bold. Word, `lang=ar`: 88 `w:bidi` paragraphs, 72 `w:rtl` runs, `w:bidiVisual` tables and a complex-script font, so Word will shape and order it. **Defect: `lang=both`.** The Arabic paragraphs of the contract body are drawn left to right and left-aligned: the image shows the full stop and the list numbers on the wrong side ("`.تم إبرام ... والعميل`", "`.نطاق الخدمات 1`"), and the `both` DOCX has **0** `w:bidi` and **0** `w:rtl` markers (P21). Word could not be rendered here (U8). |
| Draft vs final documents are visibly different | PASS | Quotation `in_review` and meeting report `draft`: a large pale "DRAFT / مسودة" diagonal watermark on every page, and empty signature areas. Signed quotation, signed contract and approved report: no watermark, with the signature image, stamp, signer name and date. DOCX drafts carry a watermark shape in the header (found `مسودة` and a `v:shape`); finals have none. Watermark rules: quotation until the head signs, contract until the CEO signs, report until the CEO approves (`documents/builders.py`). |
| Files are served only through permission-checked endpoints, never a public URL | PASS | Every document is an authenticated action: `GET /quotations/<id>/document/`, `/contracts/<id>/document/`, `/meeting-reports/<id>/document/`, plus the portal copies. Headers: `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`, `Cache-Control: private, no-store`. As anonymous: 401 on all three. Quotation and contract: Marketing, Operation head and Operation member 403; a Commercial member who is not on the lead 404; reports 404 for everyone outside the lead's visibility. Id enumeration 1 to 6 as an Operation member: all 403/404. Guessing the stored file (`2026/11/<hash>.png`) under `/media/`, `/private/`, `/files/`, `/api/v1/files/`, `/` and `/static/../`: 404 each; files live in `PRIVATE_MEDIA_ROOT`, outside `MEDIA` and `static`. Bad `fmt` or `lang`: 400. |
| Uploaded signed copy overrides the generated document | PASS | After `POST /quotations/<id>/signed-copy/`: `GET ...?fmt=pdf` returns the upload (`X-Document-Source: signed-copy`); `fmt=docx` and `?generated=1` still return the generated file. Contracts try `final_signed` first, then `client_signed_copy` (`contracts/views.py`). |

Note on the totals in my draft sample: they show 0.00 because my probe wrote the lines directly without the service that computes version totals; the contract sample, which stores a total, prints 770.00 JOD. Not an application defect. Also, in a right-to-left line, `50%` is drawn as `%50`; Arabic usage varies, so I did not count it.

### Obj 16: post-quotation status, meeting reports, contracts

| Done when | Status | Evidence |
|---|---|---|
| A sent contract blocks the client status from leaving Confirm (409) | PASS | Confirm (after a completed meeting) created contract `CT-0001` (`requested`). After HR drafted, Commercial returned with a note and re-confirmed, HR sent it (number `CT/2026/11/0001`): Waiting and Rejection both answer **409 `contract_sent`**. Before that, Waiting without a date 400, with a past date 400, +7 days 200 and a follow-up appointment on 2026-11-24; Rejection without a reason 400; with a reason 200 and the open follow-ups cancelled; Confirm with no completed meeting 400; a member who is not on the lead, Marketing, HR: 403. Confirm twice made one contract. |
| The contract draft contains the services and fees of the signed quotation | PASS | Version 1 of the contract: currency USD, total 1160.00, payment terms "Net 30", services `Bookkeeping 1000.00` and `Payroll 160.00`, taken from the confirmed quotation's last version, rendered into the country template (`contracts/services.py:123 _prefill`). A small defect: the template link is not saved (P23). |
| Each signer can act only at their step | PASS | Contract matrix: 10 states x 10 actions x 8 roles (rolled back). **0 successes outside the legal (state, role) set and 0 legal pairs refused.** HR drafts and sends to the client, the Commercial head confirms and returns, a Commercial member cannot confirm (403), only the CEO approves or returns, only HR hands over, only the head cancels. Meeting report: report on a meeting that is not completed 400; one per appointment (second one 400); CEO approve before the head signs 400; a Commercial member or the CEO signing 403; the head approving 403; edit after signing 400; CEO return without a comment 400, with a comment the author sees it; author edits, head re-signs, CEO approves. HR and Marketing get 404 on the report. |

Other checks: one yearly sequence per key, contract numbers independent of quotation numbers (`YearSequence` rows `quotation` and `contract`). Country templates: the mechanism exists (`template_for(country)` then the `*` default) and a freshly migrated database contains only the `*` template, so "templates differ by country" is supported but not populated. Documents tab (`documents/views.py`): anonymous 401, Operation head 404, a Commercial member who is not on the lead 404, Commercial head 200; each kind is filtered with its own `visible_q`.

### Obj 17: process tracking and SLA alerts

| Done when | Status | Evidence |
|---|---|---|
| Each alert fires once per case, at the right time, reproducible by moving the clock | PASS (with P14 and P15) | `timezone.now` mocked: HR alert at +59 min sent 0, at +61 sent 1, at +62 and +300 sent 0. Commercial alert (in review): +30 0, +61 sent (the count of 2 at that step also included the new-case HR alert below), +90 0. Appointment 10 minutes past its time: +30 0, +61 sent 1, again 0. Re-assigning an unsubmitted quotation starts a new case (a second `urgent_hr` went to the new assignee). Dedupe keys carry the start of the clock (`urgent-hr:<id>:<assigned_at>`), `notify(None, ...)` is a no-op so a missing Commercial head does not crash. Thresholds come from `URGENT_*_MINUTES` (default 60). Caveats: no scheduler in compose (P14) and the dedupe check is not atomic (P15). |
| The activity feed can be filtered by employee and by action type | PASS | `?actor=` returned 5 rows, all by that person; `?action=outcome_qualified` 5 rows, all matching; both together 5; `?kind=lead` 33 rows, all leads; `from`/`to` bounds work (tomorrow 0, today 61). Filters endpoint lists people, actions and kinds. Only the CEO and Super Admin can read it (others 403). A made-up `kind` is silently ignored (P25). |

Administration page numbers (`GET /admin/tracking/`): lead pipeline `{qualified: 18}` and client pipeline `{undecided: 4, confirm: 1}` equal independent counts from the database; each person's 7-day count equals the audit table; late quotations, missed appointments and overdue follow-ups use the same thresholds as the alerts. "Changed today" shows at most 50 rows of 61 with no marker that more exist (P25). The history is append-only: `AuditEntry.save()` on an existing row and a queryset `delete()` both raise `ImmutableError`.

## 1d. Phase 4: Handover, KYC, recurring work, execution (objectives 18 to 21)

How it was run: one seeded deal ("Alpha Trading": lead, accepted, client with a portal login, confirmed quotation with a signed copy, signed contract with three attachments, instalment, payment, salaries, a draft payroll run, handover, project PRJ-0001 with a primary and a support person, recurring task, task, published deliverable). Money and file sentinels (`777123.45`, `31337.31`, `4242.42`, `9191.91`, `SECRETCLAUSE`, `SECRETCONTRACTFILE`, ...) were planted so a leak can be found by text search, not only by field name. Everything ran in-process (Django test client, no server, port 8000 untouched) against **both** SQLite and PostgreSQL 16.2. Where the two differ it is said explicitly; the single cause of every difference is P20.

### SQLite vs PostgreSQL: what differs in Phase 4

| Check | SQLite | PostgreSQL 16.2 |
|---|---|---|
| Confidentiality crawl (6 identities, same hits) | identical results | identical results (after the seed used ORM fallbacks for the crashing steps) |
| `contracts.hand_over`, `create_recurring`, task start/submit, `publish`, `generate_due`, `escalate_overdue`, every task lifecycle call | work | **crash**: `NotSupportedError: FOR UPDATE cannot be applied to the nullable side of an outer join` (P20) |
| Same calls with `select_for_update` forced to `of=("self",)` (audit-only monkeypatch, no repo change) | not needed | **all work, results identical to SQLite** |
| Repo tests: `operations.tests_privacy`, `tests_handover`, `tests_kyc_staffing`, `tests_kyc_migration`, `tests_handover_migration` (42) | 42 OK | 32 of 42 error |
| Repo tests: all Phase 4 modules (122: `operations.tests`, `tests_lifecycle`, `tests_recurrence_*`, `tests_reports_and_log`, `reports.tests`, `audit.tests_tracking`) | **2 fail** (P27) | **43 error** (P20), same 2 date failures hidden behind them |
| KYC gate, one-primary constraint, report parity, immutability | same | same (constraint error class differs: SQLite `IntegrityError`, PostgreSQL `UniqueViolation` / `CheckViolation`) |

### Obj 18: handover and confidentiality

| Done when | Status | Evidence |
|---|---|---|
| A test checks every Operations endpoint, report and notification for financial fields | PARTIAL | The repo has `operations/tests_privacy.py` (walks Operations endpoints, reports, notifications). It passes on SQLite (42 OK with the other Obj 18/19 modules) but **errors on PostgreSQL** because its setup goes through the crashing services (P20). My own crawl (below) is broader than the repo test. |
| The original contract file is unreachable from Operations endpoints | PASS | As `operation_head`, `operation_member`, `operation_member2` and the portal client: every GET endpoint with ids 1 to 8, `files/?target=<each registered target>:<id>` (including `contract:1`, `archived=1`), `comments/`, `activity/`, `documents/`, `search/?q=...`, `notifications/`, 5 reports x csv/xlsx/pdf (and `lang=ar`), `/lookups/*`, `hr/*`, `payments/*`. Result: **0 contract file names, 0 sentinel strings from the contract or quotation files**, in JSON, in xlsx XML and in PDF text. The `handover` target is registered `can_attach=False` (`operations/apps.py`). Identical on both databases. |

Crawl detail (both databases): no price, contract value, payment figure or salary reaches any of the three Operations identities. `/lookups/services/` returns names only (the `default_unit_price` and `currency` fields are removed unless the caller holds `settings.manage` or `quotation.prepare`; `lookups/views.py` `PRICE_FIELDS`). `payments/*` and `hr/payroll*` returned no money to Operations (hits: none). The handover and project serializers are explicit whitelists (`operations/handover_api.py`, `operations/serializers.py`); nothing is read from the contract, quotation or payments. The positive controls behave as expected (commercial head and CEO do see the money), so the scan can detect a leak. The portal client sees only its own quotation and contract (by design, not a leak).

What the crawl cannot stop (P29): free text typed by Commercial (`client.notes`, `decision_note`, handover `services`/`scope_notes`/`contacts`, comments on the client) is shown to Operations unfiltered. A salesperson who writes "agreed 777,123 JOD" in the handover notes puts the value in front of Operations. The brief's Done-when item is about endpoints and fields, so this is a Medium design gap, not a failure. The contract reference (`CT-1`) appears in the client's activity trail (P30, Low): a reference, not a value.

### Obj 19: KYC, legal documents, projects and assignment

| Done when | Status | Evidence |
|---|---|---|
| Onboarding can be approved only once KYC is verified | PASS | Client starts `onboarding`. `PATCH /clients/<id>/ {"status":"active"}` returns 200 but status stays `onboarding` (`status` is read-only in the serializer). Verifying 4 of the 5 required items leaves `onboarding`; verifying the 5th flips to `active` and sets `activated_at` (`services.recompute_status`). Verifying with no upload: 400. N/A without a reason: 400. Document needing an expiry date: no date 400, past date 400. Resetting one verified item sends the client back to `onboarding`. `expire_documents` marks 2 expired items and the client returns to `onboarding`; a second run marks 0. A new upload on an expired item becomes version 2, version 1 `superseded`, item `uploaded` (needs a fresh verification). Commercial cannot upload to a checklist item (403). Same on PostgreSQL. |
| The database prevents two primary employees on one project | PASS (raw SQL, both engines) | Raw `INSERT INTO operations_projectstaff` of a second active primary: SQLite `IntegrityError`; PostgreSQL `UniqueViolation` (partial unique index `project_one_active_primary`). Same person active twice: refused. Ended row with no `end_reason`: refused (PostgreSQL `CheckViolation`). `bulk_create` of two primaries: refused. **Two simultaneous raw inserts** on a fresh project from two connections: `{'ok': 1, 'refused': 1}`, one active primary left (PostgreSQL and SQLite). |
| Replacing the primary requires a reason; assignment history kept | PASS | `POST /projects/<id>/primary/`: no reason 400, same person 400, Operation member 403, with reason 200. History after replacing: `operation_member primary ended "workload"`, `op2 support ended "Became the primary employee."`, `op2 primary active`. Adding the same support person twice: 200 then 400. |
| "A versioned KYC record (request info, mark supplied, verify)" | PARTIAL | Documents are versioned and verified (above). There is no separate KYC "request info / mark supplied" step: the states are pending, uploaded, verified, expired, not applicable. The checklist is the KYC record. Record as a deviation (D12). |

### Obj 20: recurring work generator

| Done when | Status | Evidence |
|---|---|---|
| Running the generator repeatedly creates no duplicates | PASS on SQLite; **FAIL on PostgreSQL as shipped** | SQLite: rule started 75 days ago, 5 runs create `[3, 0, 0, 0, 0]`, 3 rows, 3 distinct (version, period). Raw duplicate (rule, version, period): `IntegrityError`. 4 simultaneous generators on SQLite: 3 of 4 threads got `OperationalError` (database is locked, a SQLite limit) and 4 rows with 4 distinct periods (no duplicate). PostgreSQL as shipped: all 5 runs and all 4 threads raise `NotSupportedError` (P20), 0 tasks. PostgreSQL with `of=("self",)`: `[3, 0, 0, 0, 0]`, 3 rows, raw duplicate `UniqueViolation`, 4 simultaneous generators no errors, 4 rows, 4 distinct periods. |
| Unit tests cover month ends, leap years, weekends and holidays | PASS, with P27 | `operations/recurrence.py` is pure functions; `tests_recurrence_rules`/`engine` cover them. Direct checks: monthly from 31 Jan 2027 gives 31 Jan, 28 Feb, 31 Mar, 30 Apr (no drift); from 31 Jan 2028 gives 29 Feb; yearly from 29 Feb 2028 gives 28 Feb 2029 and 29 Feb 2032; a Friday or Saturday moves to Sunday; a Saturday holiday followed by a Sunday holiday moves to Monday. **Two repo tests fail today on SQLite** (Wednesday 18 Nov 2026) because they assume "today plus a month / plus 10 days" is a working day (P27). |
| Editing a rule leaves past tasks untouched | PASS | `update_recurring` (monthly to weekly) bumps the rule to version 2; the 3 version-1 tasks are identical before and after (id, due date, title); new tasks are version 2 and dated today or later. Both engines (PostgreSQL with the P20 patch). |
| Recurrence kinds in the brief: daily, **working days**, weekly, monthly (fixed day, **first/last working day, nth weekday**), quarterly, yearly; rule's own weekend/holiday **policy**; generator **days ahead** configurable | PARTIAL | Offered: daily, weekly, every 2 weeks, monthly, quarterly, every 6 months, yearly, every N days. No "working days", no first/last working day, no nth weekday, no per-rule policy field (one fixed policy: move to the next working day; a daily rule skips closed days), no "days ahead" setting (tasks are created on the due date). See P31, D11. |

### Obj 21: execution, review, monitoring

| Done when | Status | Evidence |
|---|---|---|
| An overdue task escalates to the manager, then to the CEO after the threshold, once each | PASS on SQLite; **FAIL on PostgreSQL as shipped**; PASS on PostgreSQL with the P20 patch | One overdue task, clock moved: 1 day late 0 escalations, 2 days late level 1 (the Operation head notified), 2 again 0, 3 and 4 0, 5 days late level 2 (CEO **and Super Admin**, everyone with `settings.manage`, notified), repeats 0, 30 days late 0. `Escalation` rows are exactly levels 1 and 2. Raw duplicate (task, level): `UniqueViolation`. 4 simultaneous escalation jobs on a 10-day-late task: levels `[1, 2]`, no errors (patched PostgreSQL). Unpatched PostgreSQL: every call raises `NotSupportedError` and nothing escalates. The thresholds are `getattr(settings, "TASK_ESCALATION_DAYS", (2, 5))` and no settings file defines it, so they are changed only by editing code or the environment, not in the CEO's settings screen (P31). |
| Reports in JSON, Excel and PDF show the same numbers | PASS | For `funnel`, `revenue`, `forecast`, `operations`, `hr`: every series point compared across JSON, CSV, XLSX and the PDF text (label and value on the same line). **51 rows on SQLite, 48 on PostgreSQL, 0 mismatches** (the Excel cell holds `100` where JSON has `100.0`; the same number). All formats are built from the same flat rows (`reports/series.py csv_rows`; `reports/exports.py`). Arabic PDF (`lang=ar`) returns 200. |
| Task lifecycle, notes, attachments, waiting, blocked, submit, approve / return | PASS on SQLite; patched PostgreSQL | Start, progress 40, wait (reason required: 400 without), resume, block, resume, submit, own approve 403, other member submit 403, return (comment required: 400 without), submit again, approve, approve again 400. Note and attachment by the assignee 201, by another member 403. Unpatched PostgreSQL: start, progress, wait, resume, block, submit, approve, return all raise `NotSupportedError`. |
| Deliverables published to the portal and acknowledged | PASS on SQLite (seed), CANNOT-VERIFY end to end on PostgreSQL | Seeded through `lifecycle.publish`; it appears in the portal client's crawl of `portal/deliverables/` (no file or money leak found there). `publish` crashes on PostgreSQL as shipped (P20), so the seed used an ORM fallback there. |
| An append-only activity log | PARTIAL | Python layer: `entry.save()`, `entry.delete()`, `queryset.update()`, `queryset.delete()`, `bulk_update()` all raise `ImmutableError`; deleting a user who has audit rows raises `ProtectedError`. API: POST, PUT, PATCH, DELETE on `/activity/` and `/admin/activity/` return 405, and `/admin/activity/<id>/` returns 404, as CEO and as Super Admin. **Raw SQL `UPDATE` and `DELETE` on `audit_auditentry` both succeeded (rows=1) on SQLite and PostgreSQL**: the row was changed, then removed (P28). `/admin/` answers 302 (a login redirect), `/django-admin/` 404. |

## 1e. Phase 5: General tasks (objective 22)

Run in-process on SQLite and on PostgreSQL 16.2 with the same script; **the two outputs are identical line for line** (`diff` empty). The task code locks only non-null relations, so P20 does not touch it.

### Obj 22: work tasks with attachments

| Done when | Status | Evidence |
|---|---|---|
| A .exe renamed to .pdf is rejected | PASS (with P33) | Upload to a task as the assignee: `setup.pdf` containing `MZ...` (an exe header) returns **400 "This file doesn't look like a real PDF file."**; `setup.exe` 400 (type not allowed); a real PDF renamed `photo.png` 400 "doesn't look like a real PNG file"; empty `empty.pdf` 400 "This file is empty."; a 10 MB + 44 byte PDF 400 "over 10 MB"; `x.html`, `x.svg`, a file with no extension 400. Valid PDF, PNG and a PK-headed `.docx` 201. A name like `..\..\p.pdf` is stored as `p.pdf` (path removed). Download comes back `application/pdf` with `X-Content-Type-Options: nosniff`. |
| A head cannot assign a task to another department | PASS | `hr_head` to `commercial_member` **400** `{"assignee": ["You can't give a task to this person."]}`; `hr_head` to the CEO 400; `commercial_head` to `operation_member` 400; a nonexistent id 400. `hr_head` to an HR employee or to themselves 201. A head's assignee list holds only their own department. A plain member and Marketing get 403 when creating. The CEO (and the Super Admin, who also holds `gtask.assign_any`) can assign to all 11 people. Re-assigning an existing task across departments: head 400, CEO 200. |
| Counters (not done / overdue / done / done late) are correct | PASS | Six tasks for one person: 2 overdue, 1 due today, 1 open, 1 done on time, 1 done late. Expected `open 4, overdue 2, due_today 1, done 2, done_late 1`. `counters/` for the assignee returned exactly that; the head's and the CEO's `team` block returned the same; the head's own `mine` was all zeros. `?overdue=1` gave 2, `?status=done` gave 2. |
| Only the assignee can tick Mark as done | PASS | CEO 403, head 403, Super Admin 403, other departments 404, assignee 200, ticking again 400. |
| Ticking after the deadline is recorded as done late | PASS | Deadline two days ago: `done_late = true`, history action `gtask_done_late`. On the deadline day: `false`. With the clock at 00:30 Amman the day after the deadline: `true`. A done task cannot be edited (400), so the flag cannot be rewritten. |
| Overdue tasks send one urgent alert; changing the deadline re-arms it | PASS | Daily job run at deadline +2, +3, +3, +4, +10 days: sent `2, 0, 0, 0, 0` (one to the assignee `gtask_overdue`, one to the person who gave it `gtask_overdue_given`). The head moved the deadline: `alert_round` 0 to 1; after the new deadline passed the job sent 2, then 0. The assignee cannot change the deadline (403). A done task gets no alert. |
| Files are checked by content, not just extension, with size and count limits | PARTIAL | Content: only the first 4 to 8 bytes are compared (P33). Size: 10 MB limit works. **Count: none** (P32): 48 files were accepted on one task. |

## 1f. Phase 6: Quality and delivery (objectives 23 and 24)

### Test and check results (Python 3.11.16, Node v24.14.1, Chrome installed on this machine)

| Run | Result |
|---|---|
| Backend `manage.py test` on **SQLite**, 851 tests (`config.settings.test`) | 849 OK, **2 FAIL** (P27), 1 skipped. 940 s. |
| Backend `manage.py test` on **PostgreSQL 16.2**, same 851 tests | 652 OK, **198 ERROR**, 0 fail, 1 skipped. 1,408 s. All 198 are `NotSupportedError: FOR UPDATE cannot be applied to the nullable side of an outer join` (P20); the two `RuntimeError` lines in the log are the tests' own expected log output. The 2 SQLite failures are hidden behind P20 errors on PostgreSQL. |
| `python -m pytest -q` on SQLite | 849 passed, 2 failed (the same two), 1 skipped. 586 s. Not repeated on PostgreSQL (same tests as `manage.py test`). |
| Modules that fail on PostgreSQL (errors) | quotations 66, contracts 24, operations 70, documents 8, hr 7, appointments 6, meetings 5, audit 5, core 7. |
| Vitest | **240 of 240 passed** (18 files). It cannot start from my `R:` drive alias (vite resolves the real path); run from the real path it passes. Environment artefact, not a repo problem. |
| `npm run typecheck` | exit 0 |
| `npm run lint` | exit 0 |
| `npm run i18n:check` | **exit 1**, 2 problems (P4) |
| `npm run build` | exit 0 (Next 16.4.6) |
| `makemigrations --check --dry-run` (README command) | **fails** on a clean clone (P34) |
| `spectacular --validate --fail-on-warn` (README command) | exit 0 |
| `scripts/secret_scan.py` | 0 findings |
| Playwright E2E run 1 (fresh database) | 15 passed, **1 failed** (spec 03, P35), 66 did not run |
| Playwright E2E run 2 (same database) | 23 passed, **1 failed** (Arabic setup, P37), 58 did not run |
| Playwright E2E run 3 (same database) | identical to run 2 (the failure is repeatable) |
| E2E scans (specs 04 and 06, English and Arabic, `--no-deps`, same database) | 23 passed, 15 failed: 6 axe violations, 2 horizontal overflows, 1 missing element, 2 HTTP 502 from the dev server, 4 timeouts at 7 min (P39; the last 6 are load on this machine, not verdicts) |
| `pip-audit` on `requirements.txt` and `requirements-dev.txt` | No known vulnerabilities |
| `npm audit` | 20 (2 critical, 11 high, 7 moderate), **all in devDependencies**; `npm audit --omit=dev` finds **0** (P40) |

### Obj 23: testing

| Done when | Status | Evidence |
|---|---|---|
| All suites pass from a clean database | **FAIL** | SQLite 849 of 851, PostgreSQL 652 of 851, `i18n:check` exit 1, `makemigrations --check` fails, E2E fails (table above). Vitest, typecheck, lint, build pass. |
| E2E can run repeatedly on the same database | **FAIL** | Run 2 and run 3 on the database run 1 left behind both stop in the Arabic project: "CEO signs in, uploads the company stamp", the page is rendered in English (sidebar shows "Home", "Users") so the Arabic text is never found (P37). Run 1 on a fresh database fails earlier at the demo-data spec (P35). |
| Every permission rule has a test that proves the denial | PARTIAL | 69 capabilities. `core/tests_capabilities.py` generates, from the URL table, a denial for each: every endpoint declares its capabilities or is public on purpose; a role with no capability reaches only open endpoints; removing any one capability closes every endpoint that names it; the Super Admin holds all. About 103 further denial-style tests sit in the modules. The 14 object-level rules (the access registry: client, lead, quotation, contract, project, task, gtask, ...) are tested module by module, not generated, so I cannot prove one for each. |
| E2E journey in the brief: setup, admin creates CEO, CEO first login creates an employee, employee first login, Arabic switch persists, access denied in UI and API, deactivation revokes tokens | PARTIAL | Covered: Super Admin and CEO sign in, CEO creates the seven roles, each is forced to change the temporary password, forbidden creations refused (API), leads journey, keyboard, console hygiene. **Missing:** deactivation revoking tokens (no spec mentions it), an explicit "Arabic persists" step (Arabic is a second pass of the whole suite), access denied shown in the UI. The CEO is created by the `seed` command, not by the admin through the UI (D13). |
| The E2E suite is part of the repository | FAIL | At HEAD `frontend/e2e/` and `frontend/playwright.config.ts` are untracked; `next.config.ts`, `tsconfig.json` and `useDialog.ts` carry uncommitted changes the suite needs (`NEXT_DIST_DIR`). A fresh clone has an `e2e` script and nothing to run (P38). |

### Obj 24: documentation and deployment

README followed literally in a clean `git clone` of HEAD, no Docker, without touching port 8000 (server on 8201, web on 3201):

| README step | What happened |
|---|---|
| `python -m venv .venv` then `pip install -r requirements.txt` with the machine's default `python` (**3.15.0**; the README says "Python 3.11+") | **Fails**: PyYAML has no wheel and wants Microsoft C++ Build Tools. |
| Same steps with Python 3.11.16 | OK. `migrate` OK. |
| `seed`, `createsuperuser --noinput`, `list_users` with the README's variables | OK (CEO and Super Admin listed). |
| `runserver` (on 8201 instead of 8000) | `GET /api/v1/health/` 200; CEO login 200. |
| `cd frontend`, `npm install` | OK (3 min). |
| `npm run build`, `next start` on 3201 | OK. Login page `<html lang="en" dir="ltr">`; login through the Next proxy 200 **only after setting `BACKEND_URL`** (the README's `NEXT_PUBLIC_API_URL` is read by nothing, P6). |
| "Tests and checks": `python -m pytest -q` | **`No module named pytest`**: the dev packages are in `requirements-dev.txt`, which the README never mentions. |
| `makemigrations --check --dry-run` | Reports pending changes (P34). |
| `spectacular --validate --fail-on-warn --file NUL` | OK on Windows (`NUL` creates a file on macOS or Linux, not run there, U17). |
| `python manage.py seed_demo_data` | **Crashes** on an empty database (P35). |
| `docs/ACCEPTANCE_MATRIX.md`, `docs/ACCEPTANCE_REPORT.md` | Do not exist (H2). |

**Questions a classmate would have to ask:**
1. Which Python version? (3.15 fails; 3.11 works; the Docker image uses 3.12.)
2. How do I install pytest? (`requirements-dev.txt`.)
3. Why do I see "pending migrations" right after cloning? (P34.)
4. Port 8000 is taken. Which variable moves the proxy? (`BACKEND_URL`, not the one in the README.)
5. Why does the demo data command crash? (P35.)
6. How do I run the browser tests? (There is no config in the repository, and it needs installed Chrome and `E2E_PYTHON`.)
7. Where are the two acceptance documents the README links?
8. On macOS or Linux, what replaces `NUL` and `.venv\Scripts\activate` inside the checks block? (Only the activate line is given for both.)
9. Which Node version? (README says 20+; only 24 was tried, U19.)

| Done when | Status | Evidence |
|---|---|---|
| A classmate can run the project from the README alone, without asking questions | **FAIL** | The backend and frontend start (Python 3.11, with `BACKEND_URL`), but the nine questions above need an answer first. |
| The Swagger page lists every endpoint with its request/response shape | PARTIAL | Generated schema: 244 operations, every one with responses, none present in the schema that is not in the URL conf. Compared with the URL conf: 27 (method, path) pairs absent, 12 of them the DRF index pages and 15 PUT/DELETE pairs on viewsets (most likely disabled by `http_method_names`; not checked one by one). 32 POST/PUT/PATCH operations have no request body (actions such as `complete`, `logout`; plausible). **140 of 244 operations have no summary or description** (P41). The docs are served only to people with `settings.manage`. |
| Production checklist: TLS at a reverse proxy, only the frontend exposed, strong secrets, backups, correct proxy count, dependency audits | PARTIAL | `docs/DEPLOYMENT.md` states TLS at one reverse proxy, `DJANGO_SECRET_KEY` 50+ characters, production settings that refuse a guessable key, DEBUG or `*` hosts, backup of database and `PRIVATE_MEDIA_ROOT` together for 14 days, `TRUST_X_FORWARDED_FOR`. There is no single checklist, no dependency-audit step (the objectives matrix itself says "audits not run"), and the proxy setting is a yes/no, not a proxy count (P3). Compose publishing only the frontend was checked in Phase 1 (P1 stops the stack from starting). |
| Dependency audits | PASS | `pip-audit`: none. `npm audit`: 0 in production, 20 in dev tooling (P40). |

## 2. Problems (sorted by severity)

Totals: 3 Blocker, 6 High, 16 Medium, 16 Low (41 problems), plus the hygiene findings H1 to H4 in Step 0. P20 and P26 are one defect seen from two phases. Evidence for each is also in the objective tables above.

| ID | Sev | Obj | Problem | Evidence | One-line fix |
|---|---|---|---|---|---|
| P1 | **Blocker** | 1 | Compose backend is unhealthy with the shipped defaults, so the frontend never starts. | Healthcheck host `127.0.0.1:8000` not in `DJANGO_ALLOWED_HOSTS=localhost,backend`; reproduced 400 vs 200 above. `docker-compose.yml:36-40`, `.env.example`. | Add `127.0.0.1` to the default allowed hosts, or make the healthcheck send `Host: localhost`. Then run `docker compose up` once. |
| P20 | **Blocker** | 14, 16, 11, 18, 22, 24 | `select_for_update().select_related(<nullable relation>)` raises on PostgreSQL, so every state transition that locks its row this way fails there. SQLite ignores row locks, so no SQLite test can see it. | Reproduced on PostgreSQL 16.2: `django.db.utils.NotSupportedError: FOR UPDATE cannot be applied to the nullable side of an outer join`. I ran the exact queries of all 13 lock sites: **7 fail** (`quotations/services.py:92` via `lead__assigned_to`; `contracts/services.py:47`; `appointments/services.py:135,159`; `hr/leave.py:124` via `user__department`; `meetings/services.py:38` via `signed_by`; `operations/lifecycle.py:43`; `operations/services.py:345`), 6 pass. The repo's own `ConcurrentNumberTests` and both contract numbering tests error with it (3 of 4 tests in the PostgreSQL run). The shipped compose stack uses PostgreSQL, so in it: sending a quotation, every contract step, meeting-report sign/approve, appointment changes, leave decisions and operations task changes would answer 500. | Lock only the row: `.select_for_update(of=("self",))` at the 7 sites (or lock first and `select_related` in a second query), then run the whole suite on PostgreSQL (U9). |
| P26 | **Blocker** | 18, 20, 21 | P20 reaches all of Phase 4 on PostgreSQL: handover creation (`hand_over`), the recurring generator, escalation and every task lifecycle action crash, so the daily job, escalation and the task board do not work there. | Unpatched PostgreSQL 16.2: `generate_due` x5, `escalate_overdue` x9 and all lifecycle API calls raise `NotSupportedError`; 0 tasks and 0 escalations created. With `select_for_update` forced to `of=("self",)` (audit-only monkeypatch) every result equals SQLite. Repo Phase 4 tests: 43 of 122 error on PostgreSQL (32 of 42 in the Obj 18/19 modules). Sites: `operations/lifecycle.py:43`, `operations/services.py:345`. | Same fix as P20: `.select_for_update(of=("self",))` at the seven sites, then run the suite on PostgreSQL in CI. |
| P2 | High | 6 | Production settings replace the renderer, so the error envelope is lost for every DRF error. | `config/settings/production.py:55` sets `DEFAULT_RENDERER_CLASSES` to plain `JSONRenderer`, dropping `EnvelopeJSONRenderer`. Reproduced under production settings. `core/tests_deploy.py` does not test it; all other tests run with test settings. The frontend `api.ts:76` quietly falls back to the raw shape, which hides it. | Keep `EnvelopeJSONRenderer` in production (only drop the browsable renderer), and add a test that runs the envelope checks under production settings. |
| P3 | High | 6, 24 | Per-IP throttle is either global or bypassable. | Through the Next proxy, Django sees the frontend container address; Next forwards the client's own `X-Forwarded-For` and adds none. **TRUST=0 (compose default):** 20 failed logins with different identifiers made a correct login from another user return 429. **TRUST=1:** `client_ip` takes the *leftmost* `X-Forwarded-For` value (`audit/events.py`); 25 failures through the proxy with rotating headers were recorded under 25 fake IPs and never blocked. The brief asks for a correct proxy count; only a boolean exists. | Use the right-most-minus-N entry (`TRUSTED_PROXY_COUNT`), have the proxy set the header, and document it. |
| P34 | High | 23, 24 | The README's own check `makemigrations --check --dry-run` fails on every machine except the author's, and four migrations contain the author's local Windows path. | Clean clone, Python 3.11: reports `Alter field ... on contract / quotation / attachment / meeting`. `files/migrations/0001_initial.py`, `contracts/migrations/0003`, `quotations/migrations/0003`, `meetings/migrations/0001` serialise `FileSystemStorage(location=PureWindowsPath('C:/Users/<author>/...'))` because `files/models.py:10` builds the storage from `settings.PRIVATE_MEDIA_ROOT`. | Give the storage a `deconstruct` that omits the location (or use a callable `storage=`), then regenerate those four migrations without the path. |
| P35 | High | 23, 24 | `manage.py seed_demo_data`, named in the README, crashes on an empty database. | Playwright run 1 and by hand: `Leads: 7 added.` then `TypeError: sign() missing 1 required positional argument: 'signature'` at `core/management/commands/seed_demo_data.py:136` (`quotations/services.py:381 sign(actor, q, signature)`). The browser suite stops at this spec; 66 tests did not run. A second run passes only because the first left partial data. | Pass a signature (the seed already has a PNG helper in the tests) or give `sign` a default for seeding. |
| P36 | High | 24 | The README cannot be followed as written without asking questions. | See the nine questions in section 1f: Python 3.15 fails to install PyYAML; `pytest` is not installed by the README's steps; `NEXT_PUBLIC_API_URL` is read by nothing (P6); `makemigrations --check` fails (P34); `seed_demo_data` crashes (P35); the two linked acceptance documents do not exist (H2); no browser-test instructions that work from a fresh clone (P38). | State the supported Python range (3.11 to 3.13), add `pip install -r requirements-dev.txt` to the test block, fix the variable name, and fix P34, P35, P38. |
| P37 | High | 23 | The browser suite is not repeatable on the same database: the Arabic pass fails. | Runs 2 and 3 on the database run 1 left behind: `[ar-setup] CEO signs in, uploads the company stamp` fails (`getByText('الختم موجود...')` not found); the page snapshot shows the English sidebar. 58 later tests did not run, both times. | Find why the CEO's saved language (English from the first pass) overrides the Arabic cookie in the second pass; the suite should set the account language the same way it does for the Super Admin. |
| P4 | Medium | 7, 23 | `npm run i18n:check` fails at HEAD. | Exit 1; `src/lib/i18n.test.tsx:33-34` vs `scripts/check-i18n.mjs`. | Make the checker skip `*.test.*` files. |
| P5 | Medium | 6 | Lockout counters are not atomic across workers. | `ratelimit.record_failure` uses file-cache `incr` (read then write). 40 parallel failure records gave a counter of **36**, not 40 (Windows; the code path is the same on Linux). Counters are also per container, so several containers do not share them (documented in `DEPLOYMENT.md`). | Use Redis (atomic `INCR`) or a database counter. |
| P6 | Medium | 24 | README and `frontend/.env.example` tell users to set `NEXT_PUBLIC_API_URL`; nothing reads it. The proxy reads `BACKEND_URL`. | `grep NEXT_PUBLIC_API_URL src next.config.ts` finds nothing. | Document `BACKEND_URL`. |
| P7 | Medium | 2 | Super Admin is not marked "full access" and does not get a new capability automatically. | `Role` model has no flag; probe above. | Add `Role.full_access` and treat it as holding every capability in `has_capability`. |
| P14 | Medium | 11, 17, 24 | The Docker stack never runs `process_notifications`, so no appointment reminder and no 60-minute urgent alert is sent unless the operator adds cron. | `docker-compose.yml` has db, backend, frontend only; `docs/DEPLOYMENT.md:62` says it "must run every few minutes" and no request-time fallback exists for it (only the daily jobs have one, `core/daily.py`). | Add a `scheduler` service running `process_notifications` every 5 minutes (and the daily jobs). |
| P15 | Medium | 11 | Notification de-duplication can double-send under concurrency. | `notifications/service.py` does `exists()` then `create()`; `Notification` has no unique constraint on (`user`, `dedupe_key`). 6 simultaneous callers per key: duplicates in 33 of 40 rounds (SQLite). Also affects the urgent alerts (Obj 17). | Add a partial `UniqueConstraint(user, dedupe_key)` where `dedupe_key <> ''` and catch `IntegrityError`. |
| P21 | Medium | 15 | In `lang=both` documents the Arabic paragraphs are laid out left to right. | PDF (rendered and viewed): in the contract's bilingual version the Arabic body is left-aligned with the full stop and list numbers on the wrong side. The `both` DOCX contains 0 `w:bidi` and 0 `w:rtl` markers (the `ar` DOCX has 88 and 72). `documents/pdf.py` and `word.py` decide direction per document (`rtl = lang == "ar"`), not per paragraph. | Detect Arabic per paragraph (`text.has_arabic`) and render those paragraphs right to left, right-aligned, and mark them `w:bidi`/`w:rtl`. |
| P22 | Medium | 14, 23 | The repo's two parallel-numbering tests fail on the default SQLite database instead of being skipped there. | `manage.py test quotations.tests_phase3.ConcurrentNumberTests contracts.tests_numbering` on SQLite: 2 failures, `OperationalError: database table is locked: core_yearsequence`. No `skipUnless(connection.vendor == 'postgresql')`. (In the later full run under `config.settings.test`, both tests passed on SQLite, so the failure shows only when those modules are run on their own or against a locked in-memory database.) | Skip them unless the database is PostgreSQL, and run a PostgreSQL job in CI so P20 cannot come back unseen. |
| P27 | Medium | 20, 23 | Two repo tests depend on the weekday they run on and fail today. | `manage.py test operations.tests` on SQLite, 2026-11-18 (Wednesday): `tests.py:282` expects `next_due == add_month(today)` (got 20 Dec, a Sunday, because 18 Dec is a Friday); `tests.py:290` `generate_due(today+10)` returns 0, not 1 (28 Nov is a Saturday, the task moves to Sunday). | Compute the expected value with `recurrence.next_working_day`, or pin `timezone.localdate` to a fixed working day in these tests. |
| P28 | Medium | 21 | The activity log is append-only only in Python. Raw SQL can change or delete rows, so "append-only" is not enforced by the database. | `UPDATE audit_auditentry SET comment='tampered-by-sql' WHERE id=...` returned rows=1 and the comment changed; `DELETE FROM audit_auditentry WHERE id=...` returned rows=1 and the row was gone, on SQLite and on PostgreSQL. The ORM routes (`save`, `delete`, `update`, `bulk_update`, queryset `delete`) all raised `ImmutableError`; API writes are 405. | Add a migration with a trigger that raises on UPDATE or DELETE of `audit_auditentry` (PostgreSQL `BEFORE UPDATE OR DELETE`; SQLite `CREATE TRIGGER ... RAISE(ABORT)`), and revoke UPDATE/DELETE from the app's database role. |
| P29 | Medium | 18 | Free text written by Commercial reaches Operations unfiltered, so a price can still be typed into a note and shown. | `client.notes`, `decision_note`, handover `services` / `scope_notes` / `contacts` and comments on the client are returned verbatim to Operations; the crawl found no structured money field, only these free-text channels. Design gap, not a failed Done-when item. | Add a guard line on those inputs ("do not enter prices"), and optionally flag digits-with-currency in handover text before submit. |
| P31 | Medium | 20, 21 | The recurrence rules and thresholds are narrower than the brief. | `recurrence.FREQUENCIES` has no "working days", no first/last working day, no nth weekday; `RecurringTask` has no policy field; tasks are created on the due date, no "days ahead" setting; `TASK_ESCALATION_DAYS` is read with a default `(2, 5)` (`operations/reminders.py:46`) and is defined in no settings file or screen. | Add the missing kinds and a per-rule policy, a days-ahead setting, and put the escalation thresholds in the CEO's settings screen; or accept as a deviation (D11). |
| P32 | Medium | 22 | No limit on how many files one task can hold, although the brief asks for size and count limits. | 40 more small PDFs after the first 8 were all accepted: 48 files on one task (`files/views.py` checks size and type only). | Count the live attachments of the record and refuse above a limit (for example 10). |
| P33 | Medium | 22 | "Checked by content" means the first 4 to 8 bytes only, so a file can carry anything after a valid header. | A PDF header followed by an exe body (`evil.pdf`, 253 bytes) returned 201; `PK\x03\x04` plus `META-INF/MANIFEST.MF` saved as `jar.docx` returned 201; any zip passes as docx or xlsx (`files/views.py` `ALLOWED`). | Open the file with the real parser (pypdf, Pillow `verify()`, `zipfile` plus the expected parts for docx/xlsx) and reject on failure. |
| P38 | Medium | 23 | The browser suite is not in the repository, and does not follow the journey in the brief. | `git ls-files frontend` shows no `e2e/` and no `playwright.config.ts` (both untracked); `next.config.ts`, `tsconfig.json` and `useDialog.ts` have uncommitted changes the suite needs. No spec covers deactivation revoking tokens, an explicit "Arabic persists" step, or access denied shown in the UI. The CEO is created by the `seed` command. | Commit the suite and its config changes; add the three missing journeys. |
| P39 | Medium | 7, 23 | Real accessibility and responsive defects found by the browser scans, against the claim of zero violations. | `aria-prohibited-attr` (serious): `aria-label` on a plain `div` in the loading placeholders (`.divide-y`, `div[aria-label="جارٍ التحميل"]`) on `/leave`, `/appointments`, `/operation`, `/tasks`, `/contracts`, `/profile?tab=settings`. `/leads` at 768 px: `scrollWidth 780 > 768`. (Two other failures were HTTP 502 from the dev server and four were 7-minute timeouts, both from load on this machine; not counted.) | Give the placeholder `role="status"` (or drop the label) and fix the 12 px overflow on `/leads`. |
| P8 | Low | 5 | `PATCH /users/{id}/` without `department` bumps the target's `token_version` and logs them out. | `accounts/serializers.py` `update()`: `moved = validated_data.get("department") != instance.department` is true when the key is absent. Reproduced: `{"full_name": ...}` took `token_version` 1 to 2. A self-PATCH of the CEO signed the CEO out. The UI always sends department and role, so only direct API calls are affected. | Compare only keys present in the payload. |
| P9 | Low | 5 | `/auth/refresh/` works while a password change is pending. | Probe above. | Leave or restrict; document the choice. |
| P10 | Low | 5 | Role choices are hard-coded in the UI. | `UserForm.tsx:15`. | Load them from `/roles/?department=`. |
| P11 | Low | 6 | Lockout is keyed per identifier as typed, so email and username of one account get separate counters. Reset clears only the email key. | `accounts/ratelimit.py`, `views.py` reset. | Key on the resolved user id. |
| P12 | Low | 1, 24 | `SECURE_SSL_REDIRECT` defaults to 1 in `production.py`, but 0 in compose. A `docker run` of the image without compose would probably fail its own `HEALTHCHECK` (it would be redirected to HTTPS; reasoned from the settings, not run). Compose publishes plain HTTP on 3000 with no proxy; Secure cookies will not work over a LAN IP. | `production.py:40`, `docker-compose.yml`, `Dockerfile:15`. | Document one supported topology; ship a Caddy/Nginx example. |
| P13 | Low | 7 | CSP uses `script-src 'unsafe-inline'`. | `next.config.ts`. | Use nonces if feasible. |
| P16 | Low | 11 | Notification text is frozen in the language the reader had when it was created. | A notification made for an English reader still shows English after they switch to Arabic. | Store `kind` + parameters and render when read. |
| P17 | Low | 10 | Status history can be out of order. | `log_interaction` writes the Contacted row with the contact's `occurred_at`; a first contact backdated 5 days sorts before the lead's creation row (`changed_at, id` ordering). | Stamp history with the real time and keep `occurred_at` as a separate field. |
| P18 | Low | 8 | The uniqueness constraint guards `phone_key`/`email_key`, not `phone`/`email`. | `QuerySet.update(phone=...)` leaves a stale key; only `save()` and the importer fill it. | Compute the keys in the database (generated column) or forbid bulk writes by a test. |
| P19 | Low | 8, 12 | Local numbers are always Jordanian. | `normalize.py` `DEFAULT_REGION = "JO"`: `0501234567` becomes `+962501234567`. | Make the region a setting. |
| P23 | Low | 16 | The contract's template link is never saved at creation. | `contracts/services.py:123 _prefill` sets `c.template = tpl` but neither `_prefill` nor `request_contract` saves `c`; after `decide(confirm)` the row has `template_id = NULL` while the version text is filled. | `c.save(update_fields=["template"])` in `_prefill`. |
| P24 | Low | 13 | Changing a client's email does not change the portal login. | `PATCH /clients/<id>/` to a new email, then `POST /clients/<id>/portal/`: `ensure_portal` resets the password of the existing portal user and mails `user.email` (the old address), reporting `sent`. | Say so in the UI, or update the portal user's email (checking it is free) when the client's email changes. |
| P25 | Low | 17 | Two small gaps in the administration feed. | `?kind=bogus` is ignored and returns everything (61 = unfiltered). "Changed today" is capped at 50 with no total or marker (61 rows exist). | Reject unknown `kind` with 400; return the total with the cap. |
| P30 | Low | 18 | The contract reference number shows in the client's activity trail for Operations. | Crawl of `activity/?target=client:<id>` as Operations returns `CT-1` in the trail text (a reference, not a value or file). | Decide if the reference may be seen; if not, drop it from the trail text shown to Operations. |
| P40 | Low | 24 | Twenty npm advisories, all in development tooling. | `npm audit`: 2 critical (`tinypool`, `vitest`), 11 high (`@vitejs/plugin-react`, `eslint-config-next` and their dependencies), 7 moderate. `npm audit --omit=dev`: 0. `pip-audit`: 0. | Plan a `vitest` 5 and `eslint-config-next` upgrade; add both audits to the production checklist. |
| P41 | Low | 24 | Most Swagger operations carry no human text. | 140 of 244 operations in the generated schema have neither `summary` nor `description` (only the generated operation id). | Add docstrings or `@extend_schema(summary=...)` to those views. |

## 3. Unverified (commands for a machine with Docker and PostgreSQL)

*(Complete: Steps 0 to 6.)*

| ID | What | Command |
|---|---|---|
| U1 | Obj 1: all three services healthy | `cp .env.example .env` (fill `DB_PASSWORD`, `DJANGO_SECRET_KEY`), then `docker compose up --build`, then `docker compose ps` and `curl -i http://localhost:3000/api/v1/health/` |
| U2 | Secure cookies over plain HTTP | Open `http://localhost:3000` in Chrome, Firefox and Safari, sign in; repeat with `http://<LAN-IP>:3000`. Check DevTools > Application > Cookies. |
| U3 | Visual RTL (Obj 7) | `cd frontend && npm run e2e` (needs Playwright browsers), plus manual check of `/login`, `/users`, `/leads` in Arabic. |
| U4 | Python 3.12 / Node 22 (the Docker versions), and current tzdata (`Asia/Amman` offset must be +3 all year) | `docker compose build` then `docker compose run --rm backend python manage.py test` and `docker compose run --rm backend python -c "import zoneinfo,datetime as d; print(d.datetime(2026,1,15,tzinfo=zoneinfo.ZoneInfo('Asia/Amman')).utcoffset())"` (expect `3:00:00`). |
| U5 | **Obj 8: two simultaneous inserts of one phone on PostgreSQL** (SQLite cannot prove this) | From `backend/`, with a PostgreSQL user that may create databases: `pip install "psycopg[binary]>=3.2"` then `DB_ENGINE=postgres DB_NAME=innovation DB_USER=<user> DB_PASSWORD=<pw> DB_HOST=localhost DB_PORT=5432 python manage.py test leads.tests_lead_model.ConcurrentInsertTests -v 2` (Django creates and drops `test_innovation`). Expected: 1 test, OK; one thread creates the lead, the other gets the `duplicate` validation error, no 500. Repeat 20 times to catch timing luck: `for i in $(seq 20); do DB_ENGINE=postgres ... python manage.py test leads.tests_lead_model.ConcurrentInsertTests --keepdb \|\| break; done`. Independent check over HTTP against the running compose stack (after logging in as Marketing; save cookies in `jar.txt`; `CSRF` is the `csrf_token` cookie value): `for i in 1 2; do curl -s -o /dev/null -w "%{http_code}\n" -b jar.txt -H "X-CSRF-Token: $CSRF" -H "Content-Type: application/json" -d '{"company_name":"Race","phone":"0797707154"}' http://localhost:3000/api/v1/leads/ & done; wait` then expect one `200/201` and one `400`, and `docker compose exec db psql -U innovation -c "select count(*) from leads_lead where phone_key='+962797707154'"` returns `1`. |
| U6 | Obj 11: overlapping scheduler runs (P15) on PostgreSQL | Create an appointment 30 minutes ahead, then `(python manage.py process_notifications & python manage.py process_notifications & wait)` and `select count(*) from notifications_notification where kind='appointment_reminder'`; expect 1 (today it can be 2). |
| U7 | **Obj 14: parallel quotation and contract numbering on PostgreSQL** (today it ERRORS because of P20; I ran it on PostgreSQL 16.2 here) | From `backend/`: `pip install "psycopg[binary]>=3.2"` then `DB_ENGINE=postgres DB_NAME=innovation DB_USER=<user> DB_PASSWORD=<pw> DB_HOST=localhost DB_PORT=5432 python manage.py test quotations.tests_phase3.ConcurrentNumberTests contracts.tests_numbering -v 2`. Expected after P20 is fixed: 3 tests, OK (distinct, consecutive numbers; a failed send gives its number back). Today: 3 errors `NotSupportedError: FOR UPDATE cannot be applied to the nullable side of an outer join`. Repeat 20 times with `--keepdb`. Independent check on the running stack: send 10 signed quotations at once (`for id in $(seq ...); do curl -s -b jar.txt -H "X-CSRF-Token: $CSRF" -X POST http://localhost:3000/api/v1/quotations/$id/send/ & done; wait`) then `docker compose exec db psql -U innovation -c "select number from quotations_quotation where number is not null order by number"` (expect `.../0001` to `.../0010`, no gap, no duplicate) and `select key,year,last from core_yearsequence`. |
| U8 | Obj 15: the Word files in real Word (and LibreOffice) | `GET /api/v1/quotations/<id>/document/?fmt=docx&lang=ar` (and `lang=both`, and the contract and meeting-report equivalents) with a signed-in cookie, open the file in Word. Check joined letters, right-to-left columns, the draft watermark on a draft and none on a signed one. Only XML markers were checked here. |
| U9 | Whole suite on PostgreSQL (needed because of P20; D5) | `DB_ENGINE=postgres ... python manage.py test --keepdb` and `pytest`; any `NotSupportedError` or `database table is locked` is a real finding. I will run this in Phase 6 on the PostgreSQL 16.2 available here. |
| U10 | Portal welcome email through a real mail server | Set `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, accept a lead with a real email, read the message, sign in at `PORTAL_URL` with the temporary password, set a new one and confirm you land on `/portal`. Only the in-memory mail backend was used here. |
| U11 | Obj 18/19/21: the Operations, reports and audit test modules on PostgreSQL | From `backend/`: `DB_ENGINE=postgres DB_NAME=innovation DB_USER=<user> DB_PASSWORD=<pw> DB_HOST=localhost DB_PORT=5432 python manage.py test operations reports audit --noinput`. Expect 43 errors today (P26) and 0 after the fix. |
| U12 | Obj 20: the daily job on PostgreSQL, twice in parallel | After the fix: run the daily command twice at once (`(python manage.py <daily-job-command> & python manage.py <daily-job-command> & wait)`), then `select recurring_id, rule_version, period, count(*) from operations_taskinstance group by 1,2,3 having count(*)>1;` must return no rows. |
| U13 | Obj 21: append-only log enforced by the database | After adding the trigger (P28): `psql -c "update audit_auditentry set comment='x' where id=1"` and `psql -c "delete from audit_auditentry where id=1"` must both fail. |
| U14 | Obj 21: submit, approve, publish, acknowledge in a real browser | Sign in as the Operation member, start and submit a task; as the head approve and publish; sign in at the portal and acknowledge. Check the CEO notification after moving a task's due date 5 days back. |
| U15 | Whole backend suite with pytest on PostgreSQL | `DB_ENGINE=postgres DB_NAME=innovation DB_USER=<user> DB_PASSWORD=<pw> DB_HOST=localhost DB_PORT=5432 python -m pytest -q` (only `manage.py test` was run on PostgreSQL here: 198 errors, all P20). |
| U16 | Browser scans on an idle machine (here 7 tests hit 502 or 7-minute timeouts under load) | `cd frontend && E2E_WORKERS=1 npx playwright test --no-deps --project=en-scan-a11y --project=en-scan-responsive --project=ar-scan-a11y --project=ar-scan-responsive` against a database that already went through `01` to `03`. |
| U17 | README commands on macOS and Linux | `source .venv/bin/activate`; `python manage.py spectacular --validate --fail-on-warn --file /dev/null` (the README's `NUL` would create a file); full walk-through on a fresh machine. |
| U18 | The browser suite on a fresh clone of the repository once P35, P37 and P38 are fixed | `cd frontend && npm run e2e` twice with `E2E_DB_DIR=<folder>` set to the same folder both times; expect two green runs. |
| U19 | Node 20 (the README's minimum) | `nvm use 20 && cd frontend && npm ci && npm run build && npm test`. Only Node 24 was used here. |
| U20 | Docker image build on Python 3.12 with PostgreSQL | `docker compose up --build`, then `docker compose exec backend python manage.py test --noinput` (needs P1 and P20 fixed first). |

## 4. Deviations from the brief (accept or reject)

| # | Brief says | Repo does | Decision needed |
|---|---|---|---|
| D1 | Next.js app shell with **next-intl** | Hand-written `src/lib/i18n.tsx` with JSON dictionaries and its own plural syntax | Accept or require next-intl. |
| D2 | "Nine roles" | Ten role rows (nine staff roles plus the system `client` role); roles named "Operation ..." where the brief says Operations | Accept the naming and the `client` role. |
| D3 | Super Admin "marked full access" | No flag, implemented as "has all capabilities after seeding" | See P7. |
| D4 | Phase scope | Extra modules `hr/` (payroll, leave, attendance), `payments/`, `comments/`, `reports/` | Phase 4 decides the confidentiality risk. |
| D5 | PostgreSQL | SQLite default for local runs; PostgreSQL only in Docker | Accept if the suite also passes on PostgreSQL (U-list, Phase 6). |
| D6 | Lead status "Not contacted" or "Contacted" with sub-status Waiting, Rejected, Initial acceptance | One flat status: `new`, `contacted`, `waiting`, `qualified` (= initial acceptance), `rejected`, plus the extra rules (reopen, archive, skip-quotation) | Accept the flat model (behaviour matches the brief). |
| D7 | Excel import (.xlsx) | Also accepts `.csv`; a two-step preview then confirm; an import can be undone | Accept (superset). |
| D8 | Quotation/contract number format `PREFIX/YYYY/M/NNNN` | Matches (`QT/2026/11/0001`, `CT/2026/11/0001`), month without a leading zero, counter per year (not per month), own counter per document kind | Accept. |
| D9 | Country templates for contracts | Mechanism present; only the `*` default template exists after migrating | Decide whether to seed country templates. |
| D10 | Document generation "from one shared rendering module" | Matches (`documents/` with builders, `pdf.py`, `word.py`); portal copies reuse it | Accept. |
| D11 | Recurrence: daily, working days, weekly, monthly (fixed day, first/last working day, nth weekday), quarterly, yearly, policy per rule, tasks generated N days ahead | Daily, weekly, every 2 weeks, monthly (by date), quarterly, every 6 months, yearly, every N days; one fixed weekend/holiday policy; tasks are created on the due date; escalation thresholds are code defaults | Accept or require the missing kinds (P31). |
| D12 | "Versioned KYC record (request info, mark supplied, verify)" | A per-client checklist whose documents are versioned and verified (pending, uploaded, verified, expired, not applicable); no separate request/supplied step | Accept the checklist as the KYC record. |
| D13 | Browser journey: setup, **admin creates the CEO**, CEO first login creates an employee | The browser suite signs in as the CEO that the `seed` command made; the Super Admin is created with `createsuperuser`; the CEO then creates the other seven roles through the screens | Accept the command-line CEO or require a UI step (P38). |
| D14 | "Department heads assign to their own department; the CEO to anyone" | Also true for the Super Admin (`gtask.assign_any`); a head may assign to themselves | Accept. |

## 5. Phase grades

**Method.** Every Done-when item or brief requirement I tested counts once: PASS = 1, PARTIAL = 0.5, FAIL = 0, CANNOT-VERIFY excluded. The phase score is points divided by counted items, and the overall grade uses the suggested weights 30/25/25/10/5/5. The weights give no credit for a Blocker that stops the product, so the verdict below is separate from the number.

| Phase | Weight | PASS | PARTIAL | FAIL | CANNOT-VERIFY | Phase score | Weighted |
|---|---|---|---|---|---|---|---|
| 1 Foundation (Obj 1 to 7) | 30% | 13 | 3 | 3 | 2 | 76% | 22.9 |
| 2 Leads (Obj 8 to 12) | 25% | 14 | 1 | 0 | 0 | 97% | 24.2 |
| 3 Sales pipeline (Obj 13 to 17) | 25% | 12 | 1 | 1 | 0 | 89% | 22.3 |
| 4 Operations (Obj 18 to 21) | 10% | 8 | 4 | 2 | 1 | 71% | 7.1 |
| 5 General tasks (Obj 22) | 5% | 6 | 1 | 0 | 0 | 93% | 4.6 |
| 6 Quality (Obj 23 to 24) | 5% | 1 | 4 | 4 | 0 | 33% | 1.7 |
| **Overall** | 100% | | | | | | **83 / 100** |

Phase 1 counts the 21 items of section 1 (2 CANNOT-VERIFY). Phase 4 counts 15 (1 CANNOT-VERIFY). The Phase 4 PostgreSQL failures are counted as FAIL for the generator and escalation, and the PARTIAL items there include the SQLite-only passes. Phase 5 counts the seven items of section 1e; Phase 6 the nine of section 1f.

**Verdict.** The number looks healthy because the logic of Phases 1 to 5 is mostly right on SQLite. As shipped, the project would not pass: (1) the compose stack does not start (P1); (2) on PostgreSQL, the database the brief names, quotation, contract, handover, recurring and task actions crash (P20, P26); (3) Phase 6 is "required to pass" in the brief and fails: not all suites pass from a clean database, the browser suite is neither committed nor repeatable, and the README cannot be followed alone (P34 to P38).

Fastest path to a pass, in this order: P20 (one argument at seven sites) and a PostgreSQL job in CI; P1; P34 and P35; P36 and P37; P2 and P3; then the Mediums.

## 6. Extra checks requested

### 6.1 Secret scan of the local databases (counts only, no values printed)

Both files were opened read-only (`mode=ro&immutable=1`). Every column of every table was tested for JWT shape, private-key header, `sk-` and AWS-style keys, long opaque strings, and password-hash prefixes.

| File | `accounts_user.password` | `token_blacklist_outstandingtoken.token` | Plaintext passwords / private keys / API keys |
|---|---|---|---|
| `db.sqlite3` | 1 row, Argon2 hash | **45 raw refresh JWTs**, 0 still unexpired | none found |
| `db.sqlite3.backup` | 1 row, PBKDF2 hash | **45 raw refresh JWTs**, 0 still unexpired | none found |

Other columns the scan flagged (`django_migrations.name`, `accounts_role.key`, `token_blacklist_blacklistedtoken.token_id`) are false positives (migration names, role keys, foreign keys). Each file has 1 user row. Conclusion: no real password, API key or private key. The stored refresh tokens are expired and were signed with the committed development key, so they are low risk, but both files are local copies of session tokens and should stay out of Git (see H1). The `outstandingtoken` table stores whole tokens by design of `simplejwt.token_blacklist`; a periodic `flushexpiredtokens` job would keep it small (not scheduled in the README job list).

### 6.2 Interpreter

Backend probes: Python 3.11.16. Frontend: Node 24.14.1. The Docker images use Python 3.12 and Node 22, which this machine did not exercise (U4).

### 6.3 Is `backend/venv` safe to delete?

Yes, in my assessment, but I did not delete anything. It is a Python **3.15.0** environment with 25 packages; it lacks `pytest`, `pytest-django`, `drf-spectacular`, `pymupdf` and `pypdf`, so it cannot run the current test suite or generate the OpenAPI schema. It is git-ignored (`.gitignore:16`), nothing tracked refers to it (README, `DEPLOYMENT.md`, `frontend/e2e/README.md`, `qa/browser/*.sh` all use `backend/.venv`), and `backend/.venv` (3.11.16, 59 packages) is the working one. I could not confirm that no editor or terminal currently has it active (a process listing timed out), so close those first.

Phase 4 headline: on SQLite the logic is sound (no money or contract file reaches Operations, the one-primary rule is enforced by the database, reports agree to the digit, escalation is once per level). On PostgreSQL the same logic cannot run because of P20 (P26). The activity log is not append-only at database level (P28).
