# Scope and limitations

FleetVerse implements the required 2D operational workflow; it is not a controller for physical robots and is not safety certified.

- Conservative one-step coordination and local deadlock escape preserve safety but do not guarantee optimal throughput or liveness in every map.
- Robots have one-cell-per-tick speed and one-unit payload. Fleet size is configurable, but per-robot speed/capacity editing is not provided.
- Battery and ETA models are simplified. Manhattan-based dispatch scoring does not model exact detour energy.
- A blocked or failed robot may require operator recovery; no automatic tow/repair agent exists.
- Snapshots are exact full JSON state, not compressed event deltas. Large, indefinite runs need retention, partitioning and payload optimization.
- One worker advances all runs and executes experiments. Large experiments can temporarily delay live wall-clock updates while preserving deterministic tick results.
- Experiments restart from the saved layout and seed. They do not branch from an arbitrary historical tick.
- Session/login throttling is process-local. Multi-process production deployments need a shared limiter. Users can be created, but account editing/deactivation and password reset flows are not yet provided.
- Roles apply to the entire shared workspace; multi-tenant warehouse isolation is not implemented.
- UI history displays a bounded event window; API pagination is available for longer investigations.
- Optional 3D and LLM incident summarization are intentionally not included.

See VALIDATION.md for the exact checks executed and environment-specific verification gaps. No production hosting deployment is claimed by a public GitHub upload.
