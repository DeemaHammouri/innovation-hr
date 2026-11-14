# Architecture

Django 5.2 + DRF + SimpleJWT backend (`/backend`), Next.js 16 + TypeScript + Tailwind v4 frontend (`/frontend`).
Design language: `/frontend/DESIGN.md`. This file is updated at the end of every phase. **Status** shows what exists today.

## 1. Modules (Django apps)

| App | Purpose | Status |
|---|---|---|
| `accounts` | Users, departments, login, forced password change, action log, dashboard summary | Task 1 |
| `clients` | Client records (CEO + Operation head) | Task 1, now audited |
| `core` | The 8 role keys, the record-access registry, readable reference counters, pagination, My Work providers, permission test harness | Phase 1 |
| `audit` | Append-only activity trail for any record | Phase 1 |
| `notifications` | In-app notifications, stored in the recipient's language | Phase 1 |
| `files` | Private uploads, authenticated download, archive | Phase 1 |
| `comments` | Internal comments with permission-limited @mentions | Phase 1 |
| `lookups` | Rejection reasons, services, legal checklist template, work hours, SLA | Phase 1 |
| `leads` | Leads, import batches (CSV), interactions, board + list, SLA flags, daily reminders | Phase 2 (done) |
| `quotations` | Quotations, versions, lines, PDF | Phase 3 |
| `contracts` | Contracts, versions, meetings, visit report | Phase 4 |
| `operations` | KYC / legal checklist, client activation, recurring tasks, QA meetings | Phase 5 |
| `payments` | Schedules, instalments, payments (reversals) | Phase 6 |
| `hr` | Attendance, leave, payroll | Phase 6 |
| `reports` | Funnel, revenue, operations, HR, forecast | Phase 7 |

## 2. The cross-cutting design (Phase 1)

**Roles are derived, never stored.** `core.roles.role_key(user)` maps department + head/member to one of
`ceo, marketing, commercial_head, commercial_member, hr_head, hr_member, operation_head, operation_member`
(or `None` for a developer superuser). The existing department rules in `accounts.User` are untouched.
`UserSerializer` now also returns `role_key`.

**One access registry.** Every record type that can carry an activity trail, comments or files registers once in
`core.access.register(key, Model, can_view, can_write, can_attach=…, can_comment=…, label=…, link=…)`.
The generic endpoints take `?target=<key>:<id>` (for example `client:5`) and apply the **parent record's** rule, so a comment, file or
timeline entry can never be reached by someone who cannot open its record. A record the user may not see answers **404**, so existence never leaks.
Object-level rules (a member sees only assigned leads) live in that record's `can_view`, and the module's queryset uses the same function.

**Audit.** `audit.models.record(actor, obj, action, from_value, to_value, comment)` is called in the same transaction as every state change.
`AuditEntry` refuses `save` on an existing row, `delete`, and queryset `update`/`delete`. There is no write endpoint.
The screen translates `action` keys (`activity.<action>` in both locale files), so adding an action means adding two strings.

**Notifications.** `notifications.service.notify(user, kind, link=…, dedupe_key=…, **params)` renders `notifications/messages.py` in the
recipient's `preferred_language` when it is created. `dedupe_key` makes reminders (overdue) fire once. People only ever read and mark their own.

**Files.** Stored under `PRIVATE_MEDIA_ROOT` (no URL), renamed to a random UUID. Allow-list: pdf, png, jpg, jpeg, docx, xlsx; max 10 MB; the first bytes
must match the extension. Download is `GET /api/files/<id>/download/` with the parent record's permission, `Content-Disposition: attachment`,
`X-Content-Type-Options: nosniff`, `Cache-Control: private, no-store`. Files are archived, never deleted.

**Comments.** Never edited or deleted. A mention is accepted only for an active user who can open the record; each mention notifies that person.

**My Work.** Each module registers a provider with `@core.mywork.provider` that returns plain items
`{kind, section, ref, title, link, due, overdue}`. `GET /api/my-work/` gathers them, orders overdue first, and returns the sidebar badge counts
(`section` = nav key) and the unread notification count. The frontend fetches it once per minute and when the tab regains focus.

