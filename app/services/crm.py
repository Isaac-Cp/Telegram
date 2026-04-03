import logging
from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, and_
from app.db.session import SessionLocal
from app.models.lead import Lead
from app.models.lead_conversation import LeadConversation
from app.models.enums import ConversionStage

logger = logging.getLogger(__name__)

class LeadCRMService:
    def update_lead_status(self, lead_id: str, status: ConversionStage):
        """Updates the status of a lead and tracks timestamps."""
        with SessionLocal() as db:
            lead = db.execute(select(Lead).where(Lead.id == lead_id)).scalar_one_or_none()
            if lead:
                old_status = lead.conversion_stage
                lead.conversion_stage = status
                
                # Track first contact
                if status == ConversionStage.CONTACTED and not lead.first_contact:
                    lead.first_contact = datetime.utcnow()
                
                lead.last_contact = datetime.utcnow()
                db.commit()
                logger.info(f"Lead {lead_id} status updated from {old_status} to {status}")

    def store_conversation_history(self, lead_id: str, message: str, sender: str):
        """Records a message in the lead's conversation history."""
        with SessionLocal() as db:
            new_conv = LeadConversation(
                lead_id=lead_id,
                message=message,
                sender=sender,
                timestamp=datetime.utcnow()
            )
            db.add(new_conv)
            
            # Also update last_contact on lead
            lead = db.execute(select(Lead).where(Lead.id == lead_id)).scalar_one_or_none()
            if lead:
                lead.last_contact = datetime.utcnow()
                
                # If user responds, update status
                if sender.lower() != "aiden" and lead.conversion_stage == ConversionStage.CONTACTED:
                    lead.conversion_stage = ConversionStage.RESPONDED
            
            db.commit()
            logger.debug(f"Stored conversation for lead {lead_id} from {sender}")

    def get_lead_history(self, lead_id: str) -> List[LeadConversation]:
        """Retrieves full conversation history for a lead."""
        with SessionLocal() as db:
            result = db.execute(
                select(LeadConversation)
                .where(LeadConversation.lead_id == lead_id)
                .order_by(LeadConversation.timestamp.asc())
            ).scalars().all()
            return list(result)

    def is_already_contacted(self, user_id: int) -> bool:
        """Prevents duplicate contact by checking if user_id was already handled."""
        with SessionLocal() as db:
            lead = db.execute(
                select(Lead).where(
                    and_(
                        Lead.telegram_user_id == user_id,
                        Lead.conversion_stage != ConversionStage.NEW
                    )
                )
            ).scalar_one_or_none()
            return lead is not None

lead_crm_service = LeadCRMService()
