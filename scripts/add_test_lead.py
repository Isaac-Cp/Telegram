from app.db.session import SessionLocal
from app.models.lead import Lead
from app.models.user import User
from app.models.enums import ConversionStage
from datetime import datetime, timezone

with SessionLocal() as db:
    # Check if user exists
    user = db.query(User).filter(User.telegram_user_id == 8003105982).first()
    if not user:
        user = User(
            telegram_user_id=8003105982,
            username="self_test",
            influence_level="regular"
        )
        db.add(user)
        db.flush() # Get user.id
    
    lead = Lead(
        user_id=user.id,
        message_text="I need help with my IPTV subscription. It keeps buffering.",
        lead_score=95,
        opportunity_score=95,
        priority_level="HIGH",
        conversion_stage=ConversionStage.NEW,
        dm_sent=False,
        last_contact=None
    )
    db.add(lead)
    db.commit()
    print(f"Added test lead for user {user.telegram_user_id}.")
