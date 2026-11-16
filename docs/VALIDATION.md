# Validation evidence

Executed on 2026-11-16. [Full Linux CI evidence](https://github.com/jeelthacker1/FleetVerse/actions/runs/43801127525) passed all three jobs: backend, web and integration.

- Backend suite at the linked CI revision: 18 tests passed in 5.01 seconds, including deterministic continuation, reservations, edge swaps, battery, task transitions, API roles/CSRF, persistence, snapshots, concurrent idempotency and shared WebSocket state. An additional checkpoint/reset/deadline regression test was subsequently added; the expanded engine suite passed locally (14 tests).
- Stress test: 20 robots, 100 orders, 300 ticks; 36 completed deliveries, 2,611 traveled cells, zero collision violations. Engine time measured 1.595 seconds on Linux CI and 0.987 seconds in the final Windows engine run. This excludes database and network I/O.
- Backend Ruff lint: passed.
- Frontend Next.js 16.4.6 production build and strict TypeScript compilation: passed.
- npm dependency audit: zero known vulnerabilities at execution time.
- Docker Compose configuration validation: passed.
- Local Docker runtime: unavailable because this Windows machine has no WSL installation and Docker Desktop cannot start. Native API/worker browser tests used a temporary SQLite database and database-based WebSocket fallback: two workflow/role tests passed in 1.1 minutes; the separate visual check passed in 3.0 seconds.
- Full-stack Linux CI: `docker compose up --build -d --wait` succeeded; web, API, worker, PostgreSQL and Redis all became healthy. All three Playwright tests passed in 18.2 seconds against that stack.
- Browser coverage: login, create warehouse and run, create/generate orders, backend robot movement, completed delivery, two-session consistency, blockage, incident replay, computed experiment, CSV download, viewer restrictions, desktop/tablet layout. Real screenshots were captured and visually inspected.

## Commands actually executed

`pip install -r backend/requirements.txt`, maintained-package upgrades, `pip freeze` to create the final lock, `pytest -q -s -p no:cacheprovider`, `ruff check backend --no-cache`, `alembic upgrade head`, `python -m app.bootstrap`, `uvicorn app.main:app`, `python -m app.worker`, `npm install`, `npm audit`, `npm run build`, `npm run typecheck` (CI), `playwright install chromium`, `npm run test:e2e`, `docker compose config --quiet`, and the full Compose startup in Linux CI. GitHub repository visibility was queried and confirmed PUBLIC.

Windows also blocked Git and dependency writes under Documents. Source remains in the requested workspace; builds used a temporary frontend checkout and Python environment, and publication used a temporary Git checkout. No test credentials or temporary databases were committed.

One deprecation warning comes from Starlette's httpx-based TestClient; it does not fail tests. Test results are measured software behavior, not warehouse performance forecasts.
