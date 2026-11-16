import asyncio
import csv
import hashlib
import io
import json
import os
import secrets
import time
from collections import defaultdict, deque
from datetime import timedelta
from typing import Literal

import redis.asyncio as redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.bootstrap import save_cells
from app.db import (Audit, Command, Event, Experiment, ExperimentResult, Layout, Run, Session,
                    SessionLocal, Snapshot, User, Warehouse, now, session)
from app.engine import command, metrics, new_state, validate_layout

app = FastAPI(title='FleetVerse', version='1.0.0', description='Simulated warehouse operations API')
origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
secure = os.getenv('COOKIE_SECURE', 'true').lower() == 'true'
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                   allow_methods=['GET', 'POST', 'DELETE'], allow_headers=['Content-Type', 'X-CSRF-Token', 'Idempotency-Key'])
limiter = defaultdict(deque)


@app.middleware('http')
async def protection(request: Request, call_next):
    if request.method in ('POST', 'DELETE') and request.headers.get('origin') not in origins:
        return Response('Origin not permitted', status_code=403)
    key = (request.client.host if request.client else 'unknown', 'login' if request.url.path.endswith('/login') else 'api')
    queue = limiter[key]
    current = time.monotonic()
    while queue and current - queue[0] > 60:
        queue.popleft()
    if len(queue) >= (15 if key[1] == 'login' else 600):
        return Response('Rate limit exceeded', status_code=429, headers={'Retry-After': '60'})
    queue.append(current)
    result = await call_next(request)
    result.headers['X-Content-Type-Options'] = 'nosniff'
    result.headers['Cache-Control'] = 'no-store'
    return result


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def authenticate(token, db):
    row = db.get(Session, digest(token or ''))
    if row is None or row.expires.replace(tzinfo=now().tzinfo) <= now():
        raise HTTPException(401, 'Authentication required')
    user = db.get(User, row.user_id)
    if user is None:
        raise HTTPException(401, 'Authentication required')
    return user, row


def current_user(request: Request, db=Depends(session)):
    user, row = authenticate(request.cookies.get('fv_session'), db)
    if request.method not in ('GET', 'HEAD') and not secrets.compare_digest(request.headers.get('x-csrf-token', ''), row.csrf):
        raise HTTPException(403, 'CSRF token required')
    return user


def operator(user=Depends(current_user)):
    if user.role not in ('ADMIN', 'OPERATOR'):
        raise HTTPException(403, 'Operator role required')
    return user


def admin(user=Depends(current_user)):
    if user.role != 'ADMIN':
        raise HTTPException(403, 'Administrator role required')
    return user


def get_run(db, run_id):
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(404, 'Run not found')
    return run


def audit(db, user, action, data):
    db.add(Audit(user_id=user.id, action=action, data=data))


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class NewUser(Login):
    password: str = Field(min_length=12, max_length=200)
    role: Literal['ADMIN', 'OPERATOR', 'VIEWER']


