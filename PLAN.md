# FleetVerse delivery plan

1. Foundation: versioned API, relational persistence, migrations, sessions, roles, Docker services.
2. Engine: deterministic ticks, task lifecycle, charging, A*, time reservations, collision guards, dispatch explanations.
3. Operations: live server-driven dashboard, layout editing, task management, failure commands.
4. History: snapshots and events, historical inspection and replay.
5. Laboratory: seeded baseline/counterfactual runs, computed comparisons and CSV/JSON exports.
6. Verification: unit/integration/E2E tests, 20+ robot benchmark, strict frontend build, CI, documentation.
7. Publication: scan tracked files, commit and push to public GitHub; verify repository visibility.

Acceptance: login → seeded warehouse → moving robots → completed order → blocked route → recorded incident → replay → experiment → export. Two clients share worker state. No simulated results are presented as real-world measurements.

Progress and exact verification results are recorded in docs/VALIDATION.md. Optional 3D and LLM summarization are deferred by design.
