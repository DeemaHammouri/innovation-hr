# Objectives matrix

Baseline audit, 16 Nov 2026, against commit `c1c68ef`. Source of truth for requirements: the "Company Workflow Platform: Student Project Objectives" brief (24 objectives).

**Status values:** Done, Partly, Different (works, but not the way the brief requires), Missing.
**Evidence rule:** a row is Done only with a named test, file or command output. Rows marked `(grep)` were judged from a code search only and must be confirmed by a test during their phase. Nothing here is marked Done on the strength of "the code exists".

**Baseline run:** `backend/.venv/Scripts/python.exe manage.py test` (temporary SQLite database) gives 397 tests, OK. No Docker and no PostgreSQL on this machine, so anything that needs them is "Written, not verified here".

## Summary

| # | Objective | Phase | Done | Partly | Different | Missing |
|---|-----------|-------|------|--------|-----------|---------|
| 1 | Skeleton and deployment | 1 | 6 (2 written, not verified here) | 0 | 0 | 0 |
| 2 | Organisation (Department, Role, Capability) | 1 | 7 | 0 | 0 | 0 |
| 3 | Cookie JWT authentication | 1 | 7 | 0 | 0 | 0 |
| 4 | Capability RBAC | 1 | 6 | 0 | 0 | 0 |
| 5 | User management, first login | 1 | 10 | 0 | 0 | 0 |
| 6 | Revocation, lockout, audit, error envelope | 1 | 7 | 0 | 0 | 0 |
| 7 | Shell, i18n, proxy | 1 | 7 | 0 | 1 (decided) | 0 |
| 8 | Lead model and normalisation | 2 | 5 | 0 | 0 | 0 |
| 9 | Import (xlsx, CSV) | 2 | 5 | 0 | 0 | 0 |
| 10 | Lead statuses and history | 2 | 4 | 0 | 0 | 0 |
| 11 | Appointments and notifications | 2 | 5 (scheduler: written, not verified here) | 0 | 0 | 0 |
| 12 | Targets and leads dashboard | 2 | 5 | 0 | 0 | 0 |
| 13 | Conversion and client portal | 3 | 5 | 0 | 0 | 0 |
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

Gate run: `manage.py test` and `pytest` both run the same 467 tests (466 pass, 1 is the opt-in matrix dump tool, skipped). `tsc`, `eslint`, `next build`, `npm run i18n:check` and `scripts/secret_scan.py` are clean. Browser proof: `qa/browser/phase1.js` and `qa/browser/cookies.js`, output in `docs/evidence/phase1-browser.txt` (21 checks, all pass).

### 1. Skeleton and deployment
| Row | Status | Evidence | Note |
|-----|--------|----------|------|
| `backend/` and `frontend/` folders | Done | repo layout | |
| Settings split base / development / production / test | Done | `backend/config/settings/{base,development,production,test}.py`; `core/tests_hardening.py` imports production settings; `pytest.ini` | wsgi/asgi default to production |
| `.env.example` documenting every variable | Done | `backend/.env.example`, root `.env.example`; test `core/tests_deploy.py::test_every_env_variable_is_documented` | the test reads the settings and fails on an undocumented variable |
| `docker-compose.yml`: PostgreSQL, Gunicorn Django, Next.js, health checks | Written, not verified here | `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`; test `core/tests_deploy.py` checks only the frontend is published | No Docker on this machine. To verify: `docker compose up --build`, then `docker compose ps` must show three healthy services |
| `GET /api/v1/health/` | Done | `core/tests_deploy.py`, `HealthView` | `/api/` stays as an alias for one release |
| Compose healthy | Written, not verified here | as above | needs Docker |
| No secrets in git | Done | `python scripts/secret_scan.py` over working tree and full history: 0 findings; detect-secrets false positives reviewed | |
| `.gitignore` for db, uploads, env | Done | `.gitignore` | |

