"""Deterministic, single-owner warehouse simulation. One tick is one simulated second."""
from __future__ import annotations

import copy
import heapq
import random


def neighbors(layout, cell):
    x, y = cell
    lane = layout.get('lanes', {}).get(f'{x},{y}')
    directions = {'E': [(1, 0)], 'W': [(-1, 0)], 'N': [(0, -1)], 'S': [(0, 1)]}
    blocked = {tuple(p) for p in layout['blocked']}
    for dx, dy in directions.get(lane, [(1, 0), (0, 1), (-1, 0), (0, -1)]):
        p = (x + dx, y + dy)
        if 0 <= p[0] < layout['width'] and 0 <= p[1] < layout['height'] and p not in blocked:
            yield p


def distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def astar(layout, start, goal, cells=None, edges=None, horizon=80):
    """Space-time A*: reservations indexed by relative tick, with explicit wait edges."""
    start, goal = tuple(start), tuple(goal)
    cells, edges = cells or set(), edges or set()
    queue = [(distance(start, goal), 0, start)]
    parent = {(start, 0): None}
    while queue:
        _, t, pos = heapq.heappop(queue)
        if pos == goal:
            path = []
            key = (pos, t)
            while parent[key] is not None:
                path.append(list(key[0]))
                key = parent[key]
            return list(reversed(path))
        if t >= horizon:
            continue
        for nxt in [*neighbors(layout, pos), pos]:
            key = (nxt, t + 1)
            if key in parent or (nxt, t + 1) in cells or (nxt, pos, t + 1) in edges:
                continue
            parent[key] = (pos, t)
            heapq.heappush(queue, (t + 1 + distance(nxt, goal), t + 1, nxt))
    return None


def layouts():
    result = []
    for idx, name in enumerate(['Cross-dock / open lanes', 'Dense storage / narrow aisles', 'Loop / directional flow']):
        blocked = [[x, y] for x in range(4, 21, 4) for y in range(3, 13)
                   if y not in ([7, 8] if idx == 0 else [8])]
        result.append(dict(name=name, width=26, height=16, blocked=blocked,
                           pickup=[[1, 3], [1, 8], [1, 12]], dropoff=[[24, 3], [24, 8], [24, 12]],
                           chargers=[[x, 15] for x in range(2, 24, 3)], checkpoints=[],
                           restricted=[], lanes={f'{x},0': 'E' for x in range(25)} if idx == 2 else {}))
    return result


def validate_layout(layout):
    if not all(isinstance(layout.get(k), int) for k in ('width', 'height')):
        raise ValueError('Integer grid dimensions are required')
    for key in ('blocked', 'restricted', 'pickup', 'dropoff', 'chargers', 'checkpoints'):
        if not isinstance(layout.get(key, []), list):
            raise ValueError('Cell collections must be arrays')
        layout.setdefault(key, [])
    if not isinstance(layout.get('lanes', {}), dict):
        raise ValueError('Lanes must be an object')
    if not 8 <= layout['width'] <= 60 or not 8 <= layout['height'] <= 60:
        raise ValueError('Grid dimensions must be between 8 and 60')
    occupied = set()
    for kind in ('blocked', 'restricted', 'pickup', 'dropoff', 'chargers', 'checkpoints'):
        for p in layout.get(kind, []):
            if not isinstance(p, list) or len(p) != 2 or not all(isinstance(v, int) for v in p):
                raise ValueError('Cell coordinates must be integers')
            if not (0 <= p[0] < layout['width'] and 0 <= p[1] < layout['height']):
                raise ValueError('Cell outside grid')
            if tuple(p) in occupied:
                raise ValueError('Cell types must not overlap')
            occupied.add(tuple(p))
    if not all(layout.get(k) for k in ('pickup', 'dropoff', 'chargers')):
        raise ValueError('At least one pickup, dropoff and charger is required')
    for key, direction in layout.get('lanes', {}).items():
        try:
            x, y = map(int, key.split(','))
        except ValueError:
            raise ValueError('Invalid lane coordinate') from None
        if direction not in ('N', 'S', 'E', 'W') or not (0 <= x < layout['width'] and 0 <= y < layout['height']):
            raise ValueError('Invalid lane')
    grid = copy.deepcopy(layout)
    grid['blocked'] += layout.get('restricted', [])
    for a in layout['pickup']:
        for b in layout['dropoff'] + layout['chargers'] + layout['checkpoints']:
            if astar(grid, a, b, horizon=layout['width'] * layout['height']) is None:
                raise ValueError('Stations must be reachable from each pickup')
    return layout


