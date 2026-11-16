# Setup and deployment

## Windows / Docker Desktop

1. Install Docker Desktop and enable a supported WSL 2 or Hyper-V Linux-container backend.
2. Start Docker Desktop and verify `docker info` succeeds.
3. Run `docker compose up --build` from the repository root.
4. Wait for API migrations and health checks, then open http://localhost:3000.

`docker compose down` stops services and preserves data. Deleting Compose volumes removes saved runs and users; export results before deliberately doing that.

## Native development fallback

For a single local developer, SQLite supports the same API and worker code. It is a fallback, not the recommended concurrent deployment database. Missing Redis uses database-backed WebSocket resynchronization instead of Pub/Sub.

In a Python 3.13 virtual environment, install `backend/requirements.lock`. In each backend terminal, set these variables (use an absolute writable file path):

```powershell
$env:DATABASE_URL='sqlite:///C:/path/to/fleetverse-local.db'
$env:DEMO_MODE='true'
$env:COOKIE_SECURE='false'
$env:ALLOWED_ORIGINS='http://localhost:3000'
cd backend
alembic upgrade head
python -m app.bootstrap
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal with the same database URL and activated environment: `python -m app.worker`. In `web`, run `npm ci` and `npm run dev`. Use `localhost` consistently; mixing `127.0.0.1` and `localhost` changes cookie origins.

If Windows security blocks dependency writes inside Documents, use a temporary development checkout and virtual environment. Do not disable endpoint protection.

## Production configuration

This repository does not claim a production deployment. Use a fresh database with `DEMO_MODE=false`, a unique `ADMIN_PASSWORD` of at least 12 characters, and a strong `POSTGRES_PASSWORD`. `COOKIE_SECURE=true` requires HTTPS. Set an exact `ALLOWED_ORIGINS` list and the public `NEXT_PUBLIC_API_URL` at frontend build time. Do not seed demo users in a production database; changing the environment does not delete previously seeded accounts.

Terminate TLS at a reverse proxy, keep PostgreSQL/Redis private, back up PostgreSQL and enforce network-level access controls. Run exactly one simulation worker; experiments currently share that worker. Use a shared external rate limiter if scaling the API to multiple processes. Add monitoring for heartbeat age, worker errors, storage growth and latency. Apply migrations before switching application versions.

Passwords and session tokens are not stored in source. The local database password and demo credentials are public development fixtures, never production credentials.
