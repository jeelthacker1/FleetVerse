import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

os.environ['DATABASE_URL'] = 'sqlite:///' + tempfile.mktemp(suffix='.db', prefix='fleetverse-test-').replace('\\', '/')
os.environ['DEMO_MODE'] = 'true'
os.environ['COOKIE_SECURE'] = 'false'

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.bootstrap import bootstrap
from app.db import Base, Command, Event, SessionLocal, Snapshot, engine
from app.main import app, limiter
from app.worker import process_experiment, process_run


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    limiter.clear()
    bootstrap()
    yield


def client(role='admin'):
    c = TestClient(app, headers={'Origin': 'http://localhost:3000'})
    result = c.post('/api/v1/auth/login', json={'username': role, 'password': 'fleetverse-demo'})
    assert result.status_code == 200
    c.headers['X-CSRF-Token'] = result.json()['csrf']
    return c


def create_run(c):
    r = c.post('/api/v1/simulations', json={'layout_id': 1, 'fleet': 3})
    assert r.status_code == 201, r.text
    return r.json()['id']


def submit(c, run, kind, data=None, key=None):
    return c.post(f'/api/v1/simulations/{run}/commands', json={'kind': kind, 'data': data or {}},
                  headers={'Idempotency-Key': key or f'test-{kind}-command'})


def test_auth_roles_csrf_and_websocket():
    c = TestClient(app)
    assert c.get('/api/v1/layouts').status_code == 401
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect('/api/v1/ws/1'):
            pass
    viewer = client('viewer')
    assert viewer.post('/api/v1/simulations', json={'layout_id': 1}).status_code == 403
    admin = client()
    run = create_run(admin)
    admin.headers.pop('X-CSRF-Token')
    assert submit(admin, run, 'start').status_code == 403
    assert admin.post('/api/v1/auth/logout', json={}, headers={'Origin': 'https://evil.example'}).status_code == 403


def test_worker_persistence_replay_and_export():
    c = client()
    run = create_run(c)
    assert submit(c, run, 'generate', {'count': 5}).status_code == 202
    assert submit(c, run, 'start').status_code == 202
    for _ in range(10):
        process_run(run)
    state = c.get(f'/api/v1/simulations/{run}').json()
    assert state['state']['tick'] == 10
    assert state['metrics']['travel_distance'] > 0
    with SessionLocal() as db:
        assert db.scalar(select(Event.id))
        snapshot = db.scalar(select(Snapshot).where(Snapshot.run_id == run, Snapshot.tick == 5))
        expected = snapshot.data
    history = c.get(f'/api/v1/simulations/{run}/history/5').json()
    assert history['state'] == expected and history['historical']
    exp = c.post('/api/v1/experiments', json={'run_id': run, 'changes': {'fleet': 3}, 'ticks': 20, 'count': 5})
    assert exp.status_code == 202
    process_experiment()
    result = c.get(f'/api/v1/experiments/{exp.json()["id"]}').json()
    assert result['status'] == 'completed'
    assert result['result']['baseline'] == result['result']['variant']
    csv = c.get(f'/api/v1/reports/experiments/{exp.json()["id"]}?format=csv')
    assert csv.status_code == 200 and 'metric,baseline,variant,delta' in csv.text


def test_concurrent_idempotent_submissions():
    c = client()
    run = create_run(c)
    def send(_):
        return submit(c, run, 'generate', {'count': 2}, 'concurrent-key')
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(send, range(4)))
    assert all(r.status_code == 202 for r in responses)
    assert len({r.json()['id'] for r in responses}) == 1
    process_run(run, False)
    assert len(c.get(f'/api/v1/simulations/{run}').json()['state']['orders']) == 2
    assert submit(c, run, 'generate', {'count': 3}, 'concurrent-key').status_code == 409


def test_revalidation_rejects_stale_commands_atomically():
    c = client()
    run = create_run(c)
    submit(c, run, 'generate', {'count': 1})
    process_run(run, False)
    submit(c, run, 'cancel', {'id': 'O00001'}, 'cancel-key-one')
    submit(c, run, 'cancel', {'id': 'O00001'}, 'cancel-key-two')
    process_run(run, False)
    with SessionLocal() as db:
        statuses = [r.status for r in db.scalars(select(Command).where(Command.kind == 'cancel').order_by(Command.id))]
    assert statuses == ['applied', 'rejected']


def test_two_websockets_share_state_and_logout_revokes():
    c = client()
    run = create_run(c)
    with c.websocket_connect(f'/api/v1/ws/{run}', headers={'Origin': 'http://localhost:3000'}) as first:
        a = first.receive_json()
        with c.websocket_connect(f'/api/v1/ws/{run}', headers={'Origin': 'http://localhost:3000'}) as second:
            b = second.receive_json()
            assert a == b
    assert c.post('/api/v1/auth/logout', json={}).status_code == 200
    assert c.get('/api/v1/layouts').status_code == 401