### 2. Organisation: Department, Role, Capability
| Row | Status | Evidence | Note |
|-----|--------|----------|------|
| Department model | Done | `accounts/models.py` | |
| Role model belonging to a department | Done | `Role`, `User.role_ref`, migrations 0004 to 0007 (legacy column dropped after the suite passed without it) | forward and backward data migration tested with `MigrationExecutor` in `accounts/tests_organization.py` |
| Capability model, roles hold capabilities | Done | `Capability`, `accounts/catalog.py` (44 capabilities) | |
| Nine roles including Super Admin | Done | `accounts/tests_organization.py` | Super Admin has no department |
| Super Admin gets every capability automatically | Done | `core/tests_capabilities.py::GrantTests::test_super_admin_holds_everything` | |
| Idempotent `seed_organization` | Done | `accounts/tests_organization.py` runs it twice and compares counts; grants made by hand survive | |
| Grant a capability without touching view code | Done | `core/tests_capabilities.py::GrantTests::test_granting_and_revoking_payment_view` | add then remove a capability on a role, endpoint opens then closes |

### 3. Authentication with HttpOnly cookies
| Row | Status | Evidence | Note |
|-----|--------|----------|------|
| Login by username or email, case-insensitive | Done | `accounts/tests_auth_cookies.py`; browser: username in other case signs in | additive nullable `username`, unique on `Lower()` |
| Tokens only in HttpOnly, SameSite=Lax cookies | Done | `tests_auth_cookies.py` (flags, no token in the body); browser `cookies.js`: page cannot read tokens, no storage use | `Secure` is on in production settings and by default outside DEBUG; browsers accept it on localhost |
| Refresh with rotation and blacklist | Done | test: replayed refresh token is refused | |
| Logout | Done | test: refresh blacklisted, cookies cleared | |
| `/auth/me/` returns user and capabilities | Done | `UserSerializer.capabilities`, test | |
| CSRF double-submit on unsafe requests | Done | tests; browser: PATCH without header 403, with header 200 | |
| Proof: tokens unreadable from JS, reused refresh rejected, no-CSRF POST rejected | Done | the three tests above and `qa/browser/cookies.js` | |

### 4. Capability RBAC
| Row | Status | Evidence | Note |
|-----|--------|----------|------|
| `HasCapability`, fail closed | Done | `accounts/permissions.py`; `core/tests_capabilities.py::FailClosedTests::test_a_role_with_no_capability_only_reaches_open_endpoints` | a view with no declaration answers 403 |
| Every view declares its capabilities per action | Done | `DeclarationTests::test_every_endpoint_declares_its_capabilities_or_is_public` walks the URL table | only login, refresh, logout and health are public |
| Migrate role-key checks without changing who can do what | Done | the existing suite (429 tests at that point) stayed green unchanged; matrix dump before/after over 645 endpoint x role cells (`core/tests_matrix_dump.py`): no cell changed from allowed to denied or back, apart from the differences listed below | see "Differences found by the before/after dump" |
| Generated matrix over every endpoint x every role | Done | `core/permission_audit.py`, `core/tests_hardening.py` | |
| Allowed and denied tests per role | Done | `FailClosedTests::test_removing_any_one_capability_closes_every_endpoint_that_names_it`: 134 generated denial cases, one per capability per endpoint | |
| Frontend reads capabilities only to show or hide | Done | `frontend/src/lib/can.ts`; no `role_key` branch remains in guards or the sidebar (grep) | `role_key` is still used to word a few labels |

**Differences found by the before/after dump** (all intended, none widens access): unsupported methods now answer 405 instead of 403; the DRF index pages (`/api/v1/`, `/api/v1/lookups/`) answer 403 to everyone (nothing reads them); `POST auth/refresh/` with no usable cookie answers 403 (CSRF check first) instead of 400, and `POST auth/logout/` answers 204 instead of 401 to nobody (sign-out is idempotent by design).

