# Database and retention

SQLAlchemy models use foreign keys and unique constraints; PostgreSQL is the supported deployment database. JSON columns preserve typed domain snapshots while relational IDs and indexes support associations and lookup.

| Table | Relationships / role |
| --- | --- |
| users | Unique username; Argon2 hash; ADMIN/OPERATOR/VIEWER |
| sessions | User FK; SHA-256 of opaque cookie; CSRF value; indexed expiry |
| warehouses | Facility identity |
| layouts | Warehouse FK; immutable saved configuration |
| map_cells | Layout FK; unique layout/x/y; cell type |
| simulation_runs | Layout FK; authoritative state; monotonic revision |
| commands | Run + user FKs; unique run/idempotency key; durable status |
| robots | Run FK; unique run/code; current telemetry projection |
| robot_telemetry | Robot FK; indexed tick; sampled state |
| orders | Run FK; unique run/code; full transition history |
| missions | Unique order FK; robot FK; execution state |
| simulation_events | Run FK; unique run/sequence; tick and wall-clock timestamp |
| simulation_snapshots | Run FK; unique run/revision; indexed tick; exact state |
| incidents | Event + run FKs |
| experiments | Source run FK; inputs; pending/completed/failed status |
| experiment_results | Unique experiment FK; computed comparison |
| audit_logs | User FK; action, inputs and wall-clock timestamp |

Commands are applied atomically with run state, snapshots, events and relational projections. Redis publication happens after commit. A crash before commit rolls back; a crash after commit but before publish is repaired by WebSocket database resynchronization. PostgreSQL row locks prevent simultaneous writes to a run. Only one worker is supported because independent worker pacing would otherwise advance ticks too quickly.

The initial migration creates this schema. Future schema changes must add explicit Alembic revisions; do not edit an already-deployed initial migration.

## Storage policy

Current implementation stores an exact snapshot for every changed revision (including command-only updates), events permanently, and robot telemetry every ten ticks. The browser receives the most recent 300 events; the history endpoint returns up to 5,000 events per page with an `after` cursor. Runs do not expire automatically. Snapshot growth is significant: JSON state includes the order list and recent events.

For extended deployments, export completed experiments, back up the database, and establish a retention job before continuous operation. Recommended policy: 30 days of detailed snapshots/telemetry and 90 days of events, retaining experiment reports longer. The current application deliberately does not silently delete historical evidence. Partitioning, compression, delta snapshots and a retention admin tool remain scaling work. For finite demonstration runs, per-tick snapshots make historical inspection exact and easy to audit.

Reset clears the live robot/order state but preserves monotonic history ticks and order IDs. Previous snapshots and events remain accessible. Old relational order records are historical evidence; live API lists come from the authoritative current run state.
