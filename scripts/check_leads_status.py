from app.db.session import SessionLocal
from app.models.lead import Lead
from sqlalchemy import select

def check_leads():
    with SessionLocal() as db:
        leads = db.execute(select(Lead)).scalars().all()
        print(f"Total leads: {len(leads)}")
        for l in leads:
            print(f"ID: {l.id}, Score: {l.lead_score}, Temp: {l.lead_temperature}, Priority: {l.priority_level}, DM Sent: {l.dm_sent}")

if __name__ == "__main__":
    check_leads()
