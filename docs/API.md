# API guide

Interactive OpenAPI: http://localhost:8000/docs. Base path: `/api/v1`.

Authenticate with `POST /auth/login` and JSON `username`, `password`. The response supplies user role and CSRF token; the server sets an HTTP-only session cookie. Send that cookie on subsequent requests. Mutating calls require an allowed `Origin` and `X-CSRF-Token`. Command submission additionally requires an `Idempotency-Key` of 8–80 characters. Reuse the same key only when retrying the exact payload.

| Route | Method / purpose | Role |
| --- | --- | --- |
| /auth/me, /auth/logout | GET identity, POST revoke session | All |
| /users | GET list, POST create user | Admin |
| /warehouses | GET list, POST create | View / admin |
| /layouts | GET list, POST validated immutable revision | View / admin |
| /simulations | GET list, POST create seeded run | View / admin |
| /simulations/{id} | GET authoritative state + metrics + revision | All |
| /simulations/{id}/commands | POST durable command | Operator; reset admin |
| /commands/{id} | GET pending/applied/rejected acknowledgment | All |
| /simulations/{id}/robots | GET live robot states | All |
| /simulations/{id}/orders | GET live order states and history | All |
| /simulations/{id}/metrics | GET computed metrics | All |
| /simulations/{id}/events | GET events; kind and after filters | All |
| /simulations/{id}/incidents | GET incident/deadlock history | All |
| /simulations/{id}/history/{tick} | GET latest recorded revision at/before tick | All |
| /experiments | POST paired scenario request | Operator |
| /experiments/{id} | GET status/result | All |
| /reports/experiments/{id}?format=csv | GET CSV (or json) download | All |
| /audit | GET recent audit actions | Admin |
| /ws/{run_id} | Authenticated WebSocket state + heartbeat | All |

Commands use `{ "kind": "block", "data": { "cell": [2, 2] } }`. Supported kinds: start, resume, pause, stop, reset, speed, generate, order, assign, cancel, breakdown, recover, low_battery, block, unblock, charger_failure, charger_restore, station_failure, station_restore, urgent, surge.

HTTP 202 means queued, not success. Poll `/commands/{id}` to observe application or rejection. The worker revalidates commands against current state; a command that was valid at submission may be rejected if another command changed the relevant state.

WebSocket clients send the session cookie and an allowed Origin. Full authoritative payloads contain run ID, revision, state and metrics. Heartbeat objects contain no state. Reconnect with exponential backoff and accept the latest full snapshot. Sessions are rechecked while connected so logout/expiry ends authorization. Historical payloads carry `historical: true` and never mutate the live run.