### 5. User management and first login
| Row | Status | Evidence | Note |
|-----|--------|----------|------|
| List, search, filter, create, edit, activate, deactivate | Done | `accounts/tests_users_security.py::test_list_search_filter` (department, role, status filters added) | |
| Reset password | Done | `RevocationTests`, `AuditTrailTests` | |
| 16-character random temporary password shown once | Done | `test_create_shows_a_16_character_password_once` | `secrets`, one of each character class, no look-alikes |
| Stored only as Argon2 hash | Done | `test_temporary_password_is_stored_only_as_an_argon2_hash` | `argon2-cffi`; PBKDF2 stays second so old hashes verify |
| Never in logs, audit or DB | Done | `test_the_password_appears_nowhere_it_should_not` scans the log stream and every column of every table | |
| Until changed, only me / password-change / logout work | Done | `test_first_sign_in_allows_only_me_password_change_and_sign_out`; browser check | |
| Password policy: min 12, not common, not similar, not the current one | Done | `test_password_policy` | Django validators plus an explicit current-password rule |
| Super Admin protected from the CEO, including forged requests | Done | `test_super_admin_is_invisible_and_untouchable_for_the_ceo` (404 on read, edit, deactivate, reset; role not offered, forged create refused) | |
| Nobody changes their own role, department or status | Done | `test_nobody_changes_their_own_role_department_or_status` | |
| Role choices depend on the department | Done | `test_role_choices_depend_on_the_department`, `GET /api/v1/roles/?department=` | the form still offers head / member per department, which maps one to one |

### 6. Revocation, lockout, audit, error envelope
| Row | Status | Evidence | Note |
|-----|--------|----------|------|
| `token_version` claim, bumped on password change, reset, deactivation, role change | Done | `RevocationTests` (old access and refresh tokens refused after each) | |
| Deactivated user cut off on the next request | Done | `test_deactivation_voids_the_old_token` | |
| Lockout 5 failures in 5 minutes, per-IP throttle | Done | `LockoutTests::test_the_sixth_attempt_is_blocked_even_with_the_right_password`, `test_per_address_throttle`; browser: `[401 x5, 429]` | |
| Audit trail: logins, failures, password, user and language changes with actor, target, IP, user agent | Done | `audit.SecurityEvent` (append-only), `AuditTrailTests` | `ActionLog` still feeds attendance |
| Secret-like fields refused | Done | `test_secret_like_fields_are_refused` (by key name and by token shape) | |
| One error envelope for the entire API | Done | `core/errors.py` renderer wraps every status of 400 or more; `ErrorEnvelopeTests` cover 400, 401, 403, 404 (record and route), 405, 429, 500 | `response.data` is unchanged for in-process callers; the wire shape is the envelope |
| No stack traces | Done | `test_500_has_no_stack_trace_or_internals` | |

### 7. Shell: i18n, proxy
| Row | Status | Evidence | Note |
|-----|--------|----------|------|
| Language from a cookie | Done | `lang` cookie | |
| `<html lang dir>` set on the server | Done | browser proof: `curl`-style fetch with each cookie returns the right attributes before any script runs | |
| Language saved to the profile | Done | browser proof: switching to Arabic saves `preferred_language`; `language_changed` audit event | |
| next-intl | Different (decided with the user) | in-house `lib/i18n.tsx`, 1,629 keys in each language | kept on the user's instruction; the missing-key script below gives the same safety |
| Logical CSS, RTL layout and icon flipping | Done | browser proof: sidebar moves from left 0 to 1024 when the language flips; RTL screenshots in the QA sweeps | |
| Same-origin proxy `/api/[...path]` | Done | `frontend/src/app/api/[...path]/route.ts`; CSP `connect-src 'self'`; every browser call in the proofs goes through it | |
| Script that fails on a missing key | Done | `npm run i18n:check` (`frontend/scripts/check-i18n.mjs`): equal keys, no empty values, matching placeholders, every literal `t("key")` exists in both files | not yet wired into CI (no CI in the repo) |
| Proof: switching flips layout, persists on a fresh browser | Done | `qa/browser/phase1.js`: a fresh context starts English, becomes Arabic and RTL after sign-in | |

---

## Phase 2: Leads

Gate run: `pytest` 534 passed, 1 skipped; `manage.py test` 535 tests OK (skipped 1); `makemigrations --check` clean; `tsc`, `eslint`, `npm run i18n:check` (1712 keys) and `npm run build` clean. Browser proof: `qa/browser/phase2-browser.txt` (23 checks, English and Arabic) with screenshots in `qa/browser/phase2/`.