def new_state(layout=None, fleet=20, seed=42, policy='improved'):
    layout = copy.deepcopy(layout or layouts()[0])
    validate_layout(layout)
    blocked = {tuple(p) for p in layout['blocked'] + layout.get('restricted', [])}
    free = [[x, y] for y in range(layout['height']) for x in range(layout['width']) if (x, y) not in blocked]
    if not 1 <= fleet <= min(80, len(free) - 10):
        raise ValueError('Fleet must be 1–80 with at least 10 spare cells')
    rng = random.Random(seed)
    rng.shuffle(free)
    robots = [dict(id=f'R{i + 1:02}', pos=free[i], destination=None, route=[], battery=100.0,
                   capacity=1, load=0, speed=1, task=None, state='IDLE', distance=0, completed=0,
                   failures=[], wait=0, idle=0, busy=0, delay=0) for i in range(fleet)]
    return dict(tick=0, epoch_tick=0, order_counter=0, status='paused', speed=1, seed=seed, policy=policy, layout=layout, robots=robots,
                orders=[], events=[], sequence=0, blocked=[], failed_chargers=[], unavailable=[],
                planning={'calls': 0, 'waits': 0, 'deadlocks': 0, 'replans': 0}, consumption=0.0,
                collision_violations=0, simulated=True)


def event(s, kind, message, **data):
    s['sequence'] += 1
    s['events'].append(dict(seq=s['sequence'], tick=s['tick'], kind=kind, message=message, **data))
    s['events'] = s['events'][-300:]


def order(s, pickup=None, dropoff=None, priority=2, deadline=None, key=None):
    if key and any(o['key'] == key for o in s['orders']):
        return next(o for o in s['orders'] if o['key'] == key)
    rng = random.Random(s['seed'] + len(s['orders']) * 7919)
    pickup = pickup if pickup is not None else rng.choice(s['layout']['pickup'])
    dropoff = dropoff if dropoff is not None else rng.choice(s['layout']['dropoff'])
    if pickup not in s['layout']['pickup'] or dropoff not in s['layout']['dropoff']:
        raise ValueError('Select configured pickup and dropoff stations')
    if not 1 <= priority <= 5:
        raise ValueError('Priority must be 1–5')
    if deadline is not None and (not isinstance(deadline, int) or deadline < s['tick']):
        raise ValueError('Deadline must be an integer tick at or after the current tick')
    s['order_counter'] += 1
    o = dict(id=f'O{s["order_counter"]:05}', pickup=pickup, dropoff=dropoff, priority=priority,
             deadline=deadline if deadline is not None else s['tick'] + 180, created=s['tick'],
             started=None, finished=None, robot=None, status='QUEUED', key=key,
             history=[dict(tick=s['tick'], status='QUEUED')], eta=None, checkpoint=0)
    s['orders'].append(o)
    event(s, 'order', f'{o["id"]} queued', order=o['id'])
    return o


def transition(s, o, status):
    o['status'] = status
    o['history'].append(dict(tick=s['tick'], status=status))
    event(s, 'order', f'{o["id"]}: {status}', order=o['id'])


def dispatch(s):
    queued = [o for o in s['orders'] if o['status'] == 'QUEUED']
    if s['policy'] == 'improved':
        queued.sort(key=lambda o: (-o['priority'], o['deadline'], o['created'], o['id']))
    for o in queued:
        candidates = []
        for r in s['robots']:
            travel = distance(r['pos'], o['pickup']) + distance(o['pickup'], o['dropoff'])
            charge = min(distance(o['dropoff'], c) for c in s['layout']['chargers'])
            congestion = sum(distance(r['pos'], other['pos']) < 3 for other in s['robots'] if other != r)
            sufficient = r['battery'] > (travel + charge) * .3 + 12
            score = travel + congestion * 3 + r['completed'] * .25
            candidates.append(dict(robot=r['id'], distance=travel, congestion=congestion,
                                   battery=r['battery'], required_charge=round((travel + charge) * .3 + 12, 2),
                                   available=r['state'] == 'IDLE', sufficient=sufficient, score=score))
        eligible = [c for c in candidates if c['available'] and c['sufficient']]
        if not eligible:
            break
        chosen = min(eligible, key=lambda c: (c['score'], c['robot'])) if s['policy'] == 'improved' else eligible[0]
        r = next(r for r in s['robots'] if r['id'] == chosen['robot'])
        r.update(task=o['id'], state='ASSIGNED', destination=o['pickup'], route=[])
        o.update(robot=r['id'], started=s['tick'], eta=s['tick'] + chosen['distance'] + 4)
        transition(s, o, 'ASSIGNED')
        event(s, 'decision', f'{r["id"]} selected for {o["id"]}: ' +
              ('lowest eligible distance + congestion + workload score' if s['policy'] == 'improved' else 'first available robot'),
              robot=r['id'], candidates=candidates, policy=s['policy'])


