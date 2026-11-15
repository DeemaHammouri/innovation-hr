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
| Quotations: sign (approve or return) | yes | no | no | no | no | no | no | no |
| Quotations: send, record outcome, follow up | no | no | yes | own leads | no | no | no | no |
| Contracts: see | all | no | all | own leads | all | all | handed over only | handed over only |
| Contracts: request | no | no | yes | own leads | no | no | no | no |
| Contracts: draft, upload, hand over | no | no | no | no | yes | yes | no | no |
| Contracts: log meeting | no | no | yes | own leads | no | no | no | no |
| Contracts: sign (approve or return) | yes | no | no | no | no | no | no | no |
| Clients and Operation: see | all | no | own deals, read-only | own deals, read-only | no | no | all | all |
| Operation: checklist, tasks, QA meetings | no | no | no | no | no | no | write | write (tasks assigned to them; head customises) |
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
| GET | `/api/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/activity/` | 401 | 400 | 400 | 400 | 400 | 400 | 400 | 400 | 400 |
| POST | `/api/auth/change-password/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/auth/login/` | 400 | 400 | 400 | 400 | 400 | 400 | 400 | 400 | 400 |
| POST | `/api/auth/logout/` | 401 | 204 | 204 | 204 | 204 | 204 | 204 | 204 | 204 |
| GET | `/api/auth/me/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| PATCH | `/api/auth/me/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| POST | `/api/auth/refresh/` | 400 | 400 | 400 | 400 | 400 | 400 | 400 | 400 | 400 |
| DELETE | `/api/clients/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 405 | 403 |
| GET | `/api/clients/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 200 | 403 |
| PATCH | `/api/clients/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 405 | 403 |
| POST | `/api/clients/` | 401 | 400 | 403 | 403 | 403 | 403 | 403 | 400 | 403 |
| PUT | `/api/clients/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 405 | 403 |
| DELETE | `/api/clients/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 405 | 403 |
| GET | `/api/clients/1/` | 401 | 404 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| PATCH | `/api/clients/1/` | 401 | 404 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| POST | `/api/clients/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 405 | 403 |
| PUT | `/api/clients/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 405 | 403 |
| GET | `/api/comments/` | 401 | 400 | 400 | 400 | 400 | 400 | 400 | 400 | 400 |
| POST | `/api/comments/` | 401 | 400 | 400 | 400 | 400 | 400 | 400 | 400 | 400 |
| DELETE | `/api/contracts/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| GET | `/api/contracts/` | 401 | 200 | 403 | 200 | 200 | 200 | 200 | 200 | 200 |
| PATCH | `/api/contracts/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| POST | `/api/contracts/` | 401 | 404 | 403 | 404 | 404 | 404 | 404 | 404 | 404 |
| PUT | `/api/contracts/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| DELETE | `/api/contracts/1/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| GET | `/api/contracts/1/` | 401 | 404 | 403 | 404 | 404 | 404 | 404 | 404 | 404 |
| PATCH | `/api/contracts/1/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| POST | `/api/contracts/1/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| PUT | `/api/contracts/1/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| DELETE | `/api/contracts/1/approve/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| GET | `/api/contracts/1/approve/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| PATCH | `/api/contracts/1/approve/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| POST | `/api/contracts/1/approve/` | 401 | 404 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/contracts/1/approve/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| DELETE | `/api/contracts/1/cancel/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| GET | `/api/contracts/1/cancel/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| PATCH | `/api/contracts/1/cancel/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| POST | `/api/contracts/1/cancel/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/contracts/1/cancel/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| DELETE | `/api/contracts/1/handover/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| GET | `/api/contracts/1/handover/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| PATCH | `/api/contracts/1/handover/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| POST | `/api/contracts/1/handover/` | 401 | 403 | 403 | 403 | 403 | 404 | 404 | 403 | 403 |
| PUT | `/api/contracts/1/handover/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| DELETE | `/api/contracts/1/meeting/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| GET | `/api/contracts/1/meeting/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| PATCH | `/api/contracts/1/meeting/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| POST | `/api/contracts/1/meeting/` | 401 | 404 | 403 | 404 | 404 | 404 | 404 | 404 | 404 |
| PUT | `/api/contracts/1/meeting/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| DELETE | `/api/contracts/1/return/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| GET | `/api/contracts/1/return/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| PATCH | `/api/contracts/1/return/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| POST | `/api/contracts/1/return/` | 401 | 404 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/contracts/1/return/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| DELETE | `/api/contracts/1/send/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| GET | `/api/contracts/1/send/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| PATCH | `/api/contracts/1/send/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| POST | `/api/contracts/1/send/` | 401 | 403 | 403 | 403 | 403 | 404 | 404 | 403 | 403 |
| PUT | `/api/contracts/1/send/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| DELETE | `/api/contracts/1/start/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| GET | `/api/contracts/1/start/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| PATCH | `/api/contracts/1/start/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| POST | `/api/contracts/1/start/` | 401 | 403 | 403 | 403 | 403 | 404 | 404 | 403 | 403 |
| PUT | `/api/contracts/1/start/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| DELETE | `/api/contracts/1/submit/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| GET | `/api/contracts/1/submit/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| PATCH | `/api/contracts/1/submit/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| POST | `/api/contracts/1/submit/` | 401 | 404 | 403 | 404 | 404 | 404 | 404 | 404 | 404 |
| PUT | `/api/contracts/1/submit/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 405 | 405 |
| GET | `/api/dashboard/summary/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| DELETE | `/api/departments/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/departments/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/departments/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/departments/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/departments/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/files/` | 401 | 400 | 400 | 400 | 400 | 400 | 400 | 400 | 400 |
| POST | `/api/files/` | 401 | 415 | 415 | 415 | 415 | 415 | 415 | 415 | 415 |
| GET | `/api/health/` | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/hr/attendance/` | 401 | 200 | 403 | 403 | 403 | 200 | 200 | 403 | 403 |
| GET | `/api/hr/attendance/export/` | 401 | 200 | 403 | 403 | 403 | 200 | 200 | 403 | 403 |
| GET | `/api/hr/attendance/mine/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/hr/attendance/mine/export/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/hr/leave-types/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| POST | `/api/hr/leave-types/` | 401 | 403 | 403 | 403 | 403 | 400 | 403 | 403 | 403 |
| PATCH | `/api/hr/leave-types/1/` | 401 | 403 | 403 | 403 | 403 | 200 | 403 | 403 | 403 |
| GET | `/api/hr/leave/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| POST | `/api/hr/leave/` | 401 | 403 | 400 | 400 | 400 | 400 | 400 | 400 | 400 |
| GET | `/api/hr/leave/balance/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/hr/leave/calendar/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| PATCH | `/api/hr/payroll/entries/1/` | 401 | 403 | 403 | 403 | 403 | 404 | 403 | 403 | 403 |
| GET | `/api/hr/payroll/runs/` | 401 | 200 | 403 | 403 | 403 | 200 | 403 | 403 | 403 |
| POST | `/api/hr/payroll/runs/` | 401 | 403 | 403 | 403 | 403 | 400 | 403 | 403 | 403 |
| GET | `/api/hr/payroll/runs/1/` | 401 | 404 | 403 | 403 | 403 | 404 | 403 | 403 | 403 |
| POST | `/api/hr/payroll/runs/1/approve/` | 401 | 404 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/hr/payroll/runs/1/export/` | 401 | 404 | 403 | 403 | 403 | 404 | 403 | 403 | 403 |
| POST | `/api/hr/payroll/runs/1/pay/` | 401 | 403 | 403 | 403 | 403 | 404 | 403 | 403 | 403 |
| POST | `/api/hr/payroll/runs/1/refresh/` | 401 | 403 | 403 | 403 | 403 | 404 | 403 | 403 | 403 |
| POST | `/api/hr/payroll/runs/1/reopen/` | 401 | 404 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/hr/payslips/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/hr/people/` | 401 | 200 | 403 | 403 | 403 | 200 | 200 | 403 | 403 |
| GET | `/api/hr/salaries/` | 401 | 200 | 403 | 403 | 403 | 200 | 403 | 403 | 403 |
| PUT | `/api/hr/salaries/1/` | 401 | 403 | 403 | 403 | 403 | 400 | 403 | 403 | 403 |
| DELETE | `/api/import-batches/` | 401 | 405 | 405 | 405 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/import-batches/` | 401 | 200 | 200 | 200 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/import-batches/` | 401 | 405 | 405 | 405 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/import-batches/` | 401 | 405 | 405 | 405 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/import-batches/` | 401 | 405 | 405 | 405 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/import-batches/1/` | 401 | 405 | 405 | 405 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/import-batches/1/` | 401 | 404 | 404 | 404 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/import-batches/1/` | 401 | 405 | 405 | 405 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/import-batches/1/` | 401 | 405 | 405 | 405 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/import-batches/1/` | 401 | 405 | 405 | 405 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/import-batches/1/undo/` | 401 | 405 | 405 | 405 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/import-batches/1/undo/` | 401 | 405 | 405 | 405 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/import-batches/1/undo/` | 401 | 405 | 405 | 405 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/import-batches/1/undo/` | 401 | 404 | 404 | 404 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/import-batches/1/undo/` | 401 | 405 | 405 | 405 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/leads/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| GET | `/api/leads/` | 401 | 200 | 200 | 200 | 200 | 403 | 403 | 403 | 403 |
| PATCH | `/api/leads/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| POST | `/api/leads/` | 401 | 403 | 400 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/leads/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| DELETE | `/api/leads/1/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| GET | `/api/leads/1/` | 401 | 404 | 404 | 404 | 404 | 403 | 403 | 403 | 403 |
| PATCH | `/api/leads/1/` | 401 | 404 | 404 | 404 | 404 | 403 | 403 | 403 | 403 |
| POST | `/api/leads/1/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| PUT | `/api/leads/1/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| DELETE | `/api/leads/1/archive/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| GET | `/api/leads/1/archive/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| PATCH | `/api/leads/1/archive/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| POST | `/api/leads/1/archive/` | 401 | 404 | 404 | 404 | 404 | 403 | 403 | 403 | 403 |
| PUT | `/api/leads/1/archive/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| DELETE | `/api/leads/1/assign/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| GET | `/api/leads/1/assign/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| PATCH | `/api/leads/1/assign/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| POST | `/api/leads/1/assign/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/leads/1/assign/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| DELETE | `/api/leads/1/interactions/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| GET | `/api/leads/1/interactions/` | 401 | 404 | 404 | 404 | 404 | 403 | 403 | 403 | 403 |
| PATCH | `/api/leads/1/interactions/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| POST | `/api/leads/1/interactions/` | 401 | 404 | 404 | 404 | 404 | 403 | 403 | 403 | 403 |
| PUT | `/api/leads/1/interactions/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| DELETE | `/api/leads/1/outcome/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| GET | `/api/leads/1/outcome/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| PATCH | `/api/leads/1/outcome/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| POST | `/api/leads/1/outcome/` | 401 | 404 | 404 | 404 | 404 | 403 | 403 | 403 | 403 |
| PUT | `/api/leads/1/outcome/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| DELETE | `/api/leads/1/reopen/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| GET | `/api/leads/1/reopen/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| PATCH | `/api/leads/1/reopen/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| POST | `/api/leads/1/reopen/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/leads/1/reopen/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| DELETE | `/api/leads/1/restore/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| GET | `/api/leads/1/restore/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| PATCH | `/api/leads/1/restore/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| POST | `/api/leads/1/restore/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/leads/1/restore/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| DELETE | `/api/leads/1/skip-quotation/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| GET | `/api/leads/1/skip-quotation/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| PATCH | `/api/leads/1/skip-quotation/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| POST | `/api/leads/1/skip-quotation/` | 401 | 404 | 404 | 404 | 404 | 403 | 403 | 403 | 403 |
| PUT | `/api/leads/1/skip-quotation/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| DELETE | `/api/leads/assignees/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| GET | `/api/leads/assignees/` | 401 | 403 | 403 | 200 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/leads/assignees/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| POST | `/api/leads/assignees/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| PUT | `/api/leads/assignees/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| DELETE | `/api/leads/board/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| GET | `/api/leads/board/` | 401 | 200 | 200 | 200 | 200 | 403 | 403 | 403 | 403 |
| PATCH | `/api/leads/board/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| POST | `/api/leads/board/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| PUT | `/api/leads/board/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| DELETE | `/api/leads/import/confirm/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| GET | `/api/leads/import/confirm/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| PATCH | `/api/leads/import/confirm/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| POST | `/api/leads/import/confirm/` | 401 | 403 | 400 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/leads/import/confirm/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| DELETE | `/api/leads/import/preview/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| GET | `/api/leads/import/preview/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| PATCH | `/api/leads/import/preview/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| POST | `/api/leads/import/preview/` | 401 | 403 | 400 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/leads/import/preview/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| DELETE | `/api/leads/import/template/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| GET | `/api/leads/import/template/` | 401 | 403 | 200 | 403 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/leads/import/template/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| POST | `/api/leads/import/template/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| PUT | `/api/leads/import/template/` | 401 | 405 | 405 | 405 | 405 | 403 | 403 | 403 | 403 |
| GET | `/api/lookups/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| DELETE | `/api/lookups/checklist-template/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/lookups/checklist-template/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| PATCH | `/api/lookups/checklist-template/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/lookups/checklist-template/` | 401 | 400 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/lookups/checklist-template/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/lookups/checklist-template/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/lookups/checklist-template/1/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| PATCH | `/api/lookups/checklist-template/1/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/lookups/checklist-template/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/lookups/checklist-template/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/lookups/rejection-reasons/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/lookups/rejection-reasons/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| PATCH | `/api/lookups/rejection-reasons/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/lookups/rejection-reasons/` | 401 | 400 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/lookups/rejection-reasons/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/lookups/rejection-reasons/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/lookups/rejection-reasons/1/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| PATCH | `/api/lookups/rejection-reasons/1/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/lookups/rejection-reasons/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/lookups/rejection-reasons/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/lookups/services/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/lookups/services/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| PATCH | `/api/lookups/services/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/lookups/services/` | 401 | 400 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/lookups/services/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/lookups/services/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/lookups/services/1/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| PATCH | `/api/lookups/services/1/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/lookups/services/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/lookups/services/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/lookups/sla/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/lookups/sla/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| PATCH | `/api/lookups/sla/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/lookups/sla/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/lookups/sla/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/lookups/work-hours/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/lookups/work-hours/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| PATCH | `/api/lookups/work-hours/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/lookups/work-hours/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/lookups/work-hours/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/mentionable/` | 401 | 400 | 400 | 400 | 400 | 400 | 400 | 400 | 400 |
| GET | `/api/my-work/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/notifications/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| POST | `/api/notifications/read-all/` | 401 | 204 | 204 | 204 | 204 | 204 | 204 | 204 | 204 |
| GET | `/api/notifications/unread-count/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| DELETE | `/api/operations/assignees/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| GET | `/api/operations/assignees/` | 401 | 200 | 403 | 200 | 200 | 403 | 403 | 200 | 200 |
| PATCH | `/api/operations/assignees/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| POST | `/api/operations/assignees/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| PUT | `/api/operations/assignees/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| DELETE | `/api/operations/checklist/1/archive/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| GET | `/api/operations/checklist/1/archive/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| PATCH | `/api/operations/checklist/1/archive/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| POST | `/api/operations/checklist/1/archive/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| PUT | `/api/operations/checklist/1/archive/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| DELETE | `/api/operations/checklist/1/not-applicable/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| GET | `/api/operations/checklist/1/not-applicable/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| PATCH | `/api/operations/checklist/1/not-applicable/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| POST | `/api/operations/checklist/1/not-applicable/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 404 |
| PUT | `/api/operations/checklist/1/not-applicable/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| DELETE | `/api/operations/checklist/1/required/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| GET | `/api/operations/checklist/1/required/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| PATCH | `/api/operations/checklist/1/required/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| POST | `/api/operations/checklist/1/required/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| PUT | `/api/operations/checklist/1/required/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| DELETE | `/api/operations/checklist/1/reset/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| GET | `/api/operations/checklist/1/reset/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| PATCH | `/api/operations/checklist/1/reset/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| POST | `/api/operations/checklist/1/reset/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 404 |
| PUT | `/api/operations/checklist/1/reset/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| DELETE | `/api/operations/checklist/1/verify/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| GET | `/api/operations/checklist/1/verify/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| PATCH | `/api/operations/checklist/1/verify/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| POST | `/api/operations/checklist/1/verify/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 404 |
| PUT | `/api/operations/checklist/1/verify/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| DELETE | `/api/operations/clients/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| GET | `/api/operations/clients/` | 401 | 200 | 403 | 200 | 200 | 403 | 403 | 200 | 200 |
| PATCH | `/api/operations/clients/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| POST | `/api/operations/clients/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| PUT | `/api/operations/clients/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| DELETE | `/api/operations/clients/1/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| GET | `/api/operations/clients/1/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| PATCH | `/api/operations/clients/1/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| POST | `/api/operations/clients/1/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| PUT | `/api/operations/clients/1/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| DELETE | `/api/operations/clients/1/cadence/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| GET | `/api/operations/clients/1/cadence/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| PATCH | `/api/operations/clients/1/cadence/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| POST | `/api/operations/clients/1/cadence/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| PUT | `/api/operations/clients/1/cadence/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| DELETE | `/api/operations/clients/1/checklist/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| GET | `/api/operations/clients/1/checklist/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| PATCH | `/api/operations/clients/1/checklist/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| POST | `/api/operations/clients/1/checklist/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| PUT | `/api/operations/clients/1/checklist/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| DELETE | `/api/operations/meetings/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| GET | `/api/operations/meetings/` | 401 | 200 | 403 | 200 | 200 | 403 | 403 | 200 | 200 |
| PATCH | `/api/operations/meetings/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| POST | `/api/operations/meetings/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 404 |
| PUT | `/api/operations/meetings/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| DELETE | `/api/operations/recurring/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| GET | `/api/operations/recurring/` | 401 | 200 | 403 | 200 | 200 | 403 | 403 | 200 | 200 |
| PATCH | `/api/operations/recurring/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| POST | `/api/operations/recurring/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| PUT | `/api/operations/recurring/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| DELETE | `/api/operations/recurring/1/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| GET | `/api/operations/recurring/1/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| PATCH | `/api/operations/recurring/1/` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 404 | 403 |
| POST | `/api/operations/recurring/1/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| PUT | `/api/operations/recurring/1/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| DELETE | `/api/operations/tasks/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| GET | `/api/operations/tasks/` | 401 | 200 | 403 | 200 | 200 | 403 | 403 | 200 | 200 |
| PATCH | `/api/operations/tasks/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| POST | `/api/operations/tasks/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| PUT | `/api/operations/tasks/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| DELETE | `/api/operations/tasks/1/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| GET | `/api/operations/tasks/1/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| PATCH | `/api/operations/tasks/1/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| POST | `/api/operations/tasks/1/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| PUT | `/api/operations/tasks/1/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| DELETE | `/api/operations/tasks/1/complete/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| GET | `/api/operations/tasks/1/complete/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| PATCH | `/api/operations/tasks/1/complete/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| POST | `/api/operations/tasks/1/complete/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| PUT | `/api/operations/tasks/1/complete/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| DELETE | `/api/operations/tasks/1/skip/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| GET | `/api/operations/tasks/1/skip/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| PATCH | `/api/operations/tasks/1/skip/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| POST | `/api/operations/tasks/1/skip/` | 401 | 404 | 403 | 404 | 404 | 403 | 403 | 404 | 404 |
| PUT | `/api/operations/tasks/1/skip/` | 401 | 405 | 403 | 405 | 405 | 403 | 403 | 405 | 405 |
| DELETE | `/api/payments/clients/1/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/payments/clients/1/` | 401 | 404 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/payments/clients/1/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/payments/clients/1/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/payments/clients/1/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/payments/clients/1/export/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/payments/clients/1/export/` | 401 | 404 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/payments/clients/1/export/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/payments/clients/1/export/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/payments/clients/1/export/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/payments/clients/1/schedule/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/payments/clients/1/schedule/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/payments/clients/1/schedule/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/payments/clients/1/schedule/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/payments/clients/1/schedule/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/payments/instalments/1/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/payments/instalments/1/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/payments/instalments/1/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/payments/instalments/1/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/payments/instalments/1/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/payments/instalments/1/cancel/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/payments/instalments/1/cancel/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/payments/instalments/1/cancel/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/payments/instalments/1/cancel/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/payments/instalments/1/cancel/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/payments/instalments/1/payments/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/payments/instalments/1/payments/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/payments/instalments/1/payments/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/payments/instalments/1/payments/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/payments/instalments/1/payments/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/payments/overview/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/payments/overview/` | 401 | 200 | 403 | 200 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/payments/overview/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/payments/overview/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/payments/overview/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/payments/records/1/reverse/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/payments/records/1/reverse/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/payments/records/1/reverse/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/payments/records/1/reverse/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/payments/records/1/reverse/` | 401 | 405 | 403 | 405 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/quotations/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| GET | `/api/quotations/` | 401 | 200 | 403 | 200 | 200 | 200 | 200 | 403 | 403 |
| PATCH | `/api/quotations/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| POST | `/api/quotations/` | 401 | 404 | 403 | 404 | 404 | 404 | 404 | 403 | 403 |
| PUT | `/api/quotations/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| DELETE | `/api/quotations/1/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| GET | `/api/quotations/1/` | 401 | 404 | 403 | 404 | 404 | 404 | 404 | 403 | 403 |
| PATCH | `/api/quotations/1/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| POST | `/api/quotations/1/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| PUT | `/api/quotations/1/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| DELETE | `/api/quotations/1/cancel/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| GET | `/api/quotations/1/cancel/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| PATCH | `/api/quotations/1/cancel/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| POST | `/api/quotations/1/cancel/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/quotations/1/cancel/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| DELETE | `/api/quotations/1/draft/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| GET | `/api/quotations/1/draft/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| PATCH | `/api/quotations/1/draft/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| POST | `/api/quotations/1/draft/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| PUT | `/api/quotations/1/draft/` | 401 | 403 | 403 | 403 | 403 | 404 | 404 | 403 | 403 |
| DELETE | `/api/quotations/1/outcome/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| GET | `/api/quotations/1/outcome/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| PATCH | `/api/quotations/1/outcome/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| POST | `/api/quotations/1/outcome/` | 401 | 404 | 403 | 404 | 404 | 404 | 404 | 403 | 403 |
| PUT | `/api/quotations/1/outcome/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| DELETE | `/api/quotations/1/request-changes/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| GET | `/api/quotations/1/request-changes/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| PATCH | `/api/quotations/1/request-changes/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| POST | `/api/quotations/1/request-changes/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/quotations/1/request-changes/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| DELETE | `/api/quotations/1/send/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| GET | `/api/quotations/1/send/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| PATCH | `/api/quotations/1/send/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| POST | `/api/quotations/1/send/` | 401 | 404 | 403 | 404 | 404 | 404 | 404 | 403 | 403 |
| PUT | `/api/quotations/1/send/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| DELETE | `/api/quotations/1/sign/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| GET | `/api/quotations/1/sign/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| PATCH | `/api/quotations/1/sign/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| POST | `/api/quotations/1/sign/` | 401 | 403 | 403 | 404 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/quotations/1/sign/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| DELETE | `/api/quotations/1/start/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| GET | `/api/quotations/1/start/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| PATCH | `/api/quotations/1/start/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| POST | `/api/quotations/1/start/` | 401 | 403 | 403 | 403 | 403 | 404 | 404 | 403 | 403 |
| PUT | `/api/quotations/1/start/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| DELETE | `/api/quotations/1/submit/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| GET | `/api/quotations/1/submit/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| PATCH | `/api/quotations/1/submit/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| POST | `/api/quotations/1/submit/` | 401 | 403 | 403 | 403 | 403 | 404 | 404 | 403 | 403 |
| PUT | `/api/quotations/1/submit/` | 401 | 405 | 403 | 405 | 405 | 405 | 405 | 403 | 403 |
| GET | `/api/reports/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/search/` | 401 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| DELETE | `/api/users/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/users/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/users/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/users/` | 401 | 400 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/users/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/users/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/users/1/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/users/1/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/users/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/users/1/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/users/1/activate/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/users/1/activate/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/users/1/activate/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/users/1/activate/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/users/1/activate/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/users/1/deactivate/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/users/1/deactivate/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/users/1/deactivate/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/users/1/deactivate/` | 401 | 400 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/users/1/deactivate/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| DELETE | `/api/users/1/reset-password/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| GET | `/api/users/1/reset-password/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PATCH | `/api/users/1/reset-password/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| POST | `/api/users/1/reset-password/` | 401 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| PUT | `/api/users/1/reset-password/` | 401 | 405 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
