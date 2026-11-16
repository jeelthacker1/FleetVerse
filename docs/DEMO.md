# Demo and screenshots

## One minute

0–10s: Open mission control, create a seeded 20-robot simulation. Explain that the worker owns all movement.

10–25s: Generate 20 orders and start. Select a robot; show its task, route and battery. Increase speed and watch an order complete.

25–40s: Pause, click an empty aisle cell and inject a block. Resume; show route changes or safe waiting and the incident entry.

40–50s: Open Incident time machine. Scrub before and after the block; inspect a dispatch decision's candidate scores.

50–60s: Show a previously completed what-if comparison, explain absolute deltas and export CSV. Do not pretend a precomputed result just ran live.

## Three minutes

0–30s: Explain the warehouse problem and architecture. Show the layout designer and three seeded congestion patterns.

30–80s: Create a run with seed 42 and 20 robots. Generate orders, start, inspect robot telemetry and order transitions. Explain next-tick reservations and edge-swap prevention.

80–120s: Inject a fault and blockage; show consequences, recover the robot, inspect the incident ledger and recorded state comparison.

120–165s: Run an experiment with five additional robots or baseline scheduling. Show the completion chart, queue wait, congestion, battery consumption and deadline misses. Discuss the finite horizon and incomplete orders.

165–180s: Export results. Show the test evidence and limitations. State explicitly that this is a simulated industrial-style system, not a safety-certified physical-robot controller.

## Screenshot guide

Capture the actual running application at 1440×1000 or wider: landing page; mission control with completed orders; selected robot telemetry; editor with a custom lane; replay at an incident tick; expanded dispatch scores; completed experiment chart and comparison. Use browser screenshots, not fabricated charts. Include the SIMULATED label and enough context to identify the selected run/tick. Never include production credentials or session cookies.
