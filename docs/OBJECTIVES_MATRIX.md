# Objectives matrix

Baseline audit, 16 Nov 2026, against commit `c1c68ef`. Source of truth for requirements: the "Company Workflow Platform: Student Project Objectives" brief (24 objectives).

**Status values:** Done, Partly, Different (works, but not the way the brief requires), Missing.
**Evidence rule:** a row is Done only with a named test, file or command output. Rows marked `(grep)` were judged from a code search only and must be confirmed by a test during their phase. Nothing here is marked Done on the strength of "the code exists".

**Baseline run:** `backend/.venv/Scripts/python.exe manage.py test` (temporary SQLite database) gives 397 tests, OK. No Docker and no PostgreSQL on this machine, so anything that needs them is "Written, not verified here".

## Summary

| # | Objective | Phase | Done | Partly | Different | Missing |
|---|-----------|-------|------|--------|-----------|---------|
| 1 | Skeleton and deployment | 1 | 1 | 2 | 1 | 4 |
| 2 | Organisation (Department, Role, Capability) | 1 | 1 | 0 | 1 | 5 |
| 3 | Cookie JWT authentication | 1 | 2 | 0 | 1 | 5 |
| 4 | Capability RBAC | 1 | 1 | 1 | 1 | 4 |
| 5 | User management, first login | 1 | 2 | 3 | 2 | 3 |
| 6 | Revocation, lockout, audit, error envelope | 1 | 0 | 2 | 1 | 4 |
| 7 | Shell, i18n, proxy | 1 | 2 | 1 | 1 | 3 |
| 8 | Lead model and normalisation | 2 | 0 | 2 | 0 | 3 |
| 9 | Import (xlsx, CSV) | 2 | 0 | 2 | 0 | 3 |
| 10 | Lead statuses and history | 2 | 1 | 2 | 0 | 0 |
| 11 | Appointments and notifications | 2 | 0 | 1 | 0 | 4 |
| 12 | Targets and leads dashboard | 2 | 0 | 1 | 0 | 3 |
| 13 | Conversion and client portal | 3 | 0 | 1 | 0 | 4 |
| 14 | Quotation state machine | 3 | 1 | 3 | 0 | 2 |
| 15 | Document rendering (PDF and Word) | 3 | 0 | 1 | 0 | 4 |
| 16 | Meeting reports and contracts | 3 | 0 | 3 | 0 | 3 |
| 17 | Administration tracking and urgent alerts | 3 | 0 | 2 | 0 | 2 |
| 18 | Handover, Operations privacy | 4 | 0 | 1 | 0 | 3 |
| 19 | KYC, project staffing | 4 | 0 | 2 | 0 | 2 |
| 20 | Recurrence engine, holidays | 4 | 0 | 2 | 0 | 2 |
| 21 | Task lifecycle, escalation, reports | 4 | 0 | 2 | 0 | 4 |
| 22 | General tasks | 5 | 0 | 0 | 0 | 6 |
| 23 | Test suites | 6 | 1 | 1 | 0 | 3 |
| 24 | Documentation, OpenAPI, production checklist | 6 | 1 | 2 | 0 | 2 |

Counts are approximate (tallied by hand from the rows below) and will be recomputed as each phase closes. The rows are the record.

---

## Phase 1: Foundation

### 1. Skeleton and deployment
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| `backend/` and `frontend/` folders | Done | repo layout | none |
| Settings split base / development / production / test | Partly | `config/settings.py` plus `config/settings_prod.py`; test overrides live inside `settings.py` behind `"test" in sys.argv` | split into `settings/base.py`, `development.py`, `production.py`, `test.py` |
| `.env.example` documenting every variable | Partly | `backend/.env.example` exists | audit against `os.environ` reads and complete it |
| `docker-compose.yml` with PostgreSQL, Gunicorn Django, Next.js, health checks | Missing | no Docker files | write Dockerfiles and compose. Not verifiable here (no Docker) |
| `GET /api/v1/health/` | Different | `core/views.py: HealthView` at `/api/health/` | move all routes under `/api/v1/` (see objective 7 proxy) and keep health |
| Compose healthy | Missing | no Docker on this machine | "Written, not verified here" |
| No secrets in git | Missing | no scan on record | run a scan over history and working tree |
| `.gitignore` for db, uploads, env | Done | `.gitignore` lines for `*.sqlite3`, `private_media/`, `.env` | none |

