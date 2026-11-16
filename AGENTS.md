# FleetVerse engineering rules

- The simulation worker is the only writer of authoritative run state. API commands are durable and idempotent.
- Keep the simulation pure Python and deterministic; no wall-clock or unseeded randomness in tick logic.
- Never synthesize telemetry in the browser. Label all runs simulated.
- Validate commands before mutation; enforce roles and CSRF on the server.
- Test safety invariants, replay, API authorization and end-to-end operations. Report only executed checks.
- Definition of done: executable implementation, passing relevant checks, documented limitations, no secrets committed, public GitHub upload verified.
- Optional 3D and LLM features follow a working 2D application.
