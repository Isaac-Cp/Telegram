import sys
from app.db.session import SessionLocal
from app.models.group import Group
from sqlalchemy import select

# Ensure utf-8 output
sys.stdout.reconfigure(encoding='utf-8')

def check_groups():
    with SessionLocal() as db:
        groups = db.execute(select(Group).where(Group.joined == True)).scalars().all()
        print(f"Total joined groups: {len(groups)}")
        for g in groups:
            print(f"ID: {g.id}, Name: {g.name}, Status: {g.status}, Joined: {g.joined}")

if __name__ == "__main__":
    check_groups()
