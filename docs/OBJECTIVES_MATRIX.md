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
| 14 | Quotation state machine | 3 | 6 | 0 | 0 | 0 |
| 15 | Document rendering (PDF and Word) | 3 | 5 | 0 | 0 | 0 |
| 16 | Meeting reports and contracts | 3 | 6 | 0 | 0 | 0 |
| 17 | Administration tracking and urgent alerts | 3 | 3 (scheduler: written, not verified here) | 0 | 0 | 0 |
| 18 | Handover, Operations privacy | 4 | 4 | 0 | 0 | 0 |
| 19 | KYC, project staffing | 4 | 3 | 0 | 0 | 0 |
| 20 | Recurrence engine, holidays | 4 | 5 | 0 | 0 | 0 |
| 21 | Task lifecycle, escalation, reports | 4 | 6 | 0 | 0 | 0 |
| 22 | General tasks | 5 | 7 | 0 | 0 | 0 |
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
| HR Head assigns, HR prepares (services, frequency, visits, cost, any currency, payment terms), submits | Done | `quotations/services.py` (`assign`, `save_draft`, `submit`); `quotations/tests_phase3.py` (assignment, who may assign); browser (EN and AR, 1280/768/375, `qa/browser/phase3-obj14-17`, script `phase3b.js`): HR head assigns from the menu | none |
| Commercial Head signs with a drawn signature and the company stamp, or returns with notes | Done | `test_sign_*` (blank canvas refused, stamp required, only the head); signature PNG and a copy of the stamp are stored on the quotation; browser: the pad is drawn on and the status becomes signed | the CEO uploads the stamp under Company details first; until then the CEO sees a setup banner and every signer a plain message (see below) |
| Sending issues PREFIX/YYYY/M/NNNN, no gaps or duplicates under concurrency | Done | `core.models.YearSequence` (row lock, one counter per year and key); `quotations/tests_phase3.py ConcurrentNumberTests` (6 threads at a barrier); the number is taken in the same transaction as the status; browser: `QT/2026/11/0005` shown on the page | PostgreSQL concurrency: Written, not verified here (SQLite serialises). Run `DB_ENGINE=postgres DB_NAME=... DB_USER=... DB_PASSWORD=... DB_HOST=... python manage.py test quotations.tests_phase3.ConcurrentNumberTests contracts.tests_numbering` against a scratch PostgreSQL database |
| Client signs on the portal, or staff upload a signed copy as the document of record | Done | `clients/portal.py` sign view, `quotations/services.client_sign`, `upload_signed_copy`; tests in `tests_phase3.py`; browser: the client signs on `/portal`; staff upload makes the quotation Confirmed and the PDF served is the upload | none |
| Illegal transitions rejected; returned notes shown to the preparer | Done | `StateMachineTests` runs every action against every state; browser: returned notes visible to the preparer | none |
| Commercial member keeps send and outcome | Done | `test_commercial_member_can_send_and_record_the_outcome` | none |

### 15. Document rendering
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| One shared rendering module: branded bilingual PDF and Word for quotations, meeting reports and contracts | Done | `backend/documents/` (`model.py` describes a document once; `pdf.py` and `word.py` render it; `builders.py` has `build_quotation`, `build_contract`, `build_meeting_report`); `documents/tests.py` 21 tests; browser: PDF and Word download in EN and AR from the quotation, contract and report pages | Word uses Arial (the brand font is embedded in PDF only) |
| DRAFT watermark until signed (quotation, contract) or approved (meeting report) | Done | `WatermarkTests` (PDF and Word header), `test_a_signed_quotation_is_final_and_an_unsigned_one_is_a_draft`, `test_the_document_is_a_draft_until_approved` | none |
| Uploaded signed copy overrides the generated PDF | Done | `test_the_uploaded_signed_copy_overrides_the_generated_pdf` (`X-Document-Source: signed-copy`); browser asserts the header after an upload | none |
| Arabic shaping and RTL, inspected | Done | rendered PDFs read back with PyMuPDF: words are in joined presentation forms and run right to left (`ArabicShapingTests`); DOCX XML asserted (`w:bidi`, `w:rtl`, `bidiVisual`, schema order); sample pages looked at by eye (`scratchpad/docs_out`) | none |
| Served only through permission-checked endpoints | Done | `/quotations|contracts|meeting-reports/<id>/document/`, `/portal/.../document/` (own records only, 404 otherwise); `test_only_people_who_may_see_the_quotation_can_download_it`, `test_the_client_downloads_only_their_own_sent_quotation`; no public file URL | none |

