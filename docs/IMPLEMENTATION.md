# Implementation plan

---

## 1. Architecture

```
browser ── /api/* ──▶ FastAPI (uvicorn :8000)
                        │
                        ├─ data/control.db          tenants, users, memberships, sessions
                        └─ data/tenants/<code>.db   one file per tenant: courses, learners,
                                                    enrollments, certificates, audit, idempotency
        └─ SPA ─────▶ Vite dev :5173 (proxy /api → :8000)
```

- One backend process. No worker, no queue, no scheduler.
- Session cookie (`httponly`, `SameSite=Lax`) backed by the `session` table in the control database.
- Every request resolves `session → tenant → tenant database`, and every repository call receives that
  tenant database handle. There is no "default" database to fall back to.
- Instants stored and transported as UTC ISO-8601. Local calendar dates derived with `zoneinfo`.
- Both databases run in WAL mode with `foreign_keys=ON` and `busy_timeout`.

---

## 2. Schema

### Control database (`data/control.db`)

| Table | Columns (beyond `id`) | Constraints |
| --- | --- | --- |
| `tenant` | name, code, timezone (IANA), db_file | `code` unique |
| `app_user` | name, email | |
| `membership` | user_id, tenant_id, role | PK(user_id, tenant_id); role in (admin, viewer) |
| `session` | token_hash, user_id, tenant_id, created_at, expires_at | PK(token_hash) |

### Tenant database (`data/tenants/<code>.db`)

No `tenant_id` column exists in this database, by design (D11).

| Table | Columns (beyond `id`) | Constraints |
| --- | --- | --- |
| `course` | code, title | |
| `learner` | name, email (nullable) | |
| `enrollment` | course_id, learner_id, completed_at (nullable) | unique(course_id, learner_id) |
| `certificate` | course_id, learner_id, serial, issued_at, issued_local_date, issued_by, status, notification_status, notification_sent_at, revoked_at, revoked_by, revoke_reason | **unique(course_id, learner_id)**, unique(serial), index(issued_local_date) |
| `audit_entry` | certificate_id, action, actor_user_id, at, detail | index(certificate_id, at) |
| `idempotency_record` | key, course_id, status_code, response_json, created_at | PK(key) |
| `serial_counter` | year, next_value | PK(year) |

Cross-database references (`audit.actor_user_id` → control `app_user`) are soft: no foreign key is
possible across files, so the actor's display name is also written into the audit `detail`.

---

## 3. API

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/auth/tenants` | unauthenticated, login page |
| GET | `/api/auth/accounts?tenantId=` | unauthenticated, demo login list |
| POST | `/api/auth/login` | `{tenantId, userId}` → sets cookie |
| POST | `/api/auth/logout` | deletes session |
| GET | `/api/auth/me` | principal, role, tenant name, tenant timezone |
| GET | `/api/certificates` | `search, status, courseId, sort, dir, page, pageSize` |
| GET | `/api/certificates/{id}` | detail + audit entries |
| POST | `/api/certificates/bulk-issue` | `{courseId, idempotencyKey}` |
| POST | `/api/certificates/{id}/revoke` | `{reason}`, admin only |
| POST | `/api/certificates/{id}/notify` | resend notification, admin only |
| GET | `/api/certificates/export.csv` | same filters as list, streaming |
| GET | `/api/courses` | bulk-issue picker |
| GET | `/api/courses/{id}/eligibility` | enrolled / eligible / already issued |
| GET | `/api/health` | liveness |

- List rows carry `issuedAt` (UTC) **and** `issuedLocalDate`, so the screen and the CSV cannot disagree.
- Errors: `{"error": {"code", "message", "details?"}}`; 401 unauthenticated, 404 not found or other
  tenant, 409 conflict, 422 validation, 403 only for role.

---

## 4. Behaviour that must be right

**Tenant routing** — a request without a resolvable tenant (no session, or a session whose tenant row is
gone) is 401. The tenant database handle is opened per request from `tenant.db_file`; a path outside the
tenants directory is refused.

**Bulk issue** — one transaction in the tenant database: course lookup; replay of a known key returns the
stored response with `replay: true`; per enrollment → `skipped` (has a certificate), `failed` (row-level
error, batch continues), or `issued` (serial + certificate + audit + pending notification); idempotency
record written in the same transaction; cap 1,000.

**Serials** — counter per local year inside the tenant database, block-allocated in the transaction.

**Timezones** — `zoneinfo` with the tenant's IANA zone from the control database. Never a stored offset.

**Export** — `StreamingResponse`, server cursor, filter in SQL, ordered by `issued_local_date, issued_at`;
count first for the row total; UTF-8 BOM.

**Audit** — one row per issuance and per revocation, actor + timestamp + human-readable detail, in the
same transaction as the state change. Append-only; no delete path exists.

**Notification** — pending on issuance, dispatched after commit, `skipped` without an address, resendable.

---

## 5. Frontend

Routes `/login`, `/certificates`, `/certificates/:id`, `/issue`. Filters, sort and page live in the URL.
Data layer is a small `api/client.ts` plus `useAsync` — no state library. Types generated from
`/openapi.json` into a committed file, with a test that fails when it is stale. Every data view has
explicit loading, empty (no data / no match) and error states.

---

## 6. Verification

`check.sh` runs `python -m compileall` and `pytest`. Eight API behaviours:

1. cross-tenant read and write → 404
2. same idempotency key twice → one set of certificates, replay flagged
3. different key on an issued course → everything skipped, nothing written
4. duplicate insert rejected by the unique index, not by check-then-insert
5. serial year uses the tenant-local year across a year boundary
6. rendering is zone-correct across a DST boundary (Sydney January vs July)
7. audit row per issuance and per revocation
8. export respects the filter and matches the list row count

Plus a test that two tenant databases are genuinely separate files, and that a certificate id from one
tenant's database is 404 in the other.

Plus the Playwright walkthrough (D10), which is the demo.

---

## 7. Task

One task covers the whole build: backend, frontend, demo walkthrough, packaging. Its detail lives in
Gitea (`task show`), and the acceptance criteria are the ones in §6 plus a working `python run.py`.
