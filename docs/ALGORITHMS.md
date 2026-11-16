# Algorithms and semantics

## Clock and state

One simulation tick is one simulated second. At 1× the worker requests a tick every 250 ms (four simulated seconds per wall-clock second); the speed selector scales this pacing. Slow persistence or experiments may reduce wall-clock throughput without changing tick semantics. The engine itself reads no wall clock.

Each generated order uses an independent PRNG initialized from the run seed and order index. Layout, fleet size, policy, seed and ordered command inputs define a reproducible run. Serialized state includes every counter needed to continue deterministically. Wall-clock event timestamps are metadata, not algorithm inputs.

## A* and reservations

The A* search key is `(cell, relative_tick)` with Manhattan heuristic and unit movement/wait cost. One-way lanes constrain outgoing edges. Racks, restricted zones and injected blocks are impassable. The search horizon is 80 ticks during operations; layout reachability checks use the grid area.

Coordination uses a conservative rolling one-tick reservation window. All robots initially reserve their current cell for the next tick. In rotating robot order, each planner removes its own reservation, searches, and commits its next cell and directed edge. Entering another robot's not-yet-vacated cell and traversing a reverse reserved edge are disallowed. Routes beyond the next committed step are advisory and replanned on subsequent ticks. This intentionally trades throughput for simple, auditable safety. It is not globally optimal multi-agent pathfinding.

After 12 consecutive waits a robot attempts a legal, unreserved neighboring escape cell while retaining its mission destination. Planning priority rotates each tick. This detects and mitigates local contention but cannot guarantee liveness in every adversarial layout. It never teleports a robot. Final occupancy and edge-swap assertions abort a tick transaction if safety is violated.

## Dispatch

Baseline: FIFO orders, first available sufficiently charged robot.

Improved: orders sorted by descending urgency, then deadline, creation tick and ID. Eligible robots must be idle and exceed a conservative estimated battery threshold. Score = distance to pickup + pickup-to-drop-off Manhattan distance + 3 × nearby-robot congestion + 0.25 × completed workload. Lowest score wins with robot ID as tie-breaker. Availability and battery are hard constraints; urgency controls task order. Every candidate's actual score, distance, congestion, charge and eligibility is recorded.

Battery estimates are heuristics, not a guarantee against depletion during unusual detours. Moves consume 0.15 percentage points unloaded and 0.20 loaded; deadlock escapes consume 0.20. Chargers replenish two percentage points per tick. A zero-charge robot faults and requires explicit recovery. Recover models maintenance intervention restoring at least 30% charge, recorded as a command. Idle robots seek charging below 40% and leave a charger at 95%. Idle service-station occupants attempt to move aside.

Delivery checkpoints are traversed in configured order after loading. Pickup and drop-off have two-tick handling phases. Temporary station unavailability prevents unloading. Cancellation removes the simulated load and releases the robot; it models operator withdrawal, not a physical return-to-stock workflow.

## Metrics

- Completion duration = finished tick − created tick, for completed orders only.
- On-time percentage = completed orders meeting their deadlines / completed orders × 100.
- Throughput = completed orders / ticks since run creation or reset × 3600.
- Utilization = robot-ticks with an assigned task / total robot-ticks. It includes task-related waiting and faults; it is not productive-motion efficiency.
- Queue wait = assigned tick − created tick averaged over assigned orders.
- Congestion = accumulated planner waiting events, not a calibrated density measure.
- Battery consumption = sum of movement percentage points across all robots, not energy in kWh.
- Deadline misses include overdue unfinished orders, excluding cancelled orders.
- ETAs are path-length estimates with handling allowance; they are recalculated and are not guarantees.

## Counterfactual method

Each experiment forks the source layout and seed into fresh baseline and variant simulations, not a continuation from the source's mid-run state. Both receive identical seeded initial orders. Fleet placement changes when fleet size changes; initial positions derive from the same shuffled cells. Only selected factors differ. Additional-arrival settings deliberately change the variant workload and are disclosed in the result. Absolute delta is variant minus baseline; positive values are not automatically better. No unmeasured improvement percentage is shown.
