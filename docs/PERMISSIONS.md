# Permissions

Every rule below is enforced by the server on each request; the screens only hide what the server would refuse. Object-level checks
(for example "a Commercial member sees only leads assigned to them") apply on top of the module-level rules. Each row is covered by a
test in the owning app.

Roles are derived from department and head/member: **CEO** (Administration head), **Marketing** (single seat), **Commercial head / member**,
**HR head / member**, **Operation head / member**. A developer superuser without a department has no business role and no access.

| Area | CEO | Marketing | Commercial head | Commercial member | HR head | HR member | Operation head | Operation member |
|---|---|---|---|---|---|---|---|---|
| Users and departments (create, edit, deactivate, reset password) | write | no | no | no | no | no | no | no |
| Lookups and settings (services, rejection reasons, SLA, work hours, checklist template) | write | read | read | read | read | read | read | read |
| Leads: see | all | own imports | all | assigned to them | no | no | no | no |
| Leads: import, assign, archive, approve outcomes | no | import | assign, archive | work own (contact, qualify, reject) | no | no | no | no |
| Quotations: see | all | no | all | own leads | all | all | no | no |
| Quotations: request | no | no | yes | yes (own leads) | no | no | no | no |
| Quotations: prepare, submit | no | no | no | no | yes | yes | no | no |
| Quotations: sign (approve or return) | no | no | yes (head only) | no | no | no | no | no |
| Quotations: send, record outcome, follow up | no | no | yes | own leads | no | no | no | no |
| Contracts: see | all | no | all | own leads | all | all | handed over only | handed over only |
| Contracts: request | no | no | yes | own leads | no | no | no | no |
| Contracts: draft, upload, hand over | no | no | no | no | yes | yes | no | no |
| Contracts: log meeting | no | no | yes | own leads | no | no | no | no |
| Contracts: sign (approve or return) | yes | no | no | no | no | no | no | no |
| Clients and Operation: see | all | no | own deals, read-only | own deals, read-only | no | no | all | all |
| Operation: checklist, tasks, QA meetings | no | no | no | no | no | no | write | write (tasks assigned to them; head customises) |
| Tasks: start, progress, wait, block, submit | no | no | no | no | no | no | any task | own tasks |
| Tasks: approve or send back (never your own work) | yes | no | no | no | no | no | yes | no |
| Tasks: escalate (level 1 to the head, level 2 to the CEO) | no | no | no | no | no | no | both levels | level 1 on own tasks |
| Tasks: show a file to the client | no | no | no | no | no | no | yes | own tasks |
| Operation monitoring view | yes | no | no | no | no | no | yes | no |
| Holiday calendar: read / change | read, change | read | read | read | read | read | read | read |
| Handovers: see | all | no | own (the deals they prepared) | own | no | no | submitted, escalated, accepted and returned | read-only, same as head |
| Handovers: fill in, submit | no | no | yes (own deals) | yes (own deals) | no | no | no | no |
| Handovers: accept, return | yes | no | no | no | no | no | yes | no |
| Handovers: escalate to the CEO | no | no | no | no | no | no | yes | no |
| Projects: see | yes | no | read-only | no | no | no | yes | yes |
| Projects: choose primary employee and support | no | no | no | no | no | no | yes | no |
| General tasks: see | all | own | own and their department's | own | own and their department's | own | own and their department's | own |
| General tasks: give a task, change its title, deadline or person | to anyone | no | to their own department (themselves included) | no | to their own department | no | to their own department | no |
| General tasks: mark as done | only the person it was given to, never the giver, the head or the CEO (every role, on their own tasks) |||||||| 
| General tasks: add notes and files (PDF, PNG, JPG, DOCX, XLSX up to 10 MB, checked by their first bytes) | while open: assignee, giver, the department head and the CEO |||||||| 
| Prices, payments and the contract file | yes (as before) | no | quotations: yes | quotations: own | contracts: yes | contracts: yes | never | never |
| Payments (schedule, record, reverse) | read | no | write | no | no | no | no | no |
| Attendance | own, all (report) | own | own | own | own, all (report) | own, all (report) | own | own |
| Leave: request | no | yes | yes | yes | yes | yes | yes | yes |
| Leave: decide | HR head's requests | no | no | no | everyone else's | no | no | no |
| Leave: calendar | everyone | own | own | own | everyone | everyone | own | own |
| Salaries | read | no | no | no | write | no | no | no |
| Payroll runs | approve, send back | no | no | no | create, edit draft, mark paid | no | no | no |
| Payslips | own | own | own | own | own | own | own | own |
| Reports: Sales funnel | yes | own leads only | yes | no | no | no | no | no |
| Reports: Revenue, Forecast | yes | no | yes | no | no | no | no | no |
| Reports: Operation | yes | no | no | no | no | no | yes | no |
| Reports: HR | yes | no | no | no | yes | no | no | no |
| Global search | leads, quotations, contracts, clients | leads (own) | leads, quotations, contracts, clients (own deals) | own leads, quotations, contracts | quotations, contracts | quotations, contracts | contracts (handed over), clients | contracts (handed over), clients |
| Notifications, comments, files on a record | whoever can see the record (comments and files also need write access to the record for the file category) | | | | | | | |

