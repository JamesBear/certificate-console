# certificate-console

Internal admin console for a multi-tenant corporate training platform. Tenant admins review
completed courses and issue, revoke and export completion certificates.

**Status: plan stage.** This repository intentionally contains no application code yet — only the
decision record, the implementation plan, and the project metadata that taskhub needs. Work is
tracked as tasks in Gitea and lands through one branch per task.

- Decisions and their rationale: [`docs/PLAN.md`](docs/PLAN.md)
- Architecture, schema, API and milestones: [`docs/IMPLEMENTATION.md`](docs/IMPLEMENTATION.md)

## Planned stack

| Layer | Choice |
| --- | --- |
| Backend | Python 3.12, FastAPI, SQLite (WAL) |
| Frontend | React 19 + TypeScript + Vite |
| Run | `python run.py` — one script starts API and web |
| Tests | pytest (API behaviour) + Playwright (scripted demo) |

## Collaboration

Tasks live in Gitea and are managed with the `task` CLI (`task doctor`, `task list --for-me`). One
task = one branch = one pull request. `check.sh` is the gate; `task gate` only looks at its exit code.