**Business records** (from Phase 2) use `core.models.TimeStamped` + `Archivable` (archive instead of delete), `core.models.Sequence.next_ref("LD")`
for readable references (LD-0001, QT-0001, CT-0001, PY-0001), and `core.pagination.StandardPagination` (25, `?page_size=` up to 100).
Existing endpoints stay unpaginated so their behaviour is unchanged.

**Time.** Stored in UTC. `TIME_ZONE` defaults to `Asia/Amman` (`DJANGO_TIME_ZONE` overrides it) and decides "today", months and attendance days.

## 3. State machines (planned; invalid transitions are rejected on the server)

**Lead (built, Phase 2):** New → Contacted → {Waiting (next follow-up date required) | Rejected (reason required; reopenable by the Commercial head with a note) | Qualified}.
Qualified → Quotation requested, or "Skip quotation" → Contract requested (both arrive with Phase 3 and 4).
Only the Commercial head and the assigned member write to the pipeline; the first contact is logged together with its outcome or on its own; a Waiting lead leaves Waiting only through a new outcome; Rejected and Qualified accept nothing except the head's reopen of a Rejected lead.

**Quotation:** Requested → In preparation (HR) → Prepared (HR submits a version) → In review (Commercial head) →
{Signed (head, signer + time stored) | Changes requested (comment required) → new version} → Sent to client →
{Confirmed | Waiting (next follow-up date) | Rejected (reason)}.

**Contract:** Requested → Drafting (HR) → Sent to Commercial (versioned) → Meeting logged → Client signed + visit report uploaded →
CEO review {Approve | Return with comment} → Signed by CEO → Final signed copy uploaded by HR → Handed over to Operation.

**Onboarding:** Handover creates or links the Client; checklist items Pending → Uploaded → Verified | Not applicable (reason); the client is Active when all required items are Verified.

**Instalment:** Expected → Partially paid → Paid; Overdue is derived from the due date. **Payroll run:** Draft → Approved (CEO) → Paid (HR head).

## 4. Permission matrix (server-enforced; the UI only hides what the server would refuse)

| Area | CEO | Marketing | Commercial head | Commercial member | HR head | HR member | Operation head | Operation member |
|---|---|---|---|---|---|---|---|---|
| Lookups (settings) | manage | read | read | read | read | read | read | read |
| Activity / comments / files | follow the parent record | | | | | | | |
| Notifications, My Work | own | own | own | own | own | own | own | own |
| Users | manage | – | – | – | – | – | – | – |
| Clients (Task 1) | manage | – | – | – | – | – | manage | – |
| Leads | read all | create/import, own batches | all, assign | assigned only | – | – | – | – |
| Pipeline | read | – | write | write if assigned | – | – | – | – |
| Quotations | read | – | request, sign | request | prepare/edit | prepare/edit | – | – |
| Contracts | review, sign | – | log meeting, visit report, client copy | same | prepare, upload final | prepare, upload final | read after handover | – |
| Onboarding | read summary | – | read summary | – | – | – | manage, assign | assigned items |
| Recurring tasks, follow-up meetings | read | – | read | read | – | – | define, assign | assigned |
| Payments | read | – | record, manage | – | – | – | – | – |
| Attendance | read | own | own | own | manage | manage | own | own |
| Leave | read | request | request | request | approve | request | request | request |
| Payroll | read, approve | own payslips | own payslips | own payslips | manage | no access | own payslips | own payslips |
| Reports | all | – | own department | – | own department | – | own department | – |

(Rows for later phases are the target; each phase adds the tests that pin its rows.)

## 5. API (current)

All under `/api/`. Everything needs sign-in and a finished forced password change unless noted.

