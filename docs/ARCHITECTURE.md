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
| `onboarding` | KYC / legal checklist, client activation, recurring tasks, follow-up meetings | Phase 5 |
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
