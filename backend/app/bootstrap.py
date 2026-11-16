import os

from argon2 import PasswordHasher
from sqlalchemy import select

from app.db import Layout, MapCell, SessionLocal, User, Warehouse
from app.engine import layouts


def save_cells(db, layout):
    for kind in ('blocked', 'restricted', 'pickup', 'dropoff', 'chargers', 'checkpoints'):
        for x, y in layout.data.get(kind, []):
            db.add(MapCell(layout_id=layout.id, x=x, y=y, kind=kind))


def bootstrap():
    with SessionLocal.begin() as db:
        if not db.scalar(select(Warehouse.id).limit(1)):
            warehouse = Warehouse(name='Northstar logistics / simulation facility')
            db.add(warehouse)
            db.flush()
            for data in layouts():
                layout = Layout(warehouse_id=warehouse.id, name=data['name'], data=data)
                db.add(layout)
                db.flush()
                save_cells(db, layout)
        if not db.scalar(select(User.id).limit(1)):
            demo = os.getenv('DEMO_MODE', 'false').lower() == 'true'
            password = os.getenv('ADMIN_PASSWORD')
            if not password and not demo:
                raise RuntimeError('Set ADMIN_PASSWORD (12+ characters) or explicitly enable DEMO_MODE')
            if not demo and len(password) < 12:
                raise RuntimeError('ADMIN_PASSWORD must be at least 12 characters')
            for username, role in ([('admin', 'ADMIN'), ('operator', 'OPERATOR'), ('viewer', 'VIEWER')] if demo else [('admin', 'ADMIN')]):
                db.add(User(username=username, role=role, password=PasswordHasher().hash(password or 'fleetverse-demo')))


if __name__ == '__main__':
    bootstrap()