### 16. Meeting reports and contracts
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Client status after a completed meeting: Confirm, Waiting (schedules a follow-up), Rejection (reason) | Done | `clients/decision.py`, `POST /clients/<id>/decide/`; `meetings/tests.py DecisionTests` (needs a completed meeting; Confirm starts the contract; Waiting books a follow-up appointment; Rejection needs a reason; only the people working the lead); browser: the decision sheet on the lead page | none |
| Meeting report: draft, Commercial signs, CEO approves or returns; one per appointment | Done | `meetings/` app (`MeetingReport.appointment` is one-to-one); `ReportTests` (state machine, returned then signed again, visibility, drafts watermarked); browser: written by the member, signed with the pad by the head, approved by the CEO | none |
| Contract flow: Confirm creates it prefilled from the signed quotation; HR prepares; Commercial confirms or returns; send with its own number; client signs; CEO signs and stamps or uploads the final copy | Done | `contracts/services.py` rewritten; `contracts/tests.py` 31 tests (prefill, country template, return with notes and a new version, confirm, own `CT/YYYY/M/NNNN` sequence, client signs on the portal, CEO drawn signature with stamp, CEO upload, hand-over, every illegal transition); browser: the full path in EN and AR | numbering: same design as quotations, concurrency test `contracts/tests_numbering.py` (6 threads; plus "a failed send gives its number back"). On SQLite it passes; PostgreSQL: Written, not verified here, command in row 14. The old `meeting_logged` state: moved to `with_commercial` by `contracts/0004` and removed by `0005` (see "Leftovers") |
| Templates per country | Done | `ContractTemplate` (country or `*` default), editor page `/admin/templates`, `ContractTemplate` tests (who may edit, country list); default template seeded by migration | none |
| Client Documents tab with every document and version, filtered by permission | Done | `documents/views.py` (`GET /documents/?lead=`), `test_documents_tab_lists_what_each_person_may_see`; browser: Documents list on the lead page | shown on the lead page (the client's page is Operation's) |
| A sent contract blocks the client's status leaving Confirm (409 `contract_sent`) | Done | `test_a_sent_contract_blocks_leaving_confirm_with_409`; an unsent contract is cancelled when the client changes their mind (`test_an_unsent_contract_is_cancelled_*`) | the browser run only checks the 200 path; the 409 is proven by the test |
| Each signer acts only at their step | Done | `test_each_action_has_one_owner` for every action and role; `test_every_illegal_transition_is_refused` | none |

### 17. Administration tracking and alerts
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Process-tracking page: today's changes, late quotations, missed appointments, overdue follow-ups, client pipeline, team activity | Done | `audit/tracking.py`, `GET /admin/tracking/` (CEO only, `tracking.view`); `audit/tests_tracking.py TrackingPageTests`; browser: `/admin/tracking` in EN and AR at all three widths | none |
| Activity feed filterable by employee and action type | Done | `GET /admin/activity/?actor=&action=&kind=&from=&to=`, `/admin/activity/filters/`; `test_the_feed_filters_by_employee_and_action`; browser: filter by employee | none |
| Urgent alerts: HR 60 min after assignment without submitting, Commercial 60 min after submission without signing, appointment open 60 min after its time; thresholds from settings; once per case; reproducible by moving the clock | Done (scheduler: written, not verified here) | `notifications/urgent.py`, run by `process_notifications`; settings `URGENT_*_MINUTES` (also read from the environment); `audit/tests_tracking.py` moves the clock with `mock.patch` (59 min: nothing, 61 min: one alert, second run: none, re-assignment and reschedule are new cases, thresholds from settings); browser: the server was started with 0-minute thresholds and the HR member received `urgent_hr` | a real cron or scheduler must run `process_notifications` every few minutes (see DEPLOYMENT) |

