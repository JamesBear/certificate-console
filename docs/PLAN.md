# Decision record

Each decision below was settled deliberately. Reopening one is allowed, but say which, and note the
consequence — several are load-bearing for the schema.

## D1 — System boundary: certificates only

Tenants, courses, learners and enrollments are **seeded data**, not managed here. The console owns:

- `certificate` (issued / revoked state machine)
- `audit_entry`
- idempotency records and serial counters

No CRUD screens for the seeded entities. No sync/ingest pipeline. Eligibility is **derived**, never
stored: a completed enrollment with no certificate row.

## D2 — Tenant admin only; tenant fixed per session

- One principal → one tenant per session. Tenant is resolved server-side; **no endpoint accepts a
  tenant id**.
- Login page: pick tenant, then pick an account. No password (deliberate, demo-level).
- Logout is the only way to change tenant. No tenant switcher inside the console.
- Roles: `admin` (issue, revoke) and `viewer` (read, export). Viewer hides actions in the UI.
- Session: httponly cookie backed by a `session` table in the control database.
- Cross-tenant resource access returns **404**, never 403.

## D3 — Certificate identity: one per (course, learner)

- Within a tenant's database: unique index on `(course_id, learner_id)`. A revoked certificate still
  occupies it.
- Revocation is **terminal**. No re-issue, no partial unique index, no `reissued_from`.
- Bulk eligibility: completed enrollment with **no certificate row, any status** — so retries cannot
  duplicate and a revocation cannot be silently undone by a batch retry.
- Accepted cost: a retake of the same course cannot be certified separately.

## D4 — Serial numbers

- Format `CERT-{TENANT_CODE}-{YYYY}-{NNNNNN}`, e.g. `CERT-ACM-2026-000123`. Human-readable.
- `YYYY` is the **tenant-local** year, from the same helper used for display.
- Allocation: counter row in the tenant's database, incremented inside the issuance transaction.
- Rollback consumes no number. Gaps only ever come from deletion.
- Global uniqueness across tenants is structural: each tenant has its own database, and the tenant code
  makes the serial unambiguous if databases are ever merged for reporting.
- Detail routes use an opaque internal id, not the serial.

## D5 — Long operations are synchronous and bounded

- Bulk issue is one transaction: select eligible, allocate serials, insert certificates + audit +
  notification rows. Cap per request (1,000). No worker, no queue, no polling endpoint.
- Progress in the UI is indeterminate; the submit button is disabled while in flight.
- CSV export streams with a read-only cursor. No materialisation, no temp files, no write transaction.
- SQLite has one writer **per database**; because each tenant has its own database, concurrent issuance
  across tenants does not contend. Within one tenant it serialises, which is acceptable.

## D6 — Stack

- Backend: Python 3.12 + FastAPI, SQLite in WAL mode, stdlib `sqlite3` with explicit SQL.
- Frontend: React 19 + TypeScript + Vite, plain CSS with design tokens, no component library.
- `python run.py` starts both; docker compose is deliberately deferred.

## D7 — Certificate display is live; the local date is a snapshot

- Detail, list and export join live `learner` / `course` rows: correcting a name propagates.
- The historical fact lives in the audit row written at issuance ("Issued to X for Y").
- `issued_local_date` (`YYYY-MM-DD`) **is stored** on the certificate, computed once at issuance with
  `zoneinfo`, because SQLite cannot convert an IANA zone in SQL and sorting/export must be by local
  calendar date. It is a snapshot: a later timezone change does not rewrite past certificates.

## D8 — Notification is a separate state, not part of issuance

- Two columns on `certificate`: `notification_status` in (`pending`, `sent`, `skipped`) and
  `notification_sent_at`.
- No channel column, no attempt counter, no last-error column.
- Written `pending` inside the issuance transaction; dispatched after commit by a stub `Notifier` that
  records success without sending anything. Learners without an email address become `skipped`.
- Revocation does not notify. Bulk issue never blocks on notification.
- An admin can resend from the certificate detail page; that sets `sent` and stamps the time.

## D9 — No expiry, no email requirement

Status is `valid | revoked`. There is no `expired` state and no `expires_at`; adding one would contradict
D3. Issuing does not require an email address. `failed` in bulk issue is reserved for genuine per-row
errors; a batch continues past them.

## D10 — The end-to-end test is also the demo

- Playwright for Python, run headed against freshly seeded databases and a built SPA on an ephemeral port.
- Each step is wrapped in a helper that injects an on-screen label and writes to the run log. The label is
  injected by the test, not built into the app.
- Every step is followed by a real assertion, so the demo cannot drift from the product.
- Artefacts: a screenshot per step, a video, and `steps.md` listing label, assertion and timing.

## D11 — One database per tenant

Complete data separation: **each tenant's data lives in its own SQLite file**, not in shared tables.

- Control database (`data/control.db`): `tenant`, `app_user`, `membership`, `session`. No domain data.
- Tenant database (`data/tenants/<tenant_code>.db`): `course`, `learner`, `enrollment`, `certificate`,
  `audit_entry`, `idempotency_record`, `serial_counter`. **No `tenant_id` column anywhere** — a tenant
  database holds exactly one tenant, so the column would be a lie that invites cross-tenant bugs.
- The session's tenant selects which file the request opens. A repository that has no tenant context
  raises rather than falling back to a default.
- Consequences we accept:
  - Leakage is structural, not filtered: a query cannot reach another tenant's rows even if a `WHERE`
    clause is forgotten.
  - Cross-tenant reporting would need an explicit fan-out across files; out of scope.
  - Provisioning a tenant means creating and migrating a file; seeding creates one per demo tenant.
  - Backups and restores are per tenant, which is what "complete separation" is for.
  - Per-tenant schema migrations: every tenant file carries its own `PRAGMA user_version`.
- Still required: the 404-on-other-tenant behaviour (an id from another tenant's file simply does not
  exist here), and the tenant code in serials, so a certificate dumped out of its database stays
  attributable.

## Open

- Whether a second notification channel will ever exist (would add `channel` and change the unique key).
- Whether viewer accounts are needed in practice, or whether one admin role suffices.