### 2. Organisation: Department, Role, Capability
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Department model | Done | `accounts/models.py: Department`, constraint `one_active_head_per_department` | none |
| Role model belonging to a department | Different | role is `User.role` CharField (`head` / `member`) with `core/roles.py: role_key` | add `Role` model, link users with an additive FK and a data migration; keep `role_key` values stable |
| Capability model, roles hold capabilities | Missing | none | add models plus the capability catalogue |
| Nine roles (eight business roles plus Super Admin) | Missing | eight role keys exist, no Super Admin | add Super Admin, no department, receives every capability automatically |
| Idempotent `seed_organization` | Different | `accounts/management/commands/seed.py` creates departments and the CEO only | new `seed_organization`; run twice in a test |
| Grant a capability without touching view code | Missing | | test: add a capability to a role, endpoint opens |

### 3. Authentication with HttpOnly cookies
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Login by username or email, case-insensitive | Different | email only (`accounts/views.py: LoginView`) | add additive `username`, accept either |
| Tokens only in HttpOnly + Secure + SameSite=Lax cookies | Missing | `frontend/src/lib/api.ts` keeps access and refresh in `localStorage`; tokens are returned in the body | cookie auth class, remove storage use, same-origin proxy |
| Refresh with rotation and blacklist | Missing | `SIMPLE_JWT.ROTATE_REFRESH_TOKENS = False`, no blacklist app | enable rotation and `token_blacklist` |
| Logout | Partly | `auth/logout/` exists (`accounts/urls.py`) | clear cookies and blacklist the refresh token |
| `GET /auth/me/` returns user and capabilities | Partly | `MeView` returns user and `role_key` | add capabilities |
| CSRF double-submit cookie on unsafe requests | Missing | none (bearer tokens today) | required once cookies are used |
| Proof: tokens unreadable from JS, reused refresh rejected, no-CSRF POST rejected | Missing | | three tests plus a browser check |
| Lockout and throttling basics exist | Done | `accounts/ratelimit.py`, tests in `accounts/tests.py` | tune in objective 6 |

### 4. Capability RBAC
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| `HasCapability` permission class, fail closed | Missing | permissions are role-key checks in each app's `access.py`; default is `IsAuthenticated` plus `PasswordChangeNotPending` | build the class, default deny |
| Each view declares capabilities per action | Missing | | declare on every view |
| Migrate role-key checks without changing who can do what | Different | `core/roles.py`, `*/access.py` | map each rule to a capability, keep tests green |
| Generated matrix test over every endpoint x every role + anonymous | Done | `core/permission_audit.py`, `core/tests_hardening.py` | keep as the regression proof for the migration |
| Allowed and denied tests per role | Partly | many per module (397 tests) | add a denial test for every capability |
| Frontend reads capabilities only to show or hide | Missing | frontend branches on `role_key` | switch to capabilities |

### 5. User management and first login
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| List, search, filter, create, edit, activate, deactivate | Done | `accounts/views.py`, `accounts/tests.py` | confirm filters (grep) |
| Reset password | Partly | exists (grep) | switch to random temporary password |
| 16-character random temporary password shown once | Different | CEO types the temporary password (`accounts/serializers.py: temporary_password`) | server generates, shows once |
| Stored only as Argon2 hash | Missing | default PBKDF2 (`PASSWORD_HASHERS` not set; MD5 in tests) | add `argon2-cffi`, configure hasher |
| Never in logs, audit log or DB | Partly | `core/logscrub.py` exists | write the proof test |
| Until changed, only me / password-change / logout work | Done | `PasswordChangeNotPending` default permission | keep |
| Password policy: min 12, not common, not similar, not current | Different | `MIN_PASSWORD_LENGTH = 8` in `accounts/serializers.py` | Django validators, min 12 |
| Super Admin protected from the CEO | Missing | no Super Admin | build with objective 2 |
| Nobody changes their own role, department or status | Partly (grep) | | explicit tests |
| Role choices depend on the department | Partly (grep) | model rules in `User.clean` | confirm in API and form |