Rules that cut across modules:

- **Salary data** is visible only to the CEO, the HR head and the employee's own payslip. It never appears in audit rows, notifications, log output, reports, CSV exports of other modules or global search (a test scans all of these).
- **No hard deletes.** Records are archived, cancelled or reversed with a reason. Audit entries and payment ledger rows cannot be updated or deleted, even from code (`ImmutableError`, `LedgerError`).
- **Files** are never served from a public URL. Downloads go through an authenticated endpoint that re-checks the record's rule, forces download and sets `nosniff`. Uploads are limited to PDF, PNG, JPG, DOCX and XLSX up to 10 MB, with the file's first bytes checked against its extension.
- **Sign-in** locks after 8 wrong passwords for one email (or 40 from one address) for 15 minutes. The answer for an unknown email, a wrong password and a deactivated account is identical.

## The endpoint sweep

`core/tests_hardening.py::PermissionAuditTests` walks every API URL and tries GET, POST, PUT, PATCH and DELETE as an anonymous caller and
as each of the eight roles. It fails if any endpoint other than sign-in, token refresh and the health check answers an anonymous caller,
or if any request ends in a server error. Regenerate the table below with:

```
cd backend
set WRITE_PERMISSIONS=..\docs\.permissions-matrix.md
python manage.py test core.tests_hardening.PermissionAuditTests.test_sweep
```

The table shows the status each role gets when the request carries no body and no record exists, so it exposes the **module-level** gate
(403 = refused by role, 400 = reached validation, 200 = allowed). Object-level rules (404 for a record you may not see) are covered by
each module's own tests. Role columns: CEO, Mkt = Marketing, ComH / ComM = Commercial head / member, HRH / HRM = HR head / member,
OpH / OpM = Operation head / member.

