"""Single worker process; database row locks serialize durable commands and ticks."""
import copy
import json
import logging
import os
import signal
import time

import redis
from redis.backoff import NoBackoff
from redis.retry import Retry
from sqlalchemy import select

from app.db import (Command, Event, Experiment, ExperimentResult, Incident, Mission, Order, Robot,
                    Run, SessionLocal, Snapshot, Telemetry, now)
from app.engine import command, experiment, metrics, step

log = logging.getLogger('fleetverse.worker')
bus = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
                          socket_connect_timeout=.2, socket_timeout=.5, retry=Retry(NoBackoff(), 0))


def persist(db, run, state, previous_sequence):
    run.state = state
    run.revision += 1
    run.updated = now()
    # Exact per-tick snapshots make scrubbing lossless, including command-only revisions.
    db.add(Snapshot(run_id=run.id, tick=state['tick'], revision=run.revision, data=copy.deepcopy(state)))
    for e in state['events']:
        if e['seq'] > previous_sequence:
            row = Event(run_id=run.id, seq=e['seq'], tick=e['tick'], data=e)
            db.add(row)
            db.flush()
            if e['kind'] in ('incident', 'deadlock'):
                db.add(Incident(run_id=run.id, event_id=row.id))
    robot_rows = {r.code: r for r in db.scalars(select(Robot).where(Robot.run_id == run.id))}
    for r in state['robots']:
        row = robot_rows.get(r['id'])
        if row is None:
            row = Robot(run_id=run.id, code=r['id'], data=r)
            db.add(row)
            db.flush()
            robot_rows[r['id']] = row
        row.data = copy.deepcopy(r)
        if state['tick'] % 10 == 0:
            db.add(Telemetry(robot_id=row.id, tick=state['tick'], data=copy.deepcopy(r)))
    order_rows = {o.code: o for o in db.scalars(select(Order).where(Order.run_id == run.id))}
    for o in state['orders']:
        row = order_rows.get(o['id'])
        if row is None:
            row = Order(run_id=run.id, code=o['id'], data=o)
            db.add(row)
            db.flush()
        row.data = copy.deepcopy(o)
        if o['robot']:
            mission = db.scalar(select(Mission).where(Mission.order_id == row.id))
            if mission is None:
                db.add(Mission(order_id=row.id, robot_id=robot_rows[o['robot']].id, status=o['status']))
            else:
                mission.status = o['status']


def process_run(run_id, advance=True):
    payload = None
    with SessionLocal.begin() as db:
        run = db.scalar(select(Run).where(Run.id == run_id).with_for_update())
        if not run:
            return
        state = copy.deepcopy(run.state)
        seq = state['sequence']
        commands = list(db.scalars(select(Command).where(Command.run_id == run_id, Command.status == 'pending').order_by(Command.id)))
        for row in commands:
            candidate = copy.deepcopy(state)
            try:
                command(candidate, row.kind, row.data)
                state = candidate
                row.status = 'applied'
            except (ValueError, KeyError, TypeError) as exc:
                row.status, row.error = 'rejected', str(exc)[:255]
        changed = bool(commands) or (advance and state['status'] == 'running')
        if advance:
            step(state)
        if changed:
            persist(db, run, state, seq)
            payload = dict(id=run.id, revision=run.revision, state=state, metrics=metrics(state))
    if payload:
        try:
            bus.publish(f'run:{run_id}', json.dumps(payload))
        except redis.RedisError:
            log.warning('Redis publish unavailable; API snapshot resynchronization remains available')
    return payload


def process_experiment():
    with SessionLocal.begin() as db:
        row = db.scalar(select(Experiment).where(Experiment.status == 'pending').order_by(Experiment.id).with_for_update(skip_locked=True))
        if row is None:
            return
        try:
            source = db.get(Run, row.source_id)
            result = experiment(source.state, row.config['changes'], row.config['ticks'], row.config['count'])
            db.add(ExperimentResult(experiment_id=row.id, data=result))
            row.status = 'completed'
        except (ValueError, KeyError) as exc:
            row.status, row.error = 'failed', str(exc)[:255]


def main():
    logging.basicConfig(level=logging.INFO, format='{"service":"worker","level":"%(levelname)s","message":"%(message)s"}')
    alive = True

    def stop(*_):
        nonlocal alive
        alive = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    due = {}
    while alive:
        try:
            with SessionLocal() as db:
                runs = [(r.id, r.state['speed']) for r in db.scalars(select(Run))]
            for run_id, speed in runs:
                current = time.monotonic()
                advance = current >= due.get(run_id, 0)
                process_run(run_id, advance)
                if advance:
                    due[run_id] = current + .25 / speed
            process_experiment()
            try:
                bus.set('worker:heartbeat', str(time.time()), ex=30)
            except redis.RedisError:
                pass
        except Exception:
            log.exception('Worker iteration failed; transaction rolled back')
        time.sleep(.05)


if __name__ == '__main__':
    main()