### 6. Revocation, lockout, audit, error envelope
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| `token_version` claim, bumped on password change, reset, deactivation, role change | Missing | none | add field, claim, check in authentication |
| Deactivated user cut off on the next request | Partly | inactive users fail authentication; no test over cookies | test with token_version |
| Lockout 5 failures in 5 minutes, per-IP throttle | Different | 8 per email, 40 per IP, 15-minute window (`config/settings.py`) | change to the brief's numbers |
| AuditLog (logins, failures, password, user and language changes, actor, target, IP, UA) | Partly | `accounts/models.py: ActionLog`, `audit/models.py: AuditEntry` | confirm coverage, add IP and user agent, refuse secret-like fields |
| One error envelope `{"error": {code, message, fields?}}` | Missing | DRF default `{"detail": ...}`; the frontend maps English messages (`API_MESSAGES`) | custom exception handler plus 404/405/429/500 handlers; adapt the frontend |
| No stack traces | Partly | `DEBUG` off in production settings (grep) | test |

### 7. Shell: i18n, proxy
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Language from a cookie | Done | `lang` cookie, `frontend/src/lib/i18n.tsx` | none |
| `<html lang dir>` set on the server | Done | `frontend/src/app/layout.tsx` (grep) | confirm by test |
| Language saved to the profile | Done | `preferred_language`, applied after sign-in | none |
| next-intl | Different | custom `lib/i18n.tsx`, 1,600 keys per language | decide: adopt next-intl or keep (see questions) |
| Logical CSS, RTL layout and icon flipping | Partly | Tailwind logical utilities; RTL sweeps passed in QA | keep |
| Same-origin proxy `/api/[...path]` to Django | Missing | `next.config.ts` points the browser at `NEXT_PUBLIC_API_URL`; CORS is on | add route handler or rewrite |
| Script that fails on a missing key | Missing | no script | add and run in CI |
| Proof: switching flips layout, persists on a fresh browser | Done (QA) | journeys in EN and AR at 375, 768, 1280 | move into Playwright (objective 23) |

---

## Phase 2: Leads

### 8. Lead model and normalisation
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Fields name, company, position, phone, email, location; phone or email required | Partly | `leads/models.py: Lead` (field list to compare) | align fields |
| E164 normalisation (07.. to +9627.., 00.. to +.., Arabic digits) | Partly | `leads/importer.py`, `leads/models.py` mention it (grep) | shared normaliser, unit tests |
| Lowercased email; database uniqueness constraints | Missing | duplicates found in code, not by constraint (grep) | constraints, clean 409 |
| 0797707154 equals +962797707154; concurrent inserts give one lead | Missing | | tests (threaded on a file database) |
| List with search, filters, ordering, pagination | Done (grep) | `leads/filters.py` | confirm |

### 9. Import
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| .xlsx template, Arabic and English | Missing | CSV only | add `openpyxl` |
| CSV kept | Done | `leads/importer.py`, QA journey import (1 ready, 2 row errors) | none |
| Up to 5,000 rows / 5 MB, type and size errors | Partly | limits to confirm | tests |
| Header matching in either language | Missing | | build |
| Skip invalid and duplicate rows (DB and in-file), full skip report | Partly | row errors reported | duplicates inside the file |

### 10. Statuses and history
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Not contacted / Contacted (Waiting) / Rejected / Initial acceptance | Partly | existing statuses `new, contacted, waiting, qualified, rejected` | map names |
| Waiting needs a future date and creates a follow-up appointment | Partly | follow-up date exists, no appointment object | objective 11 |
| Rejected needs a reason and cancels open follow-ups | Done | rejection reason enforced (QA journey: reason required) | add follow-up cancel with appointments |
| History (who, from, to, when) | Done (grep) | `leads/models.py: Interaction` | confirm |

