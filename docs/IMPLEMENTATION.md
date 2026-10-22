# Implementation plan

Build order is expressed as task slices. Each slice is one branch, one pull request, one gate run.

---

## 1. Architecture

```
browser ── /api/* ──▶ FastAPI (uvicorn :8000) ──▶ SQLite (WAL, single file)
        └─ SPA ─────▶ Vite dev :5173 (proxy /api → :8000)
```

- One backend process. No worker, no queue, no scheduler.
- Session cookie (`httponly`, `SameSite=Lax`) backed by a `session` table.
- Instants stored and transported as UTC ISO-8601. Local calendar dates derived with `zoneinfo` and
  stored where sorting/export needs them.

---

## 2. Schema

| Table | Columns (beyond `id`) | Constraints |
| --- | --- | --- |
| `tenant` | name, code, timezone (IANA) | `code` unique |
| `app_user` | name, email | |
| `membership` | user_id, tenant_id, role | PK(user_id, tenant_id); role in (admin, viewer) |
| `session` | token_hash, user_id, tenant_id, created_at, expires_at | PK(token_hash) |
| `course` | tenant_id, code, title | |
| `learner` | tenant_id, name, email (nullable) | |
| `enrollment` | tenant_id, course_id, learner_id, completed_at (nullable) | unique(course_id, learner_id) |
| `certificate` | tenant_id, course_id, learner_id, serial, issued_at, issued_local_date, issued_by, status, notification_status, notification_sent_at, revoked_at, revoked_by, revoke_reason | **unique(tenant_id, course_id, learner_id)**, unique(serial), index(tenant_id, issued_local_date) |
| `audit_entry` | tenant_id, certificate_id, action, actor_user_id, at, detail | index(certificate_id, at) |
| `idempotency_record` | tenant_id, key, course_id, status_code, response_json, created_at | PK(tenant_id, key) |
| `serial_counter` | tenant_id, year, next_value | PK(tenant_id, year) |

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

**Bulk issue** — one transaction: course lookup scoped to session tenant; replay of a known
`(tenant, key)` returns the stored response with `replay: true`; per enrollment → `skipped` (has a
certificate), `failed` (row-level error, batch continues), or `issued` (serial + certificate + audit +
pending notification); the idempotency record is written in the same transaction.

**Serials** — counter per (tenant, local year), block-allocated inside the transaction.

**Timezones** — `zoneinfo` with the tenant's IANA name. Never a stored offset, never
`toISOString().slice(0,10)` for user-facing dates.

**Export** — `StreamingResponse`, server cursor, filter in SQL, ordered by `issued_local_date, issued_at`;
count computed first for the row total; UTF-8 BOM.

**Audit** — one row per issuance and per revocation, actor + timestamp + human-readable detail, written
in the same transaction as the state change.

**Notification** — pending on issuance, dispatched after commit, `skipped` without an address, resendable.

---

## 5. Frontend

Routes `/login`, `/certificates`, `/certificates/:id`, `/issue`. Filters, sort and page live in the URL.
Data layer is a small `api/client.ts` plus `useAsync` — no state library. Types generated from
`/openapi.json` into a committed file, with a test that fails when it is stale. Every data view has
explicit loading, empty (no data / no match) and error states.

---

## 6. Verification

`check.sh` runs the gate: `python -m compileall` plus `pytest`. Eight API tests:

1. cross-tenant read and write → 404
2. same idempotency key twice → one set of certificates, replay flagged
3. different key on an issued course → everything skipped, nothing written
4. duplicate insert rejected by the unique index, not by check-then-insert
5. serial year uses the tenant-local year across a year boundary
6. rendering is zone-correct across a DST boundary (Sydney January vs July)
7. audit row per issuance and per revocation
8. export respects the filter and matches the list row count

Plus the Playwright walkthrough (D10), which is the demo.

---

## 7. Task slices

| Slice | Task | Done when |
| --- | --- | --- |
| backend | T-001 skeleton: app factory, DB layer, schema, seed, session auth, `/health` | login as two tenants works; seed re-runs safely |
| backend | T-002 list API + CSV export | filters, sort by local date, pagination; export matches count |
| backend | T-003 detail + revoke + audit | revoke needs a reason, writes audit, 404 across tenants |
| backend | T-004 bulk issue + serials + notification state | per-learner outcomes, replay, unique-index protection |
| frontend | T-005 shell + login + list | session gate, URL state, three states |
| frontend | T-006 detail + revoke + bulk issue screens | actions role-gated, progress, outcome table |
| e2e | T-007 Playwright demo walkthrough | labelled steps, assertions, screenshots, video |
| docs | T-008 run script + README + docker note | `python run.py` starts both from clean checkout |