### 8. Lead model and normalisation
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Fields name, company, position, phone, email, location; phone or email required | Done | `leads/models.py` (`position`, `location`, migration `0004`); `leads/tests_lead_model.py: LeadFieldsTests` | none |
| E164 normalisation (07.. to +9627.., 00.. to +.., Arabic digits) | Done | `leads/normalize.py`; `tests_lead_model.py: NormaliseTests`; backfill `0005_normalise_keys` | none |
| Lowercased email; database uniqueness constraints | Done | `uniq_open_lead_phone` / `uniq_open_lead_email` (migration `0006`); duplicate gives a field error naming the existing lead; archived leads do not hold keys | none |
| 0797707154 equals +962797707154; concurrent inserts give one lead | Done | `tests_lead_model.py: ConcurrentInsertTests` (threads on a file database, 12/12 isolated runs) | none |
| List with search, filters, ordering, pagination | Done | `tests_lead_model.py: SearchFilterOrderPaginateTests`, `ListQueryCostTests` | none |

Note: a lead can no longer be created as a duplicate on purpose (the old "add anyway" is gone); this follows the brief's database uniqueness. Migration `0005` clears the phone or email key of an older duplicate (keeps the lead) and prints how many.

### 9. Import
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| .xlsx template, Arabic and English | Done | `importer.template_xlsx(lang)`; `ExcelImportTests`; browser: both Excel templates and the CSV template on the page | none |
| CSV kept | Done | `ExcelImportTests`, `leads/tests.py` import tests | none |
| Up to 5,000 rows / 5 MB, type and size errors | Done | `MAX_ROWS`, `MAX_BYTES`; tests for wrong type, too big, too many rows, empty, wrong encoding | none |
| Header matching in either language | Done | `_fold` header map; test with an Arabic-header workbook; browser run uses one | none |
| Skip invalid and duplicate rows (DB and in-file), full skip report | Done | `ImportBatch.skip_report` (migration `0007`); browser: "Import finished" page lists each skipped row with the reason | none |

Note: the old `duplicates=import` option is removed (it conflicts with the uniqueness rule).

### 10. Statuses and history
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Not contacted / Contacted (Waiting) / Rejected / Initial acceptance | Done | labels only: `new` is "Not contacted", `qualified` is "Initial acceptance" (keys unchanged so nothing else moves); EN and AR | none |
| Waiting needs a future date and creates a follow-up appointment | Done | follow-up date must be after today; `appointments/tests.py: FollowUpWorkflowTests` (one open follow-up, replaced on a new date, nothing half-done on refusal) | none |
| Rejected needs a reason and cancels open follow-ups | Done | `test_rejection_cancels_open_follow_ups_and_keeps_the_reason`; acceptance cancels them too | none |
| History (who, from, to, when) | Done | `LeadStatusChange` (migration `0008`), `GET /leads/<id>/history/`; `test_history_endpoint_lists_every_move_in_order`; `test_a_failure_in_the_side_effect_rolls_the_status_back` (transactional); browser: history card on the lead | none |

Limit: leads that existed before migration `0008` have no history rows until their next move (their earlier moves are still in the activity timeline). Not back-filled, because the exact earlier timestamps cannot be reconstructed reliably.

### 11. Appointments and notifications
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Appointment model, five types, own vs manager-all | Done | `appointments/` app; `AppointmentApiTests` (all five types, optional lead, own vs head and CEO all, only the Commercial head assigns); new capabilities `appointment.access`, `.view_all`, `.assign` | none |
| Notifications in the reader's language, polling bell | Done | `notifications/messages.py` (EN and AR kinds); tests read the Arabic title; bell polls through the My Work request | none |
| Idempotent `process_notifications` | Done | `notifications/processing.py`, command `process_notifications`; `ProcessNotificationsTests` (run twice sends once; a reschedule reminds again) | run it every few minutes from cron or a scheduler: written, not verified here |
| Rescheduling a follow-up updates the lead's follow-up date | Done | `test_rescheduling_the_follow_up_moves_the_lead_date` | none |
| Mark one / all read | Done | `test_mark_one_and_mark_all_read_and_unread_count` | none |