### Phase 3 acceptance fixes
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Full suites after the `.env.example` fix | Done | see the commit report: pytest and `manage.py test` run in full | none |
| Contract numbering: row-locked counter, no gaps, no duplicates, concurrency test | Done (PostgreSQL run: Written, not verified here) | `YearSequence.next_number` is shared with quotations; `contracts/tests_numbering.py` (parallel sends get 1..6; a failed send leaves no gap) passes on SQLite; no PostgreSQL on this machine | run the command in row 14 against PostgreSQL |
| Missing company stamp: CEO banner, friendly bilingual message for every signer, link to the right place | Done | `GET /company/setup/` (any signed-in role; `core/tests_stamp_setup.py`); `StampBanner` (CEO only, on every page) and `StampNotice` in the quotation, report and contract signing sheets (a link only for the person who can upload); the server still refuses with a `stamp` field error if called anyway (`test_signing_needs_the_company_stamp`); browser EN and AR at 375/768/1280 (`qa/browser/phase3-fixes`, `phase3c.js`): banner, messages, upload by the CEO, banner gone, signing then works | none |
| "Write report" on the appointments page where allowed | Done | `permissions.can_write_report` and `report_id` on each appointment (`meetings/tests_appointment_action.py`: completed meeting with a lead and the writer's capability only, link instead once written, no id for people who cannot open the report, constant query count); shared `WriteReportSheet` with the meeting preselected; browser EN and AR | none |
| Old contract `meeting_*` fields and unused keys removed only if provably unused | Done | grep over backend, frontend and docs: no reader or writer left; `contracts/0005_remove_old_meeting_fields` copies any note into the contract history (`meeting_archived`) before dropping the fields, and going back restores them from it (`contracts/tests_migration_0005.py`: forward, back, and the state is gone); also drops `meeting_logged` from the status list and the one-open-contract constraint; 19 unused `ct.*` keys removed in both languages (i18n check: 1960 keys) | see "Leftovers" |

**Leftovers kept on purpose:** `activity.meeting_logged` and `activity.qa_meeting_logged` (history entries written by the old flow and by Operation still need a label); `activity.meeting_archived` is new; `ct.api.*` (the map from server messages to keys: `ct.api.3`, `ct.api.7` and `ct.api.8` match messages the server no longer sends, but removing map entries gains nothing and a message that comes back would show in English); about 40 other unused keys outside contracts (for example `users.*Aria`, `lead.import.field.*`) were not touched because they are not part of this change and some may be built dynamically; `Contract.submitted_to_ceo_at` is still written when the client's copy arrives, so it stays.

---

## Phase 4: Operations

### 18. Handover and Operations privacy
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Handover filled by Commercial, Operations Head accepts, returns, escalates | Done | `operations/handover.py` (draft, submitted, returned, escalated, accepted; created in the same transaction as the contract hand-over); `/api/handovers/` actions `save`, `submit`, `accept`, `return`, `escalate`; `operations/tests_handover.py` (creation, editing, decisions, visibility, illegal-transition matrix, history, My Work); `operations/tests_handover_migration.py` (contracts handed over before this existed get an accepted handover and one project; going back removes only those); browser EN and AR (`docs/evidence/phase4/`, script `qa/browser/phase4a.js`; 375/768/1280 layout of every page, the full walk at 1280): an empty handover is refused on submit, Commercial fills and submits, the Operation head returns with a note (an empty note is refused), Commercial corrects and resubmits, the head accepts and the project is created and linked, the head escalates a second one and the CEO sees the reason; Commercial has no Escalate button and the head has no Edit button. Not covered in the browser (covered by tests): the CEO accepting an escalated handover | none |
| Accepting creates a Project | Done | `Project` (ref `PRJ-`, one per handover, unique constraint); `test_accepting_creates_one_project`; `/projects` page | none |
| No prices or payment data to Operations (whitelist serializers) | Done | `HandoverSerializer` and `ProjectSerializer` are whitelists; `operations/tests_privacy.py` seeds a quotation (7777.77), a contract body (6666.66) and an instalment with a payment (8888.88), then walks every endpoint Operation can reach and fails on any money key or any of those numbers; it found one real leak, `/lookups/services/` (default unit price), now hidden unless the role may price; Operation no longer has `contract.access` or `contract.view_handed_over` (accounts migration 0012, reversible) | none |
| Original contract file unreachable from Operations | Done | `ContractFileIsUnreachableTests`: the file, its download link, the contract record and the files list all answer 403 or 404 to Operation; browser EN and AR (`docs/evidence/phase4/`, `phase4a.js`): the Operation menu has no Quotations, Contracts, Leads or Payments, `/quotations` shows nothing, the quotations, contracts and leads APIs answer 403 and payments 404 for an Operation member, and the handover API carries no price field | none |

### 19. KYC and staffing
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Versioned KYC record and legal checklist with expiry | Done | `ChecklistItemVersion` (every upload is the next version, earlier ones are superseded and kept, unique number per item); template items can carry `has_expiry`, and verifying such an item needs a future expiry date; `expire_documents` (daily, in `operation_daily`) marks expired documents, sends the client back to onboarding, tells the Operation head, warns 30 days ahead, and is safe to repeat; `operations/tests_kyc_staffing.py` (7 tests), `operations/tests_kyc_migration.py` (existing documents become versions, reversible); browser EN and AR (`docs/evidence/phase4/`, `phase4a.js`): the item says verifying needs the expiry date, verifying without it is refused, with it the date is shown, a second file verified again becomes version 2 and version 1 stays as Replaced. Not covered in the browser: a past date being refused (tests) | scheduler must run the daily job (see DEPLOYMENT) |
| Onboarding approval only when KYC verified | Done | `OnboardingNeedsVerifiedTests`: an uploaded but unverified required item keeps the client in onboarding; an expired document does not count even before the daily job has run | none |
| One primary employee per project (DB constraint) plus support; replace needs a reason | Done | `ProjectStaff` with `project_one_active_primary`, `project_person_once_while_active` and an end-needs-reason check; `operations/staffing.py`; only the Operation head (`project.staff`) and only Operation people; replacing the primary needs a reason and keeps the old row with its end date; `StaffingTests` (5 tests, including the database refusing a second active primary); browser EN and AR (`docs/evidence/phase4/`, `phase4a.js`): choose the primary employee, replace without a reason is refused, replace with a reason. This run found and fixed a bug: after a successful save the Team sheet kept its buttons disabled until it was closed and reopened (`StaffSheet.tsx`). Not covered in the browser: the history list (tests) | none |

### 20. Recurrence engine
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Rule types daily to yearly | Done | `operations/recurrence.py` (pure functions): daily, weekly, every 2 weeks, monthly, quarterly, every 6 months, yearly, every N days, always counted from the start date; `operations/tests_recurrence_rules.py` | none |
| One task per (rule, version, period); repeated runs safe | Done | `TaskInstance.rule_version` and `period` with the database constraint `task_one_instance_per_rule_version_period` (replaces one-per-due-date); `generate_due` uses `get_or_create` inside a row lock; `tests_recurrence_engine.py`: five repeated runs create each task once, the database refuses a duplicate period, a task moved to Sunday keeps its month as the period, nothing is made before its due date; `operations/tests_recurrence_migration.py` (older tasks get their due date as period) | none |
| Friday-Saturday weekend and holiday policy, editable calendar | Done | weekend from `WEEKEND_DAYS` (Friday, Saturday); `lookups.Holiday` and `/api/lookups/holidays/` (everyone reads, only `settings.manage` adds or removes, each change logged: `holiday_added`, `holiday_removed`); a task on a weekend or holiday is due the next working day (a daily rule skips closed days instead); CEO tab "Holidays" in Settings; browser EN and AR (`docs/evidence/phase4/`, `qa/browser/phase4.js`; 375/768/1280 layout, the walk at 1280): add a holiday, empty names refused, Operation can read the calendar, remove. Not covered in the browser: a duplicate date refused and Operation unable to change it (tests). The rule editor: add a rule, edit it, the frequency list, sheet at all three widths | none |
| Edits affect only future periods | Done | a changed frequency or start date raises `RecurringTask.version` and counts from today; tasks already made keep their version, dates and titles (`test_editing_the_schedule_starts_a_new_version_and_keeps_past_tasks`); a title or assignee edit changes only tasks created afterwards; a holiday added later does not move a task already made (`test_a_holiday_moves_future_tasks_only`) | none |
| Month-end, leap-year, weekend, holiday unit tests | Done | `operations/tests_recurrence_rules.py` (13 tests, no database): 31st clamps and comes back, 29 February in common and leap years, quarterly and half-yearly from month ends, Friday and Saturday move to Sunday, a holiday and a holiday after the weekend chain, a calendar closed for a year cannot loop | none |

Also closed here (objective 19 gap): the checklist template has a "has expiry" flag, editable by the CEO in Settings, so verifying that item asks for the expiry date.

### 21. Task lifecycle and reports
| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Start, progress, notes, attachments, waiting, blocked, submit; manager approves, returns, escalates | Done | `operations/lifecycle.py` (open, in progress, waiting, blocked, submitted, done): waiting and blocked need a reason, progress is 0 to 100 (database checks too), submit by the assignee, approve or send back (note required) by a reviewer who is never the person who did the work (`operation.review`: Operation head and CEO); notes, files and history use the shared record panels (`task` target); closing straight away is now the head's shortcut; `operations/tests_lifecycle.py` (14 tests); earlier tests updated to the new rule (assignee submits, head approves); browser EN and AR (`docs/evidence/phase4/`, `phase4.js`): start, progress 40%, waiting (empty reason refused), resume, blocked, resume, submit, the assignee has no Approve button, the head sends back (empty note refused), the assignee submits again, the head approves | none |
| Deliverables published to portal and acknowledged | Done | `Deliverable`: only after the task is submitted, only a file attached to that task, once per file; the client's portal lists only their own (`/api/portal/deliverables/`), downloads and confirms once, with time and person kept; Operation is told; `DeliverableTests`; browser EN and AR (`docs/evidence/phase4/`, `phase4.js`): published, shown as not confirmed, the client sees it as new, downloads it, confirms, the task shows the confirmation, and the client's API call to the Operation tasks answers 403. This run found and fixed a bug: after submitting, the assignee had no menu entry to show a file (new `can_publish` flag, test added) | none |
| Escalations unique per case and level | Done | `Escalation` with `escalation_one_per_task_and_level` (level 1 the Operation head, level 2 the CEO); manual by the assignee or the head, automatic for overdue tasks after 2 and 5 days (`settings.TASK_ESCALATION_DAYS`), one level per run; `EscalationTests` (a third is refused, the database refuses a duplicate row, repeated job runs change nothing, closed tasks are never escalated); browser EN and AR (`phase4.js`): the assignee escalates to the head, the head to the CEO, a third is not offered. The automatic escalation job was not run in the browser (tests only) | the daily job must run (see DEPLOYMENT) |
| Monitoring view | Done | `/api/operations/monitoring/` (`operation.monitor`: CEO and Operation head): totals, per person, and a "needs attention" list (late, blocked, waiting for review, escalated); page `/operation/monitoring`; `MonitoringTests` (matrix, numbers, no money); browser EN and AR (`docs/evidence/phase4/`, `phase4.js`): the Operation head and the CEO at 375/768/1280, the blocked and the escalated task listed, no money shown | none |
| JSON, Excel and PDF reports with identical numbers | Done | `/api/reports/<section>/export/?fmt=csv|xlsx|pdf&lang=en|ar` all come from the same rows as the JSON; `operations/tests_reports_and_log.py` reads the JSON, the CSV, the Excel sheet and the text of the PDF (English and Arabic) and compares every value; permissions are the same for every format; spreadsheet cells are written as text so nothing runs as a formula; browser EN and AR: the three Export buttons on `/reports` download CSV, Excel and PDF, and `qa/browser/compare_exports.py` shows the 12 values equal in JSON, CSV, Excel and the PDF text (`docs/evidence/phase4/export-compare-*.txt`); an Operation member is refused another department's export | none |
| Append-only activity log, confirmed per action | Done | every lifecycle step, escalation and deliverable writes an `AuditEntry` in the same transaction; `ActivityLogTests`: every action appears once, saving, deleting, bulk update and bulk delete all raise `ImmutableError`, and a refused step writes nothing | none |

**Phase 4 gate run (16 Nov 2026):** `manage.py test` 762 tests OK (1 skipped, the opt-in matrix dump); `pytest` 761 passed, 1 skipped; `tsc`, `eslint` (no warnings), `npm run i18n:check` (2171 keys) and `next build` clean. Browser: `qa/browser/phase4a.js` (objectives 18-19) and `phase4.js` (objectives 20-21), English and Arabic, 375/768/1280, 306 checks (97 per language for objectives 20-21, 56 for 18-19) with no failure and no console error; export comparison in `docs/evidence/phase4/export-compare-*.txt`. The run found and fixed two bugs: the Team sheet stayed disabled after a save, and the assignee could not show a file to the client after submitting. Still written but not verified here: the items already marked so in the table above (Docker and PostgreSQL, and the schedulers that run the daily jobs).

---

## Phase 5: General tasks

**Phase 5 gate run.** Backend: Django runner 802 tests OK (1 skipped), pytest 805 passed (1 skipped). Frontend: tsc, eslint, `i18n:check` (2232 keys) and `next build` clean. Browser: `docs/evidence/phase5/`, 58 checks per language, 0 failures, on a throwaway database.

### 22. General tasks
Model `generaltasks.GeneralTask` (migration `0001`), app `generaltasks/`, capabilities `gtask.access`, `gtask.assign_team`, `gtask.assign_any` (accounts migration `0014`), page `/tasks`. Browser evidence for every row: `docs/evidence/phase5/` (script `qa/browser/phase5.js`, seed `qa/browser/seed/phase5_general_tasks.py`): English and Arabic, 375/768/1280, 58 checks each, no failure, no console error. Tests: `generaltasks/tests.py` (39).

| Row | Status | Evidence | Work needed |
|-----|--------|----------|-------------|
| Model and screens | Done | title, details, assignee, giver, deadline, status, `done_at`, `done_late`, `alert_round`; database checks (a done task has a time, an open one is never late, no blank title); `/tasks` with five counters, views My tasks, My team and Given by me, filter open, finished or all, a form with refusals, edit, details sheet (notes, files, history through the shared record panels), nav entry and a My Work section; browser: give a task (empty form refuses title, person and deadline), pick a person, edit a deadline | none |
| Scope: the CEO gives to anyone, a department head to their own department | Done | `generaltasks/scope.py`; tests: the CEO to all seven others, a head to their department and to themselves only, members refused (403), inactive and missing people refused, the person picker lists only allowed people; visibility: the assignee, the giver, the department head and the CEO see a task, everyone else gets 404; browser: the CEO's picker lists Commercial, the head's lists only the head's department, a head does not see another department's task, a member sees no other department's task, the API answers 404 and 403 | none |
| Only the assignee can mark it done | Done | `services.mark_done` refuses the CEO, the head and the giver (403) and a second time (400); a done task cannot be edited; browser: the CEO has no "Mark as done" on someone else's task | none |
| "Done late" | Done | `done_late` is set once, when it is marked done, by comparing the local date to the deadline (the deadline day itself is on time); the history writes `gtask_done_late`; the giver is told; tests move the clock; browser: an overdue task finished by its assignee shows "Done late" with its time | none |
| Magic-byte upload checks | Done | tasks are a registered record type, so the shared upload check applies: the file's first bytes must match its extension (PDF, PNG, JPG, DOCX, XLSX), 10 MB, no other types, path and double extensions neutralised; tests: a program renamed to .pdf, a PDF renamed to .png, an empty file, .exe, .js, .html, .zip, an oversized file; only people who can see the task can add or read files; a done task takes no more; browser: a fake PDF is refused, a real one is listed | none |
| Overdue alert re-armed when the deadline changes | Done | one alert per `alert_round`, to the assignee and to the giver; changing the deadline adds 1 to the round, so the next overdue day alerts again, the same date changes nothing, done tasks never alert; daily job `general_tasks_daily`; tests run the job with a moved clock, twice, and after a change. Not covered in the browser: the alert itself, which needs the daily job and a past deadline (tests only) | the daily job must run (see DEPLOYMENT) |
| Counters | Done | `GET /api/tasks/counters/`: open, due today, overdue, done, done late, for the person and, for heads and the CEO, for everything they may see; tests check every number and that they match the list; browser: the five tiles equal the server's numbers | none |

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
