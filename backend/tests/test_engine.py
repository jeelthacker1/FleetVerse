import copy
import time

import pytest

from app.engine import astar, command, experiment, layouts, metrics, new_state, order, step, validate_layout


def test_astar_shortest_unreachable_and_lane():
    grid = dict(width=4, height=3, blocked=[], lanes={})
    path = astar(grid, [0, 0], [3, 2])
    assert len(path) == 5 and path[-1] == [3, 2]
    grid['blocked'] = [[2, y] for y in range(3)]
    assert astar(grid, [0, 0], [3, 2]) is None
    grid['lanes'] = {'0,0': 'N'}
    assert astar(grid, [0, 0], [1, 0]) is None


def test_time_reservation_wait_and_edge_swap():
    grid = dict(width=3, height=1, blocked=[], lanes={})
    path = astar(grid, [0, 0], [2, 0], {((1, 0), 1)})
    assert path[0] == [0, 0] and path[-1] == [2, 0]
    path = astar(grid, [0, 0], [2, 0], edges={((1, 0), (0, 0), 1)})
    assert path[0] == [0, 0]


@pytest.mark.parametrize('layout', layouts())
def test_layout_validation(layout):
    assert validate_layout(layout)
    layout['chargers'] = []
    with pytest.raises(ValueError):
        validate_layout(layout)


def test_deterministic_replay_and_restore():
    a = new_state(fleet=5)
    command(a, 'generate', {'count': 10})
    command(a, 'start', {})
    b = copy.deepcopy(a)
    for _ in range(35):
        step(a)
        step(b)
    assert a == b
    restored = copy.deepcopy(a)
    for _ in range(40):
        step(a)
        step(restored)
    assert a == restored


def test_order_idempotency_transition_cancel_and_explanation():
    s = new_state(fleet=3)
    first = order(s, key='same')
    assert order(s, key='same') is first and len(s['orders']) == 1
    command(s, 'start', {})
    step(s)
    decision = next(e for e in s['events'] if e['kind'] == 'decision')
    eligible = [c for c in decision['candidates'] if c['available'] and c['sufficient']]
    selected = min(eligible, key=lambda c: (c['score'], c['robot']))
    assert first['robot'] == selected['robot']
    command(s, 'cancel', {'id': first['id']})
    assert first['status'] == 'CANCELLED'
    assert all(r['task'] is None for r in s['robots'])
    with pytest.raises(ValueError):
        command(s, 'cancel', {'id': first['id']})


def test_delivery_completes_and_battery_recharges():
    s = new_state(fleet=1)
    o = order(s)
    command(s, 'start', {})
    for _ in range(250):
        step(s)
    assert o['status'] == 'COMPLETED'
    assert [h['status'] for h in o['history']] == ['QUEUED', 'ASSIGNED', 'LOADING', 'IN_TRANSIT', 'UNLOADING', 'COMPLETED']
    r = s['robots'][0]
    r.update(battery=30, pos=s['layout']['chargers'][0], state='CHARGING')
    for _ in range(40):
        step(s)
    assert r['battery'] >= 95


def test_failures_have_consequences():
    s = new_state(fleet=2)
    command(s, 'breakdown', {'robot': 'R01'})
    pos = s['robots'][0]['pos'][:]
    command(s, 'generate', {'count': 4})
    command(s, 'start', {})
    for _ in range(15):
        step(s)
    assert s['robots'][0]['pos'] == pos
    assert s['robots'][0]['state'] == 'FAULT'
    command(s, 'recover', {'robot': 'R01'})
    step(s)
    assert s['robots'][0]['state'] != 'FAULT'
    with pytest.raises(ValueError):
        command(s, 'block', {'cell': s['robots'][0]['pos']})
    command(s, 'charger_failure', {'cell': s['layout']['chargers'][0]})
    assert len(s['failed_chargers']) == 1
    command(s, 'station_failure', {'cell': s['layout']['dropoff'][0]})
    assert len(s['unavailable']) == 1


def test_low_battery_not_dispatched():
    s = new_state(fleet=1)
    s['robots'][0]['battery'] = 10
    order(s)
    command(s, 'start', {})
    step(s)
    assert s['orders'][0]['status'] == 'QUEUED'
    assert s['robots'][0]['state'] == 'CHARGING'


def test_deadlock_escape_and_block_replanning():
    s = new_state(fleet=2)
    s['robots'][0].update(pos=[2, 2], destination=[3, 2], task=None, wait=11)
    s['robots'][1].update(pos=[3, 2], state='FAULT')
    s['status'] = 'running'
    step(s)
    assert s['planning']['deadlocks'] == 1
    assert s['robots'][0]['pos'] != s['robots'][1]['pos']
    command(s, 'block', {'cell': [2, 4]})
    assert [2, 4] in s['blocked']
    assert all(not r['route'] for r in s['robots'])


def test_seeded_experiment_equal_configuration_is_equal():
    s = new_state(fleet=3)
    result = experiment(s, {'fleet': 3, 'policy': 'improved'}, ticks=80, count=8)
    assert result['baseline'] == result['variant']
    assert all(v == 0 for v in result['delta'].values())


def test_twenty_robots_stress_safety_and_progress():
    s = new_state(fleet=20)
    command(s, 'generate', {'count': 100})
    command(s, 'start', {})
    start = time.perf_counter()
    for _ in range(300):
        before = {r['id']: r['pos'][:] for r in s['robots']}
        step(s)
        assert len({tuple(r['pos']) for r in s['robots']}) == 20
        for r in s['robots']:
            assert abs(r['pos'][0] - before[r['id']][0]) + abs(r['pos'][1] - before[r['id']][1]) <= 1
    assert metrics(s)['completed'] >= 10
    print(f'BENCHMARK 20 robots / 100 orders / 300 ticks: {time.perf_counter()-start:.3f}s, {metrics(s)}')


def test_checkpoints_reset_and_invalid_deadline():
    layout = layouts()[0]
    layout['checkpoints'] = [[10, 1], [14, 1]]
    s = new_state(layout, fleet=1)
    o = order(s)
    command(s, 'start', {})
    for _ in range(200):
        step(s)
    assert o['status'] == 'COMPLETED'
    assert o['checkpoint'] == 2
    assert len([e for e in s['events'] if e['kind'] == 'checkpoint']) == 2
    old_tick, old_id = s['tick'], o['id']
    command(s, 'reset', {})
    assert s['tick'] == old_tick and metrics(s)['throughput'] == 0
    assert order(s)['id'] != old_id
    with pytest.raises(ValueError):
        order(s, deadline='tomorrow')