### 12. Targets and dashboard
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Target per employee over a date range | Done | `LeadTarget` (user, start_date, end_date, target; migrations `leads/0010-0012`); a manager (`lead.target_manage`) assigns a Marketing employee a number of leads from date A to date B (no overlap per person, at most 366 days); progress %, remaining, days elapsed and left, expected by today (on track or behind) and required per day are computed in the company time zone and tested on the first day, the last day, before and after the range (`tests_insights.py: TargetMathTests`, `TargetApiTests`); an employee sees only their own targets; browser proof EN and AR `qa/browser/phase2/*-targets-*.png` | none |
| Old monthly targets keep working | Done | data migration `leads/0011` turns each monthly target into a date range for its month, assigned to the only active Marketing user (else a team target); reversible; `MonthlyTargetMigrationTests`; also run on a copy of the QA database (40 for November became 2026-11-01 to 2026-11-30 for the Marketing user) | none |
| Leads dashboard (totals, rates, due and overdue, breakdowns, contributors) | Done | `leads/insights.py`; `GET /leads/dashboard/`; browser screenshots EN and AR | none |
| Company time zone for "today"; boundary tests | Done | `test_midnight_boundary_uses_the_company_time_zone_not_utc`, first-day and last-day tests, last-local-minute test | none |
| Numbers equal a manual count | Done | `DashboardTests.test_numbers_equal_a_manual_count` | none |
| "Overdue" opens the filtered pool | Done | `test_overdue_link_filter_returns_exactly_the_overdue_leads`; browser: the overdue card opens `?overdue=1` | none |

Definitions (shown in the code header of `insights.py`): contact rate is leads ever contacted over leads added; acceptance rate is accepted over contacted; archived leads are left out; the dashboard counts only the leads the signed-in person may see.

---

## Phase 3: Sales pipeline

### 13. Conversion and portal
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Initial acceptance converts to a Client and locks the lead (409 `lead_converted`) | Done | `clients/services.convert_lead` runs in the same transaction as the outcome (`test_a_failure_while_converting_rolls_the_acceptance_back`); edit, assign, archive, restore, log, outcome and reopen all answer 409 `lead_converted` (`test_the_lead_is_locked_with_409_lead_converted`); browser: PATCH, archive and log return 409 `lead_converted`, the lead page shows the converted banner with no edit control; `qa/browser/phase3-obj13/` (EN and AR at 375, 768, 1280; script `qa/browser/phase3a.js`) | the lead has no DELETE endpoint at all (archive is the only removal and it is locked too) |
| Client portal account, emailed temporary password | Done | role `client`, capability `portal.access`; `test_account_is_made_and_the_temporary_password_is_emailed` (the password is never written to the audit trail); mail backend from settings (console in development, SMTP variables in `.env.example`) | production needs real SMTP settings: written, not verified here |
| Missing email and email already in use handled | Done | `no_email`, `email_in_use`, `failed` (mail server down) all still convert the lead and say so on the client record; staff can fix the email and press "Send portal login" (resets and re-sends the temporary password); tests `test_missing_email_*`, `test_email_already_in_use_*`, `test_a_mail_server_failure_*`, `test_staff_can_open_the_portal_*`; browser screenshots `client-no_email`, `client-email_in_use` | none |
| Client changes password, lands on `/portal`, sees only own data | Done | first sign-in is held at `/set-password` (`test_first_sign_in_forces_a_new_password`); afterwards `/portal/me/` returns only their client (`test_a_client_sees_only_their_own_company`); a client reaches no endpoint guarded by a staff capability (`test_a_client_can_reach_nothing_a_staff_capability_guards` walks every endpoint); browser: temporary password, set password, lands on `/portal`, another client's company never shown, `/leads` and another client's URL redirect back, API returns 403 or 404 | none |
| Client accounts hidden from user management | Done | excluded from the users queryset and the role list; `test_client_accounts_never_appear_in_user_management`; browser: users page and `/users/` API list no client | none |

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
