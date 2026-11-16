import os
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))


class Session(Base):
    __tablename__ = 'sessions'
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    csrf: Mapped[str] = mapped_column(String(64))
    expires: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Warehouse(Base):
    __tablename__ = 'warehouses'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))


class Layout(Base):
    __tablename__ = 'layouts'
    id: Mapped[int] = mapped_column(primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey('warehouses.id'), index=True)
    name: Mapped[str] = mapped_column(String(120))
    data: Mapped[dict] = mapped_column(JSON)


class MapCell(Base):
    __tablename__ = 'map_cells'
    __table_args__ = (UniqueConstraint('layout_id', 'x', 'y'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    layout_id: Mapped[int] = mapped_column(ForeignKey('layouts.id', ondelete='CASCADE'), index=True)
    x: Mapped[int]
    y: Mapped[int]
    kind: Mapped[str] = mapped_column(String(20))


class Run(Base):
    __tablename__ = 'simulation_runs'
    id: Mapped[int] = mapped_column(primary_key=True)
    layout_id: Mapped[int] = mapped_column(ForeignKey('layouts.id'))
    state: Mapped[dict] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(default=0)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Command(Base):
    __tablename__ = 'commands'
    __table_args__ = (UniqueConstraint('run_id', 'key'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('simulation_runs.id'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    key: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(40))
    data: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default='pending', index=True)
    error: Mapped[str | None] = mapped_column(String(255))


class Event(Base):
    __tablename__ = 'simulation_events'
    __table_args__ = (UniqueConstraint('run_id', 'seq'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('simulation_runs.id'), index=True)
    seq: Mapped[int]
    tick: Mapped[int] = mapped_column(index=True)
    data: Mapped[dict] = mapped_column(JSON)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Snapshot(Base):
    __tablename__ = 'simulation_snapshots'
    __table_args__ = (UniqueConstraint('run_id', 'revision'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('simulation_runs.id'), index=True)
    tick: Mapped[int] = mapped_column(index=True)
    revision: Mapped[int]
    data: Mapped[dict] = mapped_column(JSON)


class Robot(Base):
    __tablename__ = 'robots'
    __table_args__ = (UniqueConstraint('run_id', 'code'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('simulation_runs.id'), index=True)
    code: Mapped[str] = mapped_column(String(20))
    data: Mapped[dict] = mapped_column(JSON)


class Telemetry(Base):
    __tablename__ = 'robot_telemetry'
    id: Mapped[int] = mapped_column(primary_key=True)
    robot_id: Mapped[int] = mapped_column(ForeignKey('robots.id'), index=True)
    tick: Mapped[int] = mapped_column(index=True)
    data: Mapped[dict] = mapped_column(JSON)


class Order(Base):
    __tablename__ = 'orders'
    __table_args__ = (UniqueConstraint('run_id', 'code'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('simulation_runs.id'), index=True)
    code: Mapped[str] = mapped_column(String(20))
    data: Mapped[dict] = mapped_column(JSON)


class Mission(Base):
    __tablename__ = 'missions'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'), unique=True)
    robot_id: Mapped[int] = mapped_column(ForeignKey('robots.id'))
    status: Mapped[str] = mapped_column(String(30))


class Incident(Base):
    __tablename__ = 'incidents'
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey('simulation_events.id'), unique=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('simulation_runs.id'), index=True)


class Experiment(Base):
    __tablename__ = 'experiments'
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey('simulation_runs.id'))
    config: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    error: Mapped[str | None] = mapped_column(String(255))


class ExperimentResult(Base):
    __tablename__ = 'experiment_results'
    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey('experiments.id'), unique=True)
    data: Mapped[dict] = mapped_column(JSON)


class Audit(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(100))
    data: Mapped[dict] = mapped_column(JSON)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


url = os.getenv('DATABASE_URL', 'sqlite:///./fleetverse.db')
engine = create_engine(url, pool_pre_ping=True, **({'connect_args': {'check_same_thread': False}} if url.startswith('sqlite') else {}))
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def session():
    with SessionLocal() as db:
        yield db
