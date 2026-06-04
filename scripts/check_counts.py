from app.db.session import SessionLocal
from app.models.lead import Lead
from app.models.group import Group
from sqlalchemy import func

def check_counts():
    with SessionLocal() as db:
        lead_count = db.query(func.count(Lead.id)).scalar()
        group_count = db.query(func.count(Group.id)).scalar()
        approved_groups = db.query(func.count(Group.id)).filter(Group.status == "APPROVED").scalar()
        contacted_leads = db.query(func.count(Lead.id)).filter(Lead.dm_sent == True).scalar()
        
        print(f"Total Leads: {lead_count}")
        print(f"Total Groups: {group_count}")
        print(f"Approved Groups: {approved_groups}")
        print(f"DMs Sent: {contacted_leads}")

if __name__ == "__main__":
    check_counts()