class Name(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class LayoutInput(Name):
    warehouse_id: int
    data: dict


class RunInput(BaseModel):
    layout_id: int
    fleet: int = Field(default=20, ge=1, le=80)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    policy: Literal['baseline', 'improved'] = 'improved'


class CommandInput(BaseModel):
    kind: Literal['start', 'resume', 'pause', 'stop', 'reset', 'speed', 'generate', 'surge', 'urgent',
                  'order', 'cancel', 'assign', 'breakdown', 'recover', 'low_battery', 'block', 'unblock',
                  'charger_failure', 'charger_restore', 'station_failure', 'station_restore']
    data: dict = Field(default_factory=dict)


class Changes(BaseModel):
    fleet: int = Field(default=20, ge=1, le=80)
    policy: Literal['baseline', 'improved'] = 'improved'
    remove_charger: bool = False
    blocked: list[int] | None = Field(default=None, min_length=2, max_length=2)
    priority: int = Field(default=2, ge=1, le=5)
    arrival_rate: int = Field(default=0, ge=0, le=20)


class ExperimentInput(BaseModel):
    run_id: int
    changes: Changes
    ticks: int = Field(default=300, ge=10, le=2000)
    count: int = Field(default=60, ge=1, le=200)


@app.get('/health')
def health(db=Depends(session)):
    db.execute(select(1))
    return {'status': 'ok'}


@app.post('/api/v1/auth/login')
def login(body: Login, response: Response, db=Depends(session)):
    user = db.scalar(select(User).where(User.username == body.username))
    try:
        if user is None:
            # Perform the same expensive operation for nonexistent accounts.
            PasswordHasher().hash(body.password)
            raise HTTPException(401, 'Invalid credentials')
        PasswordHasher().verify(user.password, body.password)
    except VerificationError:
        raise HTTPException(401, 'Invalid credentials') from None
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.add(Session(token=digest(token), user_id=user.id, csrf=csrf, expires=now() + timedelta(hours=12)))
    audit(db, user, 'login', {})
    db.commit()
    response.set_cookie('fv_session', token, httponly=True, secure=secure, samesite='strict', max_age=43200)
    return dict(username=user.username, role=user.role, csrf=csrf)


@app.get('/api/v1/auth/me')
def me(request: Request, db=Depends(session)):
    user, row = authenticate(request.cookies.get('fv_session'), db)
    return dict(username=user.username, role=user.role, csrf=row.csrf)


@app.post('/api/v1/auth/logout')
def logout(request: Request, response: Response, user=Depends(current_user), db=Depends(session)):
    db.delete(db.get(Session, digest(request.cookies['fv_session'])))
    audit(db, user, 'logout', {})
    db.commit()
    response.delete_cookie('fv_session')
    return {'ok': True}


@app.get('/api/v1/users')
def users(user=Depends(admin), db=Depends(session)):
    return [dict(id=u.id, username=u.username, role=u.role) for u in db.scalars(select(User))]


@app.post('/api/v1/users', status_code=201)
def create_user(body: NewUser, user=Depends(admin), db=Depends(session)):
    row = User(username=body.username, role=body.role, password=PasswordHasher().hash(body.password))
    db.add(row)
    audit(db, user, 'user.create', {'username': body.username, 'role': body.role})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Username already exists') from None
    return {'id': row.id}


@app.get('/api/v1/warehouses')
def warehouses(user=Depends(current_user), db=Depends(session)):
    return [dict(id=w.id, name=w.name) for w in db.scalars(select(Warehouse))]


@app.post('/api/v1/warehouses', status_code=201)
def create_warehouse(body: Name, user=Depends(admin), db=Depends(session)):
    row = Warehouse(name=body.name)
    db.add(row)
    audit(db, user, 'warehouse.create', body.model_dump())
    db.commit()
    return {'id': row.id, 'name': row.name}


@app.get('/api/v1/layouts')
def get_layouts(user=Depends(current_user), db=Depends(session)):
    return [dict(id=row.id, name=row.name, warehouse_id=row.warehouse_id, data=row.data)
            for row in db.scalars(select(Layout))]


@app.post('/api/v1/layouts', status_code=201)
def create_layout(body: LayoutInput, user=Depends(admin), db=Depends(session)):
    if db.get(Warehouse, body.warehouse_id) is None:
        raise HTTPException(404, 'Warehouse not found')
    try:
        validate_layout(body.data)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from None
    row = Layout(name=body.name, warehouse_id=body.warehouse_id, data=body.data)
    db.add(row)
    db.flush()
    save_cells(db, row)
    audit(db, user, 'layout.create', {'name': body.name})
    db.commit()
    return {'id': row.id}


@app.get('/api/v1/simulations')
def runs(user=Depends(current_user), db=Depends(session)):
    return [dict(id=r.id, tick=r.state['tick'], status=r.state['status'], layout_id=r.layout_id)
            for r in db.scalars(select(Run).order_by(Run.id.desc()))]


@app.post('/api/v1/simulations', status_code=201)
def create_run(body: RunInput, user=Depends(admin), db=Depends(session)):
    layout = db.get(Layout, body.layout_id)
    if layout is None:
        raise HTTPException(404, 'Layout not found')
    try:
        state = new_state(layout.data, body.fleet, body.seed, body.policy)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    row = Run(layout_id=layout.id, state=state)
    db.add(row)
    db.flush()
    db.add(Snapshot(run_id=row.id, tick=0, revision=0, data=state))
    audit(db, user, 'simulation.create', body.model_dump())
    db.commit()
    return {'id': row.id}


@app.get('/api/v1/simulations/{run_id}')
def state(run_id: int, user=Depends(current_user), db=Depends(session)):
    row = get_run(db, run_id)
    return dict(id=row.id, revision=row.revision, state=row.state, metrics=metrics(row.state))


@app.post('/api/v1/simulations/{run_id}/commands', status_code=202)
def submit(run_id: int, body: CommandInput, request: Request, user=Depends(operator), db=Depends(session)):
    run = get_run(db, run_id)
    if body.kind == 'reset' and user.role != 'ADMIN':
        raise HTTPException(403, 'Administrator role required')
    key = request.headers.get('idempotency-key', '')
    if not 8 <= len(key) <= 80:
        raise HTTPException(422, 'Idempotency-Key header (8–80 characters) required')
    existing = db.scalar(select(Command).where(Command.run_id == run_id, Command.key == key))
    if existing:
        if existing.kind != body.kind or existing.data != body.data:
            raise HTTPException(409, 'Idempotency key reused with different payload')
        return dict(id=existing.id, status=existing.status, error=existing.error)
    import copy
    try:
        command(copy.deepcopy(run.state), body.kind, body.data)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from None
    row = Command(run_id=run_id, user_id=user.id, key=key, kind=body.kind, data=body.data)
    db.add(row)
    audit(db, user, 'command.' + body.kind, {'run_id': run_id, 'inputs': body.data})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Command).where(Command.run_id == run_id, Command.key == key))
        if not existing or existing.kind != body.kind or existing.data != body.data:
            raise HTTPException(409, 'Conflicting idempotency key') from None
        return dict(id=existing.id, status=existing.status, error=existing.error)
    return dict(id=row.id, status=row.status, error=None)