### 11. Appointments and notifications
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Appointment model, five types, own vs manager-all | Missing | no appointment model | build |
| Notifications in the reader's language, polling bell | Partly | `notifications/` app, bell in the top bar | keys per language |
| Idempotent `process_notifications` | Missing | `lead_reminders` command exists for leads | consolidate |
| Rescheduling updates the lead's follow-up date | Missing | | build |
| Mark one / all read | Done (grep) | `notifications/views.py` | confirm |

### 12. Targets and dashboard
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Marketing target over a date range, progress maths | Missing | no target model | build |
| Leads dashboard (totals, rates, due and overdue, breakdowns, contributors) | Partly | `reports/` funnel report covers part | extend |
| Company time zone for "today"; boundary tests | Partly | `DJANGO_TIME_ZONE`, `leads/sla.py: sla_now` | boundary tests |
| Numbers equal a manual count | Missing | | test |
| "Overdue" opens the filtered pool | Missing | `/leads?overdue=` filter exists | link and test |

---

## Phase 3: Sales pipeline

### 13. Conversion and portal
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Initial acceptance converts to a Client and locks the lead (409 `lead_converted`) | Partly | lead and client models exist; lock and error code to confirm | build and test |
| Client portal account, emailed temporary password | Missing | no portal | build, console email backend |
| Missing email and email already in use handled | Missing | | build |
| Client changes password, lands on `/portal`, sees only own data | Missing | | build |
| Client accounts hidden from user management | Missing | | build |

### 14. Quotation state machine
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| HR Head assigns, HR prepares, submits | Done | `quotations/services.py`, QA journey (HR prepare, valid_until rule) | none |
| Commercial Head signs or returns with notes | Done | `quotations/tests.py` (`test_the_ceo_cannot_sign`), QA journey | drawn signature and company stamp: Missing |
| Drawn signature and stamp | Missing | | build |
| Sending issues PREFIX/YYYY/M/NNNN, gapless under concurrency | Partly | `core/models.py: Sequence`; format and concurrency proof to check | align format, concurrency test |
| Client signs on portal or staff upload a signed copy | Missing | | after objective 13 |
| Illegal transitions rejected; returned notes shown | Done | quotation tests and QA (returned path) | keep |

### 15. Document rendering
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| One shared rendering module, PDF and Word | Missing | browser print view only (`/quotations/N/print`) | server-side module (`reportlab`, `python-docx`, `arabic-reshaper`, `python-bidi`) |
| DRAFT watermark | Missing | | build |
| Uploaded signed copy overrides | Missing | | build |
| Arabic shaping and RTL, inspected | Missing | | render and look at the files |
| Permission-checked endpoints only | Partly | files served through `files/views.py` with checks | extend |

### 16. Meeting reports and contracts
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Client status after a follow-up meeting | Partly | meeting outcome exists (QA journey) | align with appointments |
| Meeting report flow draft, Commercial signs, CEO approves | Partly | visit report exists (QA journey) | one per appointment, state machine |
| Contract flow with own number sequence | Partly | `contracts/` module, QA journey | confirm sequence, templates per country |
| Client Documents tab with versions | Missing | | build |
| Sent contract blocks client status leaving Confirm (409) | Missing | | build |
| Each signer acts only at their step | Done | contract tests (CEO signs, HR drafts) | keep |

### 17. Administration tracking and alerts
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Process-tracking page | Partly | reports and "My work" exist | build page |
| Urgent alerts at 60 minutes, once per case, settings-driven | Partly | `leads/sla.py`, `lookups: SlaSetting` for leads | extend to HR and Commercial, clock-shift tests |
| Activity feed filterable | Missing | `audit/` log exists | build |

---

## Phase 4: Operations

### 18. Handover and Operations privacy
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Handover filled by Commercial, Operations Head accepts, returns, escalates | Partly | handover appears in `contracts/services.py` | confirm and extend |
| Accepting creates a Project | Missing | no Project model | build |
| No prices or payment data to Operations (whitelist serializers) | Missing | | build, plus the walker test |
| Original contract file unreachable from Operations | Missing | | test |

