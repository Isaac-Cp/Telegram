import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal
from app.models.lead import Lead
from app.models.user import User
from app.services.lead_scoring import lead_scoring

async def test_scoring():
    print("Testing 5-Layer Dynamic Scoring...")
    
    with SessionLocal() as db:
        # 1. Create a dummy user
        user = User(
            telegram_user_id=123456789,
            username="test_buyer",
            message_frequency=20 # High engagement
        )
        db.add(user)
        db.flush()
        
        # 2. Create a High Intent Lead
        lead1 = Lead(
            user_id=user.id,
            message_text="Can anyone recommend a provider? Need a new IPTV, mine is constant buffering.",
            timestamp=datetime.utcnow(),
            conversion_stage="NEW"
        )
        db.add(lead1)
        db.flush()
        
        # 3. Create a Low Intent Lead
        lead2 = Lead(
            user_id=user.id,
            message_text="Just chatting about the game last night.",
            timestamp=datetime.utcnow() - timedelta(days=5), # Old lead
            conversion_stage="NEW"
        )
        db.add(lead2)
        db.flush()
        
        db.commit()
        
        print(f"Created Lead 1: {lead1.id}")
        print(f"Created Lead 2: {lead2.id}")
        
        # 4. Run Scoring
        score1 = await lead_scoring.calculate_predictive_buyer_score(lead1.id, lead1.message_text)
        score2 = await lead_scoring.calculate_predictive_buyer_score(lead2.id, lead2.message_text)
        
        print(f"Lead 1 Score: {score1} (Temp: {lead1.lead_temperature})")
        print(f"Lead 2 Score: {score2} (Temp: {lead2.lead_temperature})")
        
        # 5. Test Decay
        print("Testing Decay...")
        await lead_scoring.decay_lead_scores()
        db.refresh(lead2)
        print(f"Lead 2 Score after decay: {lead2.lead_score} (Recency: {lead2.recency_score})")

if __name__ == "__main__":
    asyncio.run(test_scoring())
