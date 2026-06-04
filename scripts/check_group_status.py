from app.db.session import SessionLocal
from app.models.group import Group
from sqlalchemy import select

def check_groups():
    with SessionLocal() as db:
        groups = db.execute(select(Group)).scalars().all()
        print(f"Total groups: {len(groups)}")
        for g in groups:
            print(f"ID: {g.id}, Name: {g.name}, Status: {g.status}, Joined: {g.joined}, Eligible: {g.eligible_for_join}")

if __name__ == "__main__":
    check_groups()
