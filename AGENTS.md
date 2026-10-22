# AGENTS.md

Conventions for any agent working in this repository. Read `docs/PLAN.md` before changing behaviour —
several decisions are load-bearing and look arbitrary out of context.

## Non-negotiables

- **Tenant comes from the session, never from the client.** No endpoint accepts a tenant id. Every
  repository query takes a tenant context and fails without one. Cross-tenant reads return 404.
- **Timezones are IANA zone names**, resolved with `zoneinfo`. Never a stored UTC offset. Never
  `toISOString().slice(0, 10)` for a user-facing date.
- **Bulk issue is idempotent twice over**: the idempotency record (replay returns the original result)
  and the unique index on `(tenant_id, course_id, learner_id)` (a replay cannot insert a second row).
- **Issuance, audit and notification rows are written in one transaction.** Notification dispatch
  happens after commit, never inside it.
- **No worker, no queue.** Long operations are synchronous and bounded (D5).
- **Audit rows are append-only.** No update or delete path may exist.
- Serial numbers are never reused, and a revoked certificate keeps its serial and its slot.

## Working style

- One task, one branch, one pull request. Run `check.sh` before submitting.
- Tests target behaviour, not coverage: isolation, idempotency, DST/year boundaries, export parity.
- No new dependencies without a note in the task report. No ORM magic, no component library.
- Keep `check.sh` green and grow it as behaviour appears; it is the only thing the gate reads.

## Layout

```
app/            FastAPI application (routers, repository, services)
tests/          pytest suites
frontend/       React + TypeScript + Vite
e2e/            Playwright demo walkthrough
docs/           decision record and implementation plan
run.py          single entrypoint (added in T-008)
```