| Endpoint | Who |
|---|---|
| `POST auth/login/`, `auth/refresh/` | public |
| `POST auth/logout/`, `GET/PATCH auth/me/` (PATCH = `preferred_language` only), `POST auth/change-password/` | signed in (work while a password change is pending) |
| `GET dashboard/summary/` | signed in, content by role |
| `GET departments/`, `users/…` (create, edit, activate, deactivate, reset-password) | CEO |
| `clients/…` (list, create, read, edit; no delete) | CEO, Operation head |
| `quotations/…` (list, read, create, `start`, `draft` (PUT), `submit`, `request-changes`, `sign`, `send`, `outcome`, `cancel`) | CEO read; Commercial head/assigned member request, send, record outcome; HR prepare; head signs/cancels |
| `POST leads/<id>/skip-quotation/` | Commercial head or assigned member |
| `contracts/…` (list, read, create, `start`, `send`, `meeting`, `submit`, `approve`, `return`, `handover`, `cancel`) | CEO read, approve, return; Commercial head/assigned member request, meeting, submit; HR draft, send, handover; Commercial head cancels; Operation reads handed-over contracts |
| `GET my-work/` | signed in |
| `GET notifications/` (`?unread=1`), `GET notifications/unread-count/`, `POST notifications/<id>/read/`, `POST notifications/read-all/` | own only |
| `GET activity/?target=` | parent record's view rule; read-only |
| `GET/POST comments/?target=`, `GET mentionable/?target=` | parent record's view rule |
| `GET/POST files/?target=` (multipart), `GET files/<id>/download/`, `POST files/<id>/archive/` | parent record's rules |
| `GET/POST/PATCH lookups/rejection-reasons/`, `services/`, `checklist-template/` (no delete: `is_active=false`) | read: all, write: CEO |
| `GET/PATCH lookups/work-hours/`, `lookups/sla/` | read: all, write: CEO |
| `GET leads/` (filters: `status`, `assigned_to` (id or `none`), `overdue=1`, `archived=1|only`, `batch`, `search`, `ordering`; 25 per page) | CEO, Marketing (own), Commercial head (all), member (assigned) |
| `POST leads/` (`allow_duplicate`), `PATCH leads/<id>/`, `GET leads/board/`, `GET leads/<id>/` | create: Marketing; edit: owner while New, head, assigned member |
| `GET leads/assignees/`, `POST leads/<id>/assign/` | Commercial head |
| `GET/POST leads/<id>/interactions/`, `POST leads/<id>/outcome/` | Commercial head, assigned member |
| `POST leads/<id>/reopen/`, `archive/`, `restore/` | reopen, restore: head; archive: head, or Marketing for an untouched own lead |
| `GET leads/import/template/`, `POST leads/import/preview/`, `POST leads/import/confirm/` (multipart `file`, `duplicates=skip|import`) | Marketing |
| `GET import-batches/`, `POST import-batches/<id>/undo/` | list: Marketing (own), CEO, head; undo: the importer, while no lead was contacted |

**Reminders.** `python manage.py lead_reminders` (overdue follow-ups, leads waiting for a first contact, leads with no assignee) is safe to run any number of times a day: notifications are de-duplicated. The same job also runs once per day on the first `GET my-work/` of the day (`core.daily`), so the system works without a scheduler.

## 6. Frontend structure

`lib/nav.ts` is the one place that decides which links a role sees. `lib/mywork.tsx` feeds sidebar badges, the bell and the My Work list.
`components/records/RecordTabs` gives every detail page the same Overview | Activity | Files | Comments tabs.
New screens reuse `components/ui/*`; no new visual language. Every string is a key in both `locales/en.json` and `locales/ar.json`, and
backend messages shown to people are mapped in `lib/i18n.tsx` (`API_MESSAGES`).

