# Validation evidence

Validation in progress on 2026-11-16. This file is updated with final executed results before the completion report.

- Backend suite: 18 tests passed (14.04 seconds), including deterministic continuation, reservations, edge swaps, battery, task transitions, API roles/CSRF, persistence, snapshots, concurrent idempotency and shared WebSocket state.
- Stress test: 20 robots, 100 orders, 300 ticks; 36 completed deliveries, 2,611 traveled cells, zero collision violations. Engine time measured 1.949 seconds in the full suite. This excludes database and network I/O.
- Backend Ruff lint: passed.
- Frontend Next.js 16.4.6 production build and strict TypeScript compilation: passed.
- npm dependency audit: zero known vulnerabilities at execution time.
- Docker Compose configuration validation: passed.
- Local Docker runtime: blocked because this Windows machine has no WSL installation and Docker Desktop cannot start. Native API/worker browser tests use a temporary SQLite database and database-based WebSocket fallback. This does not substitute for PostgreSQL/Redis integration.
- Full-stack GitHub Actions and Playwright acceptance results: pending.

One deprecation warning comes from Starlette's httpx-based TestClient; it does not fail tests. Test results are measured software behavior, not warehouse performance forecasts.
