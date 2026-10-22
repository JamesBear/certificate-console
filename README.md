# Certificate Console

Internal admin console for a multi-tenant corporate training platform. Tenant admins review completed
courses, issue completion certificates in bulk, revoke them, and export the result.

**One database per tenant.** The control database holds tenants, users and sessions; each tenant's
courses, learners, enrollments, certificates and audit trail live in their own SQLite file, so a
forgotten `WHERE` clause cannot reach another tenant's data.

---

## Quick start

Prerequisites: **Python 3.11+** and **Node 20+** (with `pnpm` or `npm`).

```bash
python run.py
```

First run creates `.venv`, installs both dependency sets, then starts:

- API on <http://127.0.0.1:8000> (uvicorn, auto-reload)
- Web app on <http://127.0.0.1:5173> (Vite, proxying `/api`)

`Ctrl+C` stops both. `python run.py --prod` builds the SPA and serves everything from FastAPI on one
port. The seed runs on first start; to reset:

```bash
python -m app.seed data
```

## Demo accounts

Sign in by picking a tenant, then an account. There is no password — this is a demo console.

| Tenant | Timezone | Accounts |
| --- | --- | --- |
| Acme Field Services | `Australia/Sydney` | Dana Whitfield (admin), Alex Chen (viewer) |
| Northwind Logistics | `Australia/Perth` | Marcus Bell (admin) |
| Meridian Health Group | `Asia/Singapore` | Wei Ling Tan (admin) |

The tenant is bound to the session. There is no tenant switcher inside the console; sign out to change
tenants.

## Demo path

1. Sign in as **Acme / Dana Whitfield** — the list shows certificates dated in Sydney time.
2. Search by learner name, then by a serial fragment; sort columns; page forward.
3. Open a certificate — the issued date shows `AEDT · UTC+11` (January) or `AEST · UTC+10` (July),
   alongside the raw UTC value.
4. **Revoke** it with a reason; the status flips and the audit trail gains a second entry.
5. **Bulk issue** a course — eligibility counts, per-learner issued/skipped outcomes, then
   **Simulate network retry**: the replay banner appears and nothing is issued twice.
6. **Export CSV** — the file honours the active filter and its row count matches the list.
7. Sign out, sign in as **Northwind** — different certificates, `Australia/Perth`, no crossover.

## Tests

```bash
python -m pytest tests        # 49 API checks (isolation, idempotency, DST, export parity)
E2E_HEADED=1 python -m pytest e2e -s   # labelled walkthrough with screenshots + video
python -m pytest e2e          # headless, CI
```

`e2e` needs `frontend/dist` (`cd frontend && npm run build`). It seeds a throwaway database, starts
uvicorn on an ephemeral port, and injects an on-screen label for every step before asserting it.
Artefacts land in `e2e/artifacts/`.

`sh check.sh` is the gate: compile, API tests, frontend typecheck.

## Layout

```
app/
  main.py        application factory, SPA mount
  db.py          control database + one database per tenant
  schema_control.sql / schema_tenant.sql
  seed.py        deterministic demo data
  auth.py        login, logout, session, tenant resolution
  timezones.py   IANA-zone rendering, local dates, zone labels
  certs/         repository, service (issuance, revocation), router
frontend/        React + TypeScript + Vite
e2e/             Playwright walkthrough
docs/PLAN.md     decision record (D1–D11)
docs/IMPLEMENTATION.md  architecture, schema, API
run.py           single entrypoint
```

## Known limitations

- No passwords and no SSO: the login page is a demo affordance.
- The notifier is a stub — it records delivery instead of sending email, and revocation does not notify.
- Bulk issue is synchronous with a 1,000-learner cap per request. Above that the answer is a job, not a
  bigger transaction.
- Revocation is terminal; there is no reinstate or re-issue (a retake cannot be certified separately).
- CSV export streams, but the list endpoint uses offset pagination, which degrades on very deep pages.
- Docker is not shipped yet; `python run.py` is the supported path.