def active_grid(s):
    grid = copy.deepcopy(s['layout'])
    grid['blocked'] += grid.get('restricted', []) + s['blocked']
    return grid


def step(s):
    if s['status'] != 'running':
        return s
    s['tick'] += 1
    dispatch(s)
    grid = active_grid(s)
    robots = s['robots']
    # Reserve every current cell at t+1. Earlier planners cannot enter cells not yet vacated.
    cells = {(tuple(r['pos']), 1) for r in robots}
    edges = set()
    before = {r['id']: tuple(r['pos']) for r in robots}
    offset = s['tick'] % len(robots)
    for r in robots[offset:] + robots[:offset]:
        r['busy' if r['task'] else 'idle'] += 1
        if r['state'] in ('FAULT', 'PAUSED'):
            continue
        if r['state'] == 'RECOVERING':
            r['state'] = 'MOVING_TO_PICKUP' if r['task'] else 'IDLE'
        if r['state'] == 'ASSIGNED':
            r['state'] = 'MOVING_TO_PICKUP'
        o = next((o for o in s['orders'] if o['id'] == r['task']), None)
        if r['battery'] <= 0:
            r['state'] = 'FAULT'
            event(s, 'incident', f'{r["id"]} battery exhausted', robot=r['id'])
            continue
        if r['delay']:
            r['delay'] -= 1
            continue
        if r['state'] == 'LOADING':
            waypoints = s['layout']['checkpoints'] + [o['dropoff']]
            r.update(load=1, state='MOVING_TO_DROPOFF', destination=waypoints[0])
            transition(s, o, 'IN_TRANSIT')
        elif r['state'] == 'UNLOADING':
            o['finished'] = s['tick']
            transition(s, o, 'COMPLETED')
            r.update(load=0, task=None, state='IDLE', destination=None, route=[])
            r['completed'] += 1
            o = None
        if r['state'] == 'CHARGING' and r['pos'] in s['layout']['chargers'] and r['pos'] not in s['failed_chargers']:
            r['battery'] = min(100, r['battery'] + 2)
            if r['battery'] >= 95:
                r.update(state='IDLE', destination=None)
            continue
        if not r['task'] and (r['battery'] < 40 or r['state'] == 'CHARGING'):
            available = [c for c in s['layout']['chargers'] if c not in s['failed_chargers']]
            if available:
                r.update(state='CHARGING', destination=min(available, key=lambda c: distance(c, r['pos'])))
            else:
                r.update(state='IDLE', destination=None)
        if r['destination'] is None:
            # Vacate service stations to avoid an idle robot permanently blocking deliveries.
            stations = s['layout']['pickup'] + s['layout']['dropoff'] + s['layout']['chargers']
            if r['pos'] in stations:
                choices = [list(p) for p in neighbors(grid, r['pos']) if list(p) not in stations and (p, 1) not in cells]
                if choices:
                    r['destination'] = choices[0]
            if r['destination'] is None:
                continue
        if r['pos'] == r['destination']:
            if o and r['state'] == 'MOVING_TO_PICKUP':
                r.update(state='LOADING', delay=1)
                transition(s, o, 'LOADING')
            elif o and r['state'] == 'MOVING_TO_DROPOFF':
                if o['checkpoint'] < len(s['layout']['checkpoints']):
                    o['checkpoint'] += 1
                    r['destination'] = (s['layout']['checkpoints'] + [o['dropoff']])[o['checkpoint']]
                    event(s, 'checkpoint', f'{r["id"]} reached checkpoint {o["checkpoint"]}', robot=r['id'])
                elif r['pos'] not in s['unavailable']:
                    r.update(state='UNLOADING', delay=1)
                    transition(s, o, 'UNLOADING')
            elif not o and r['state'] != 'CHARGING':
                r['destination'] = None
            continue
        old = tuple(r['pos'])
        cells.discard((old, 1))
        s['planning']['calls'] += 1
        path = astar(grid, old, r['destination'], cells, edges)
        if path and path[0] != r['pos']:
            if r['route'] and path != r['route']:
                s['planning']['replans'] += 1
                event(s, 'reroute', f'{r["id"]}: A* changed route under current reservations', robot=r['id'],
                      previous_length=len(r['route']), selected_length=len(path), destination=r['destination'],
                      reserved_cells=len(cells), blocked_cells=len(grid['blocked']))
            r['route'] = path
            r['pos'] = path.pop(0)
            r['distance'] += 1
            r['battery'] = round(max(0, r['battery'] - .15 - .05 * r['load']), 3)
            s['consumption'] = round(s['consumption'] + .15 + .05 * r['load'], 3)
            r['wait'] = 0
        else:
            r['wait'] += 1
            r['route'] = path or []
            s['planning']['waits'] += 1
            if r['wait'] % 12 == 0:
                s['planning']['deadlocks'] += 1
                # Safe local escape; never teleport or swap. Keep original mission destination.
                escape = [p for p in neighbors(grid, old) if (p, 1) not in cells and (p, old, 1) not in edges]
                if escape:
                    r['pos'] = list(escape[(s['tick'] // 12) % len(escape)])
                    r['distance'] += 1
                    r['battery'] = round(max(0, r['battery'] - .2), 3)
                    s['consumption'] = round(s['consumption'] + .2, 3)
                event(s, 'deadlock', f'{r["id"]}: safe escape attempted after 12 waiting ticks', robot=r['id'])
        cells.add((tuple(r['pos']), 1))
        edges.add((old, tuple(r['pos']), 1))
        if o:
            o['eta'] = s['tick'] + len(r['route']) + (distance(o['pickup'], o['dropoff']) if not r['load'] else 0) + 4
    positions = [tuple(r['pos']) for r in robots]
    assert len(set(positions)) == len(positions), 'Occupancy invariant violated'
    for i, r in enumerate(robots):
        for other in robots[i + 1:]:
            assert not (before[r['id']] == tuple(other['pos']) and before[other['id']] == tuple(r['pos'])), 'Edge swap'
    return s


def command(s, kind, data):
    if kind in ('start', 'resume', 'pause', 'stop'):
        s['status'] = {'start': 'running', 'resume': 'running', 'pause': 'paused', 'stop': 'stopped'}[kind]
    elif kind == 'reset':
        fresh = new_state(s['layout'], len(s['robots']), s['seed'], s['policy'])
        fresh['sequence'] = s['sequence']
        fresh['tick'] = s['tick']  # Preserve a monotonic history within this run.
        fresh['epoch_tick'] = s['tick']
        fresh['order_counter'] = s['order_counter']
        s.clear()
        s.update(fresh)
    elif kind == 'speed':
        value = float(data['value'])
        if value not in (.5, 1, 2, 4, 8):
            raise ValueError('Unsupported speed')
        s['speed'] = value
    elif kind in ('generate', 'surge', 'urgent'):
        count = 1 if kind == 'urgent' else int(data.get('count', 20))
        if not 1 <= count <= 200:
            raise ValueError('Order count must be 1–200')
        for _ in range(count):
            order(s, priority=5 if kind == 'urgent' else 2)
    elif kind == 'order':
        order(s, **data)
    elif kind == 'cancel':
        o = next((o for o in s['orders'] if o['id'] == data['id']), None)
        if not o or o['status'] in ('COMPLETED', 'CANCELLED'):
            raise ValueError('Order cannot be cancelled')
        if o['robot']:
            r = next(r for r in s['robots'] if r['id'] == o['robot'])
            r.update(task=None, load=0, destination=None, route=[], state='IDLE')
        transition(s, o, 'CANCELLED')
    elif kind == 'assign':
        o = next((o for o in s['orders'] if o['id'] == data['id']), None)
        r = next((r for r in s['robots'] if r['id'] == data['robot']), None)
        if not o or o['status'] != 'QUEUED' or not r or r['state'] != 'IDLE' or r['battery'] < 40:
            raise ValueError('Assignment requires a queued order and an idle charged robot')
        o.update(robot=r['id'], started=s['tick'])
        r.update(task=o['id'], destination=o['pickup'], state='ASSIGNED')
        transition(s, o, 'ASSIGNED')
    elif kind in ('breakdown', 'recover', 'low_battery'):
        r = next((r for r in s['robots'] if r['id'] == data['robot']), None)
        if not r:
            raise ValueError('Unknown robot')
        if kind == 'breakdown':
            r['state'] = 'FAULT'
            r['failures'].append(s['tick'])
        elif kind == 'recover':
            r.update(state='MOVING_TO_DROPOFF' if r['load'] else 'RECOVERING', battery=max(30, r['battery']))
        else:
            r['battery'] = 5
    elif kind in ('block', 'unblock', 'charger_failure', 'charger_restore', 'station_failure', 'station_restore'):
        cell = data['cell']
        if not (isinstance(cell, list) and len(cell) == 2 and all(isinstance(x, int) for x in cell)
                and 0 <= cell[0] < s['layout']['width'] and 0 <= cell[1] < s['layout']['height']):
            raise ValueError('Invalid cell')
        target = 'blocked' if kind in ('block', 'unblock') else 'failed_chargers' if kind.startswith('charger') else 'unavailable'
        if kind.startswith('charger') and cell not in s['layout']['chargers']:
            raise ValueError('Select a charging station')
        if kind.startswith('station') and cell not in s['layout']['dropoff']:
            raise ValueError('Select a delivery station')
        if kind == 'block' and (any(r['pos'] == cell for r in s['robots']) or cell in s['layout']['blocked']):
            raise ValueError('Cannot block occupied cells or racks')
        if kind in ('unblock', 'charger_restore', 'station_restore'):
            if cell in s[target]:
                s[target].remove(cell)
        elif cell not in s[target]:
            s[target].append(cell)
        for r in s['robots']:
            r['route'] = []
    else:
        raise ValueError('Unknown command')
    event(s, 'incident' if kind in ('block', 'breakdown', 'low_battery', 'charger_failure', 'station_failure', 'surge', 'urgent') else 'command',
          kind.replace('_', ' '), command=kind, inputs=data)


def metrics(s):
    done = [o for o in s['orders'] if o['status'] == 'COMPLETED']
    durations = [o['finished'] - o['created'] for o in done]
    busy = sum(r['busy'] for r in s['robots'])
    idle = sum(r['idle'] for r in s['robots'])
    assigned = [o for o in s['orders'] if o['started'] is not None]
    elapsed = s['tick'] - s.get('epoch_tick', 0)
    return dict(completed=len(done), average_duration=sum(durations) / len(done) if done else 0,
                on_time=100 * sum(o['finished'] <= o['deadline'] for o in done) / len(done) if done else 0,
                utilization=100 * busy / (busy + idle) if busy + idle else 0, idle_time=idle,
                travel_distance=sum(r['distance'] for r in s['robots']), battery_consumption=s['consumption'],
                congestion=s['planning']['waits'], collision_violations=s['collision_violations'],
                throughput=len(done) * 3600 / elapsed if elapsed else 0,
                queue_wait=sum(o['started'] - o['created'] for o in assigned) / len(assigned) if assigned else 0,
                deadline_misses=sum((o['finished'] if o['finished'] is not None else s['tick']) > o['deadline']
                                    for o in s['orders'] if o['status'] != 'CANCELLED'))


def experiment(source, changes, ticks=300, count=60):
    """Fresh paired scenarios share layout, seed and identical initial workload."""
    base = new_state(source['layout'], len(source['robots']), source['seed'], source['policy'])
    variant_layout = copy.deepcopy(source['layout'])
    if changes.get('remove_charger') and len(variant_layout['chargers']) > 1:
        variant_layout['chargers'].pop()
    variant = new_state(variant_layout, changes.get('fleet', len(source['robots'])), source['seed'],
                        changes.get('policy', source['policy']))
    for state in (base, variant):
        for _ in range(count):
            order(state)
        state['status'] = 'running'
    if changes.get('blocked'):
        command(variant, 'block', {'cell': changes['blocked']})
    for o in variant['orders']:
        o['priority'] = changes.get('priority', o['priority'])
    series = []
    for tick in range(ticks):
        if tick and tick % 30 == 0:
            for state in (base, variant):
                for _ in range(changes.get('arrival_rate', 0) if state is variant else 0):
                    order(state)
        step(base)
        step(variant)
        if (tick + 1) % 10 == 0:
            series.append(dict(tick=tick + 1, baseline=metrics(base)['completed'], variant=metrics(variant)['completed']))
    a, b = metrics(base), metrics(variant)
    return dict(baseline=a, variant=b, delta={k: b[k] - a[k] for k in a}, series=series,
                seed=source['seed'], ticks=ticks, workload=count, changes=changes, simulated=True,
                method='Fresh paired runs with identical seeded initial orders. Delta = variant − baseline. '
                       'Arrival-rate changes intentionally add variant-only orders; finite-horizon unfinished orders are not completion durations.')
