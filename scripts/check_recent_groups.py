from app.db.session import SessionLocal
from app.models.group import Group
from sqlalchemy import select

with SessionLocal() as db:
    groups = db.execute(select(Group).order_by(Group.id.desc()).limit(10)).scalars().all()
    for g in groups:
        print(f"ID: {g.id}, Name: {g.name}, Status: {g.status}, Score: {g.authority_score}")