Leads: `components/leads/` holds the browser (list + board, filters in the address bar), `LeadMoves` (the "Move to…" menu, drag and the detail page's primary action all end in the same sheets), `LeadSheets` (contact/outcome, assign, reopen, archive), the stepper and the form with its saved draft. Routes: `/leads`, `/leads/new`, `/leads/import`, `/leads/[id]`, `/leads/[id]/edit`, `/pipeline`.

## 7. Testing

`core.testing.RoleCase` creates one user per role. `assert_matrix(method, url, {role: status, "*": default})` calls the endpoint **as all eight roles**
and fails if any role is left out, so a forgotten role cannot slip through. Browser journeys live outside the repo during development and
screenshots go to `/frontend/.design-review/`.


## 8. Quotations (Phase 3)

- **States:** requested → in_preparation → in_review → (changes_requested → in_preparation …) → signed → sent → waiting ⇄ confirmed | rejected; cancelled from any open state by the Commercial head. One open quotation per lead is a database constraint.
- **Versions:** each submit freezes the version; changes create version N+1 as a copy. Totals are computed server-side (half-up rounding) and the signed version, signer and time are stored. The CEO reads; only the Commercial head signs.
- **Lead integration:** a qualified lead can request a quotation or be marked "skipped" (recorded in the audit trail); both unlock the Contracts step in Phase 4.
- **PDF:** the signed version is shown as an A4 print view in English or Arabic; the browser's "Save as PDF" lays out RTL and Arabic shaping correctly with no external service.
- **Reminders:** `quotation_reminders` daily job notifies the owner of overdue Waiting follow-ups (idempotent per date).


## 9. Contracts (Phase 4)

- **States:** requested -> drafting -> with_commercial -> meeting_logged -> ceo_review -> signed -> handed_over; the CEO may return (ceo_review -> returned, comment required), after which HR redrafts or Commercial updates the documents and resubmits; cancelled (reason, Commercial head) from any open state. One open contract per lead is a database constraint.
- **Gate:** a contract can start only when the lead's quotation is confirmed or the quotation was skipped.
- **Documents:** the files live in the shared attachments store with a category. `draft` (HR, needed to send a version), `visit_report` and `client_signed_copy` (Commercial, both needed to reach the CEO), `final_signed` (HR, needed to hand over). Archived files do not count. The contract payload lists which slots the caller may upload to (`attachable`).
- **Visibility:** CEO, Commercial head and HR see every contract; a Commercial member only their own leads; Operation only handed-over contracts; Marketing none.
- **Client record:** the contract has a nullable `client` link, filled by Operation's onboarding in Phase 5.

## 10. Operation (Phase 5)

- **Client status:** `onboarding` -> `active` (-> `inactive`, reserved). Existing clients default to `active`. Created or linked in `operations.services.onboard`, called by contract hand-over; the match is case-insensitive on company name.
- **Checklist:** copied from the active `ChecklistTemplateItem`s per client (name EN/AR, required, position), so later template changes do not touch existing clients. Item states: pending -> uploaded (automatically when a file is attached, via the registry's `after_attach` hook) -> verified (needs a live file; records verifier and time); not applicable needs a reason (database check); reset returns an item to pending. Removing an item archives it.
- **Activation rule:** `recompute_status` runs after every change. Active exactly when every non-archived required item is verified or not applicable; it flips back to onboarding if that stops being true. A client with no checklist items (legacy) is never changed.
- **Recurring tasks:** frequency daily/weekly/biweekly/monthly/yearly/custom (1-365 days). Due dates are counted from the start date (month ends clamp, e.g. 31 Jan -> 28 Feb -> 31 Mar). `generate_due` creates instances idempotently (unique recurring+due date), catching up at most 12 missed instances per task per run; the first instance appears at creation when it starts today. Complete takes an optional note; skip needs a reason; only the assignee or the Operation head can close one.
- **QA meetings:** per client cadence (7-365 days, default 30); logging needs a date not in the future and notes, and suggests next date = held date + cadence. Overdue meetings and tasks are reminded once per day per item.
- **Access:** CEO, Commercial and Operation can open Operation; Commercial head and members only for clients from their own deals (leads assigned to them or contracts they requested), read-only. Operation staff work items, tasks and meetings; the Operation head customises checklists, recurring tasks and cadence. The generic activity, comments and files endpoints follow the same rules via the `client` and `checklist_item` registry targets.
- **Scheduling:** `python manage.py generate_recurring_tasks` (idempotent) once a day; it also runs on the first request of each day.

## 11. Payments (Phase 6)

- **Who:** the Commercial head writes; the CEO reads. Nobody else, including the Commercial members, can open any payments endpoint (403).
- **Model:** `Instalment` (client, number, due date, amount, currency; one currency per client) and `Payment`, an append-only ledger. A payment row is either `payment` or `reversal`; rows can never be updated or deleted (queryset and model both raise `LedgerError`). A reversal needs a reason, points at the payment it undoes (one reversal per payment, no reversal of a reversal) and counts negatively.
- **Status** is computed, never stored: cancelled, paid (net paid >= amount), overdue (due date passed and balance left, which wins over partially paid), partially paid, expected. Amounts over the remaining balance and future received dates are refused. An instalment with any payment rows cannot be edited; cancelling needs a reason and is blocked while money is held.
- **Receipts** are attachments (`payment` registry target, category `receipt`); the UI offers the upload straight after recording and flags payments without one.
- **Reminders:** `python manage.py check_overdue_payments` notifies the Commercial head and the CEO once per overdue instalment (no amounts in the text). It also runs on the first request of the day. CSV statement export goes through `core.csvout` (formula-injection safe, UTF-8 BOM).

## 12. HR (Phase 6)

- **Attendance** is derived from the audit `ActionLog`: first sign-in and last sign-out of each local day, hours between them, late when the first sign-in is after the CEO-configured `WorkHours.work_start` plus grace (to the minute). Days with no sign-in have no row; a day with no sign-out shows "still open" and no hours. Everyone sees their own; HR and the CEO see the report (range up to 93 days) and CSV. Weekend is Friday and Saturday (`WEEKEND_DAYS`); there is no public-holiday calendar.
- **Leave:** types are managed by the HR head (Annual 21 days, Sick 14 and Unpaid unlimited are seeded). Requests count working days only, stay inside one calendar year, may not overlap another pending or approved request and may not exceed the remaining allowance. The HR head decides everyone's request; the CEO decides the HR head's; the CEO does not request leave. Rejecting needs a note; cancelling is for the owner before the leave starts. The calendar shows approved and pending leave for the month.
- **Payroll:** `EmployeeSalary` (HR head sets; the CEO reads). A monthly `PayrollRun` is Draft -> CEO approved -> Paid. The HR head creates it (one entry per salaried person), edits allowances and deductions while Draft, the CEO approves (or sends it back to Draft with a reason), the HR head marks it paid. Net = base + allowances - deductions and can't be negative (database check). Each employee reads only their own payslips of paid runs, in English or Arabic, printable.
- **Salary privacy:** salary figures appear only in the payroll endpoints for the CEO and the HR head (and a person's own payslip). Audit rows, notifications and logs never contain amounts, and global search never indexes them; a test scans all of these.
- **Scheduling:** `python manage.py check_overdue_payments` once a day, together with `generate_recurring_tasks`.


## 13. Reports, forecast and search (Phase 7)

- **No new tables.** `reports` is read-only over the other modules. Access: Sales funnel = CEO, Commercial head, Marketing (Marketing only over the leads they added, no quotation or contract series); Revenue and Forecast = CEO, Commercial head; Operation = CEO, Operation head; HR = CEO, HR head. Everyone else gets 403 and no menu entry. Lead, quotation and contract figures go through the same `visible_q` rules as their lists.
- **One shape:** every chart is a *series* of points `{key, value, n}` (`reports/series.py`). The screen draws it as bars (blue token family) and as a table (the accessible alternative, with a records column); the CSV export is the same rows. A value with nothing behind it is `null` and reads "Not enough data"; it is never drawn as zero.
- **Funnel:** leads created in the period and how many were contacted, qualified, contract signed and handed over, the conversion between steps (with the base count), rejection reasons for leads and quotations, average hours between stages (pairs with a missing or backwards timestamp are left out and the count shows how many were used), and current first-contact and follow-up SLA breaches.
- **Revenue:** expected (by due month) against received (net of reversals) per currency, plus overdue balances per client.
- **Forecast:** expected = value of open quotations (latest version) x P(confirmed) x, for quotations not yet sent, P(sent). P(confirmed) = confirmed / (confirmed + rejected); P(sent) = reached the client / (reached + cancelled before sending); both from quotations created in the chosen window (default 365 days). If either rests on fewer than 10 records the forecast **refuses** and says why, with the counts. The method, window and counts are always on screen. Unpaid instalments by month (overdue first) are shown separately as contracted money. Currencies are never added together.
- **Search:** `GET /api/search/?q=` (2+ characters) returns up to 5 leads, quotations, contracts and clients per kind, each through its own visibility rule. It only looks at reference, company and contact fields, so no HR, attendance or salary data is reachable. The command palette uses it next to the existing people and client lookups.
- **Performance:** report queries use aggregate counts and one pass over small lists; `created_at` indexes were added to leads, quotations and contracts (additive migrations). Tests assert the funnel and search query counts do not grow with the amount of data.
