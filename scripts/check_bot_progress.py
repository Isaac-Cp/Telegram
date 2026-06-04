from app.db.session import SessionLocal
from app.models.group import Group
from app.models.lead import Lead
from sqlalchemy import select, func

with SessionLocal() as db:
    joined_groups = db.execute(select(func.count(Group.id)).where(Group.joined == True)).scalar() or 0
    dms_sent = db.execute(select(func.count(Lead.id)).where(Lead.dm_sent == True)).scalar() or 0
    total_leads = db.execute(select(func.count(Lead.id))).scalar() or 0
    
    print(f"BOT PROGRESS REPORT:")
    print(f"- Groups Joined: {joined_groups}")
    print(f"- DMs Sent: {dms_sent}")
    print(f"- Total Leads Scored: {total_leads}")
    
    if joined_groups > 0:
        recent_group = db.execute(select(Group).where(Group.joined == True).order_by(Group.updated_at.desc())).scalars().first()
        print(f"- Most recent group join: {recent_group.name} at {recent_group.updated_at}")
    
    if dms_sent > 0:
        recent_dm = db.execute(select(Lead).where(Lead.dm_sent == True).order_by(Lead.updated_at.desc())).scalars().first()
        print(f"- Most recent DM sent to: @{recent_dm.user.username if recent_dm.user else 'Anonymous'} at {recent_dm.updated_at}")