@app.get('/api/v1/commands/{command_id}')
def command_status(command_id: int, user=Depends(current_user), db=Depends(session)):
    row = db.get(Command, command_id)
    if row is None:
        raise HTTPException(404, 'Command not found')
    return dict(id=row.id, status=row.status, error=row.error)


@app.get('/api/v1/simulations/{run_id}/robots')
def robots(run_id: int, user=Depends(current_user), db=Depends(session)):
    return get_run(db, run_id).state['robots']


@app.get('/api/v1/simulations/{run_id}/orders')
def orders(run_id: int, user=Depends(current_user), db=Depends(session)):
    return get_run(db, run_id).state['orders']


@app.get('/api/v1/simulations/{run_id}/metrics')
def get_metrics(run_id: int, user=Depends(current_user), db=Depends(session)):
    return metrics(get_run(db, run_id).state)


@app.get('/api/v1/simulations/{run_id}/events')
def events(run_id: int, kind: str | None = None, after: int = 0, user=Depends(current_user), db=Depends(session)):
    get_run(db, run_id)
    rows = db.scalars(select(Event).where(Event.run_id == run_id, Event.seq > after).order_by(Event.seq).limit(5000))
    return [dict(**r.data, timestamp=r.created.isoformat()) for r in rows if kind is None or r.data['kind'] == kind]


@app.get('/api/v1/simulations/{run_id}/incidents')
def incidents(run_id: int, user=Depends(current_user), db=Depends(session)):
    get_run(db, run_id)
    rows = db.scalars(select(Event).where(Event.run_id == run_id).order_by(Event.seq.desc()).limit(5000))
    return [r.data for r in rows if r.data['kind'] in ('incident', 'deadlock')]