| Method | Endpoint | anon | CEO | Mkt | ComH | ComM | HRH | HRM | OpH | OpM |
|---|---|---|---|---|---|---|---|---|---|---|
| GET | `/api/v1/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/activity/` | 401 | 400 | 400 | 400 | 400 | 400 | 400 | 400 | 400 |
| GET | `/api/v1/admin/activity/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/admin/activity/filters/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/admin/tracking/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/appointments/` | 401 | 200 | 200 | 200 | 200 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/appointments/` | 401 | 400 | 400 | 400 | 400 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/appointments/1/` | 401 | 404 | 404 | 404 | 404 | 403 | 403 | 403 | 403 |
| PATCH | `/api/v1/appointments/1/` | 401 | 404 | 404 | 404 | 404 | 403 | 403 | 403 | 403 |
| PUT | `/api/v1/appointments/1/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/appointments/1/cancel/` | 401 | 404 | 404 | 404 | 404 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/appointments/1/complete/` | 401 | 404 | 404 | 404 | 404 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/appointments/1/reschedule/` | 401 | 404 | 404 | 404 | 404 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/appointments/assignees/` | 401 | 403 | 403 | 200 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/auth/change-password/` | 401 | 400 | 400 | 400 | 400 | 400 | 400 | 400 | 400 |
| POST | `/api/v1/auth/login/` | 400 | 400 | 400 | 400 | 400 | 400 | 400 | 400 | 400 |
| POST | `/api/v1/auth/logout/` | 204 | 204 | 204 | 204 | 204 | 204 | 204 | 204 | 204 |
| GET | `/api/v1/auth/me/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| PATCH | `/api/v1/auth/me/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| POST | `/api/v1/auth/refresh/` | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/clients/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 200 | 403 |
| POST | `/api/v1/clients/` | 401 | 400 | 403 | 403 | 403 | 403 | 403 | 400 | 403 |
| GET | `/api/v1/clients/1/` | 401 | 404 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| PATCH | `/api/v1/clients/1/` | 401 | 404 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| PUT | `/api/v1/clients/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 405 | 403 |
| POST | `/api/v1/clients/1/decide/` | 401 | 403 | 403 | 404 | 404 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/clients/1/portal/` | 401 | 404 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| GET | `/api/v1/comments/` | 401 | 400 | 400 | 400 | 400 | 400 | 400 | 400 | 400 |
| POST | `/api/v1/comments/` | 401 | 400 | 400 | 400 | 400 | 400 | 400 | 400 | 400 |
| GET | `/api/v1/company/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/v1/company/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/company/setup/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/company/stamp/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/contract-templates/` | 401 | 200 | 403 | 200 | 200 | 200 | 200 | 403 | 403 |
| POST | `/api/v1/contract-templates/` | 401 | 400 | 403 | 403 | 403 | 400 | 403 | 403 | 403 |
| DELETE | `/api/v1/contract-templates/1/` | 401 | 405 | 403 | 403 | 403 | 405 | 403 | 403 | 403 |
| GET | `/api/v1/contract-templates/1/` | 401 | 200 | 403 | 200 | 200 | 200 | 200 | 403 | 403 |
| PATCH | `/api/v1/contract-templates/1/` | 401 | 200 | 403 | 403 | 403 | 200 | 403 | 403 | 403 |
| PUT | `/api/v1/contract-templates/1/` | 401 | 405 | 403 | 403 | 403 | 405 | 403 | 403 | 403 |
| GET | `/api/v1/contracts/` | 401 | 200 | 403 | 200 | 200 | 200 | 200 | 403 | 403 |
| POST | `/api/v1/contracts/` | 401 | 404 | 403 | 404 | 404 | 404 | 404 | 403 | 403 |
| GET | `/api/v1/contracts/1/` | 401 | 404 | 403 | 404 | 404 | 404 | 404 | 403 | 403 |
| POST | `/api/v1/contracts/1/approve/` | 401 | 404 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/contracts/1/cancel/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/contracts/1/client-copy/` | 401 | 404 | 403 | 404 | 404 | 404 | 404 | 403 | 403 |
| POST | `/api/v1/contracts/1/commercial-return/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/contracts/1/confirm/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/contracts/1/document/` | 401 | 404 | 403 | 404 | 404 | 404 | 404 | 403 | 403 |
| PATCH | `/api/v1/contracts/1/draft/` | 401 | 403 | 403 | 403 | 403 | 404 | 404 | 403 | 403 |
| POST | `/api/v1/contracts/1/draft/` | 401 | 403 | 403 | 403 | 403 | 404 | 404 | 403 | 403 |
| POST | `/api/v1/contracts/1/handover/` | 401 | 403 | 403 | 403 | 403 | 404 | 404 | 403 | 403 |
| POST | `/api/v1/contracts/1/return/` | 401 | 404 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/contracts/1/send-to-client/` | 401 | 403 | 403 | 403 | 403 | 404 | 404 | 403 | 403 |
| POST | `/api/v1/contracts/1/send/` | 401 | 403 | 403 | 403 | 403 | 404 | 404 | 403 | 403 |
| POST | `/api/v1/contracts/1/start/` | 401 | 403 | 403 | 403 | 403 | 404 | 404 | 403 | 403 |
| GET | `/api/v1/dashboard/summary/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/departments/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/files/` | 401 | 400 | 400 | 400 | 400 | 400 | 400 | 400 | 400 |
| POST | `/api/v1/files/` | 401 | 415 | 415 | 415 | 415 | 415 | 415 | 415 | 415 |
| GET | `/api/v1/handovers/` | 401 | 200 | 403 | 200 | 200 | 403 | 403 | 200 | 200 |
| GET | `/api/v1/handovers/1/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| POST | `/api/v1/handovers/1/accept/` | 401 | 404 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| POST | `/api/v1/handovers/1/escalate/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| POST | `/api/v1/handovers/1/return/` | 401 | 404 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| POST | `/api/v1/handovers/1/save/` | 401 | 403 | 403 | 404 | 404 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/handovers/1/submit/` | 401 | 403 | 403 | 404 | 404 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/health/` | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/hr/attendance/` | 401 | 200 | 403 | 403 | 403 | 200 | 200 | 403 | 403 |
| GET | `/api/v1/hr/attendance/export/` | 401 | 200 | 403 | 403 | 403 | 200 | 200 | 403 | 403 |
| GET | `/api/v1/hr/attendance/mine/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/hr/attendance/mine/export/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/hr/leave-types/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| POST | `/api/v1/hr/leave-types/` | 401 | 403 | 403 | 403 | 403 | 400 | 403 | 403 | 403 |
| PATCH | `/api/v1/hr/leave-types/1/` | 401 | 403 | 403 | 403 | 403 | 200 | 403 | 403 | 403 |
| GET | `/api/v1/hr/leave/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| POST | `/api/v1/hr/leave/` | 401 | 403 | 400 | 400 | 400 | 400 | 400 | 400 | 400 |
| GET | `/api/v1/hr/leave/balance/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/hr/leave/calendar/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| PATCH | `/api/v1/hr/payroll/entries/1/` | 401 | 403 | 403 | 403 | 403 | 404 | 403 | 403 | 403 |
| GET | `/api/v1/hr/payroll/runs/` | 401 | 200 | 403 | 403 | 403 | 200 | 403 | 403 | 403 |
| POST | `/api/v1/hr/payroll/runs/` | 401 | 403 | 403 | 403 | 403 | 400 | 403 | 403 | 403 |
| GET | `/api/v1/hr/payroll/runs/1/` | 401 | 404 | 403 | 403 | 403 | 404 | 403 | 403 | 403 |
| POST | `/api/v1/hr/payroll/runs/1/approve/` | 401 | 404 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/hr/payroll/runs/1/export/` | 401 | 404 | 403 | 403 | 403 | 404 | 403 | 403 | 403 |
| POST | `/api/v1/hr/payroll/runs/1/pay/` | 401 | 403 | 403 | 403 | 403 | 404 | 403 | 403 | 403 |
| POST | `/api/v1/hr/payroll/runs/1/refresh/` | 401 | 403 | 403 | 403 | 403 | 404 | 403 | 403 | 403 |
| POST | `/api/v1/hr/payroll/runs/1/reopen/` | 401 | 404 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/hr/payslips/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/hr/people/` | 401 | 200 | 403 | 403 | 403 | 200 | 200 | 403 | 403 |
| GET | `/api/v1/hr/salaries/` | 401 | 200 | 403 | 403 | 403 | 200 | 403 | 403 | 403 |
| PUT | `/api/v1/hr/salaries/1/` | 401 | 403 | 403 | 403 | 403 | 400 | 403 | 403 | 403 |
| GET | `/api/v1/import-batches/` | 401 | 200 | 200 | 200 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/import-batches/1/` | 401 | 404 | 404 | 404 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/import-batches/1/undo/` | 401 | 404 | 404 | 404 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/leads/` | 401 | 200 | 200 | 200 | 200 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/leads/` | 401 | 403 | 400 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/leads/1/` | 401 | 404 | 404 | 404 | 404 | 403 | 403 | 403 | 403 |
| PATCH | `/api/v1/leads/1/` | 401 | 404 | 404 | 404 | 404 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/leads/1/archive/` | 401 | 404 | 404 | 404 | 404 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/leads/1/assign/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/leads/1/history/` | 401 | 404 | 404 | 404 | 404 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/leads/1/interactions/` | 401 | 404 | 404 | 404 | 404 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/leads/1/interactions/` | 401 | 404 | 404 | 404 | 404 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/leads/1/outcome/` | 401 | 404 | 404 | 404 | 404 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/leads/1/reopen/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/leads/1/restore/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/leads/1/skip-quotation/` | 401 | 404 | 404 | 404 | 404 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/leads/assignees/` | 401 | 403 | 403 | 200 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/leads/board/` | 401 | 200 | 200 | 200 | 200 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/leads/dashboard/` | 401 | 200 | 200 | 200 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/leads/import/confirm/` | 401 | 403 | 400 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/leads/import/preview/` | 401 | 403 | 400 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/leads/import/template/` | 401 | 403 | 200 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/leads/targets/` | 401 | 200 | 200 | 200 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/leads/targets/` | 401 | 400 | 403 | 400 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/v1/leads/targets/1/` | 401 | 404 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/leads/targets/1/` | 401 | 404 | 404 | 404 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/v1/leads/targets/1/` | 401 | 404 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/leads/targets/assignees/` | 401 | 200 | 403 | 200 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/lookups/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/lookups/checklist-template/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| POST | `/api/v1/lookups/checklist-template/` | 401 | 400 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/v1/lookups/checklist-template/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/lookups/checklist-template/1/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| PATCH | `/api/v1/lookups/checklist-template/1/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/v1/lookups/checklist-template/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/lookups/holidays/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| POST | `/api/v1/lookups/holidays/` | 401 | 400 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/v1/lookups/holidays/1/` | 401 | 404 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/lookups/rejection-reasons/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| POST | `/api/v1/lookups/rejection-reasons/` | 401 | 400 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/v1/lookups/rejection-reasons/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/lookups/rejection-reasons/1/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| PATCH | `/api/v1/lookups/rejection-reasons/1/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/v1/lookups/rejection-reasons/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/lookups/services/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| POST | `/api/v1/lookups/services/` | 401 | 400 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/v1/lookups/services/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/lookups/services/1/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| PATCH | `/api/v1/lookups/services/1/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/v1/lookups/services/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/lookups/sla/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| PATCH | `/api/v1/lookups/sla/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/v1/lookups/sla/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/lookups/work-hours/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| PATCH | `/api/v1/lookups/work-hours/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/v1/lookups/work-hours/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/meeting-reports/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| POST | `/api/v1/meeting-reports/` | 401 | 403 | 403 | 404 | 404 | 403 | 403 | 403 | 403 |
| PATCH | `/api/v1/meeting-reports/1/` | 401 | 403 | 403 | 404 | 404 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/meeting-reports/1/approve/` | 401 | 404 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/meeting-reports/1/return/` | 401 | 404 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/meeting-reports/1/sign/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/mentionable/` | 401 | 400 | 400 | 400 | 400 | 400 | 400 | 400 | 400 |
| GET | `/api/v1/my-work/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/notifications/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| POST | `/api/v1/notifications/read-all/` | 401 | 204 | 204 | 204 | 204 | 204 | 204 | 204 | 204 |
| GET | `/api/v1/notifications/unread-count/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/operations/assignees/` | 401 | 200 | 403 | 200 | 200 | 403 | 403 | 200 | 200 |
| POST | `/api/v1/operations/checklist/1/archive/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| POST | `/api/v1/operations/checklist/1/not-applicable/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 404 |
| POST | `/api/v1/operations/checklist/1/required/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| POST | `/api/v1/operations/checklist/1/reset/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 404 |
| POST | `/api/v1/operations/checklist/1/verify/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 404 |
| GET | `/api/v1/operations/clients/` | 401 | 200 | 403 | 200 | 200 | 403 | 403 | 200 | 200 |
| GET | `/api/v1/operations/clients/1/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| POST | `/api/v1/operations/clients/1/cadence/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| POST | `/api/v1/operations/clients/1/checklist/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| GET | `/api/v1/operations/meetings/` | 401 | 200 | 403 | 200 | 200 | 403 | 403 | 200 | 200 |
| POST | `/api/v1/operations/meetings/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 404 |
| GET | `/api/v1/operations/monitoring/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 200 | 403 |
| GET | `/api/v1/operations/recurring/` | 401 | 200 | 403 | 200 | 200 | 403 | 403 | 200 | 200 |
| POST | `/api/v1/operations/recurring/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| GET | `/api/v1/operations/recurring/1/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| PATCH | `/api/v1/operations/recurring/1/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| PUT | `/api/v1/operations/recurring/1/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| GET | `/api/v1/operations/tasks/` | 401 | 200 | 403 | 200 | 200 | 403 | 403 | 200 | 200 |
| GET | `/api/v1/operations/tasks/1/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| POST | `/api/v1/operations/tasks/1/approve/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| POST | `/api/v1/operations/tasks/1/block/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| POST | `/api/v1/operations/tasks/1/complete/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| POST | `/api/v1/operations/tasks/1/escalate/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| POST | `/api/v1/operations/tasks/1/progress/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| POST | `/api/v1/operations/tasks/1/publish/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| POST | `/api/v1/operations/tasks/1/resume/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| POST | `/api/v1/operations/tasks/1/return/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| POST | `/api/v1/operations/tasks/1/skip/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| POST | `/api/v1/operations/tasks/1/start/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| POST | `/api/v1/operations/tasks/1/submit/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| POST | `/api/v1/operations/tasks/1/wait/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| GET | `/api/v1/payments/clients/1/` | 401 | 404 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/payments/clients/1/export/` | 401 | 404 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/payments/clients/1/schedule/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/v1/payments/instalments/1/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/payments/instalments/1/cancel/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/payments/instalments/1/payments/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/payments/overview/` | 401 | 200 | 403 | 200 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/payments/records/1/reverse/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/portal/contracts/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/portal/contracts/1/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/portal/contracts/1/document/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/portal/contracts/1/sign/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/portal/deliverables/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/portal/deliverables/1/acknowledge/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/portal/deliverables/1/download/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/portal/me/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/portal/quotations/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/portal/quotations/1/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/portal/quotations/1/document/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/portal/quotations/1/sign/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/projects/` | 401 | 200 | 403 | 200 | 403 | 403 | 403 | 200 | 200 |
| GET | `/api/v1/projects/1/` | 401 | 404 | 403 | 404 | 403 | 403 | 403 | 404 | 404 |
| POST | `/api/v1/projects/1/primary/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| POST | `/api/v1/projects/1/remove/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| POST | `/api/v1/projects/1/support/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| GET | `/api/v1/quotations/` | 401 | 200 | 403 | 200 | 200 | 200 | 200 | 403 | 403 |
| POST | `/api/v1/quotations/` | 401 | 404 | 403 | 404 | 404 | 404 | 404 | 403 | 403 |
| GET | `/api/v1/quotations/1/` | 401 | 404 | 403 | 404 | 404 | 404 | 404 | 403 | 403 |
| POST | `/api/v1/quotations/1/assign/` | 401 | 403 | 403 | 403 | 403 | 404 | 403 | 403 | 403 |
| POST | `/api/v1/quotations/1/cancel/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/quotations/1/document/` | 401 | 404 | 403 | 404 | 404 | 404 | 404 | 403 | 403 |
| PUT | `/api/v1/quotations/1/draft/` | 401 | 403 | 403 | 403 | 403 | 404 | 404 | 403 | 403 |
| POST | `/api/v1/quotations/1/outcome/` | 401 | 404 | 403 | 404 | 404 | 404 | 404 | 403 | 403 |
| POST | `/api/v1/quotations/1/request-changes/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/quotations/1/send/` | 401 | 404 | 403 | 404 | 404 | 404 | 404 | 403 | 403 |
| POST | `/api/v1/quotations/1/sign/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/quotations/1/signed-copy/` | 401 | 404 | 403 | 404 | 404 | 404 | 404 | 403 | 403 |
| POST | `/api/v1/quotations/1/start/` | 401 | 403 | 403 | 403 | 403 | 404 | 404 | 403 | 403 |
| POST | `/api/v1/quotations/1/submit/` | 401 | 403 | 403 | 403 | 403 | 404 | 404 | 403 | 403 |
| GET | `/api/v1/quotations/hr-people/` | 401 | 403 | 403 | 403 | 403 | 200 | 403 | 403 | 403 |
| GET | `/api/v1/reports/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/roles/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/search/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/users/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/users/` | 401 | 400 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/v1/users/1/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/v1/users/1/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/v1/users/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/users/1/activate/` | 401 | 400 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/users/1/deactivate/` | 401 | 400 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/v1/users/1/reset-password/` | 401 | 400 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