### 19. KYC and staffing
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Versioned KYC record and legal checklist with expiry | Partly | `operations/models.py: ChecklistItem`, QA journey (4 of 5, 5 of 5) | versioning, expiry |
| Onboarding approval only when KYC verified | Done | QA journey (client becomes Active at 5 of 5) | confirm with a test |
| One primary employee per project (DB constraint) plus support; replace needs a reason | Missing | | build |

### 20. Recurrence engine
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Rule types daily to yearly | Partly | `operations/models.py: RecurringTask`, `generate_recurring_tasks` | extend rule types |
| One task per (rule, version, period); repeated runs safe | Partly | command exists | constraint, tests |
| Friday-Saturday weekend and holiday policy, editable calendar | Partly | `hr/attendance.py` has weekends and holidays | CEO-editable calendar |
| Edits affect only future periods | Missing | | versioning |
| Month-end, leap-year, weekend, holiday unit tests | Missing | | write |

### 21. Task lifecycle and reports
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Start, progress, notes, attachments, waiting, blocked, submit; manager approves, returns, escalates | Partly | `operations/services.py` | gaps to list |
| Deliverables published to portal and acknowledged | Missing | | after portal |
| Escalations unique per case and level | Missing | | build |
| Monitoring view | Partly | operations reports section | extend |
| JSON, Excel and PDF reports with identical numbers | Partly | JSON and CSV only | add xlsx and pdf |
| Append-only activity log | Done | `audit/models.py: AuditEntry` (immutable) | confirm per action |

---

## Phase 5: General tasks

### 22. General tasks
All rows Missing: model and screens; scope by department head or CEO; only the assignee can mark done; done late; magic-byte upload checks; overdue alert re-armed on deadline change; counters.

---

## Phase 6: Quality and delivery

### 23. Tests
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Backend suite green from a clean database | Done | 397 tests OK on a temporary SQLite database | pytest is not used; Django's runner is. Decide whether to adopt pytest (see questions) |
| Vitest + Testing Library | Missing | `package.json` has no test script | add |
| Playwright journeys repeatable on one database | Partly | scratch scripts outside the repo, run in EN and AR at three widths | move into `frontend/e2e` |
| Every permission rule has a denial test | Partly | `core/tests_hardening.py` sweep | per-capability denial tests |

### 24. Documentation
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| README, ARCHITECTURE, PERMISSIONS, DEPLOYMENT, USER_GUIDE | Done (baseline) | files in `docs/` and `README.md` | rewrite after each phase |
| OpenAPI with Swagger and ReDoc | Missing | no schema generator | `drf-spectacular` |
| Production checklist, `pip-audit`, `npm audit` | Partly | `docs/DEPLOYMENT.md`; audits not run | run and record |

---

## Decisions I am making unless you object

1. **Role model:** add `Role` and `Capability` tables and a nullable `User.role_ref` FK, filled by a data migration from the existing `role` + department. The old `role` column stays until Phase 1 closes, so your database upgrades without data loss.
2. **Username:** add a nullable unique `username`, case-insensitive. Existing users keep email login.
3. **Super Admin:** a user with no department, role `super_admin`, every capability. The CEO remains the only Administration-department user.
4. **API prefix:** `/api/v1/`. The old `/api/` stays as an alias for one release so nothing breaks mid-phase.
5. **Libraries I will add:** `argon2-cffi`, `drf-spectacular`, `openpyxl`, `reportlab`, `python-docx`, `arabic-reshaper`, `python-bidi`, `filetype` (magic bytes), `phonenumbers`; frontend `vitest`, `@testing-library/react`, `@playwright/test`.
6. **Test runner:** keep Django's runner (397 tests already use it) and not move to pytest.

## Questions I need answered once (batched)

1. **next-intl:** the brief names it, but the app already has a working in-house i18n with 1,600 keys per language and RTL verified. Replace it (large, risky churn) or keep it and add the missing-key check script? My default: keep, and record the difference.
2. **Brief vs business flow:** the brief says Initial acceptance converts a lead to a Client and the client portal exists from that moment, while the current flow creates clients at Operation onboarding. My default: follow the brief (convert at acceptance), and keep the Operation onboarding for KYC and activation.
3. **Scope and time:** this is months of work. My default is to finish Phase 1 completely, with evidence, before starting Phase 2, as the brief says.