@app.get('/api/v1/simulations/{run_id}/history/{tick}')
def history(run_id: int, tick: int, user=Depends(current_user), db=Depends(session)):
    get_run(db, run_id)
    row = db.scalar(select(Snapshot).where(Snapshot.run_id == run_id, Snapshot.tick <= tick)
                    .order_by(Snapshot.tick.desc(), Snapshot.revision.desc()).limit(1))
    if row is None:
        raise HTTPException(404, 'Snapshot not found')
    return dict(id=run_id, revision=row.revision, state=row.data, metrics=metrics(row.data), historical=True)


@app.post('/api/v1/experiments', status_code=202)
def create_experiment(body: ExperimentInput, user=Depends(operator), db=Depends(session)):
    get_run(db, body.run_id)
    row = Experiment(source_id=body.run_id, config=body.model_dump(exclude={'run_id'}))
    db.add(row)
    audit(db, user, 'experiment.create', body.model_dump())
    db.commit()
    return {'id': row.id}


@app.get('/api/v1/experiments/{experiment_id}')
def get_experiment(experiment_id: int, user=Depends(current_user), db=Depends(session)):
    row = db.get(Experiment, experiment_id)
    if row is None:
        raise HTTPException(404, 'Experiment not found')
    result = db.scalar(select(ExperimentResult).where(ExperimentResult.experiment_id == row.id))
    return dict(id=row.id, status=row.status, error=row.error, result=result.data if result else None)


@app.get('/api/v1/reports/experiments/{experiment_id}')
def export(experiment_id: int, format: Literal['csv', 'json'] = 'json', user=Depends(current_user), db=Depends(session)):
    result = db.scalar(select(ExperimentResult).where(ExperimentResult.experiment_id == experiment_id))
    if result is None:
        raise HTTPException(404, 'Result not ready')
    if format == 'json':
        body = json.dumps(result.data, indent=2)
    else:
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(['metric', 'baseline', 'variant', 'delta'])
        for key in result.data['baseline']:
            writer.writerow([key, result.data['baseline'][key], result.data['variant'][key], result.data['delta'][key]])
        body = stream.getvalue()
    return Response(body, media_type='application/json' if format == 'json' else 'text/csv',
                    headers={'Content-Disposition': f'attachment; filename="experiment-{experiment_id}.{format}"'})


@app.get('/api/v1/audit')
def audit_log(user=Depends(admin), db=Depends(session)):
    return [dict(id=a.id, user_id=a.user_id, action=a.action, data=a.data, created=a.created.isoformat())
            for a in db.scalars(select(Audit).order_by(Audit.id.desc()).limit(200))]


@app.websocket('/api/v1/ws/{run_id}')
async def websocket(ws: WebSocket, run_id: int):
    if ws.headers.get('origin') not in origins:
        await ws.close(code=1008)
        return
    try:
        with SessionLocal() as db:
            authenticate(ws.cookies.get('fv_session'), db)
            get_run(db, run_id)
    except HTTPException:
        await ws.close(code=1008)
        return
    await ws.accept()
    client = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
                                 socket_connect_timeout=.2, socket_timeout=.5, retry=Retry(NoBackoff(), 0))
    pubsub = client.pubsub()
    subscribed = False
    revision = -1
    try:
        try:
            await pubsub.subscribe(f'run:{run_id}')
            subscribed = True
        except redis.RedisError:
            pass
        while True:
            # Check expiry/revocation and recover missed Pub/Sub messages from durable state.
            with SessionLocal() as db:
                authenticate(ws.cookies.get('fv_session'), db)
                row = get_run(db, run_id)
                if row.revision != revision:
                    await ws.send_json(dict(id=row.id, revision=row.revision, state=row.state, metrics=metrics(row.state)))
                    revision = row.revision
            if subscribed:
                try:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=.5)
                    if message:
                        payload = json.loads(message['data'])
                        if payload['revision'] > revision:
                            await ws.send_json(payload)
                            revision = payload['revision']
                except redis.RedisError:
                    subscribed = False
            else:
                await asyncio.sleep(.5)
            # Heartbeat detects disconnected idle clients without depending on a new tick.
            await ws.send_json({'heartbeat': True, 'revision': revision})
    except (WebSocketDisconnect, RuntimeError, HTTPException):
        pass
    finally:
        await pubsub.aclose()
        await client.aclose()
