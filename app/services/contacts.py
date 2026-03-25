from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.activity_event import ActivityEvent
from app.models.consent import Consent
from app.models.contact import Contact
from app.models.enums import EventType
from app.schemas.contact import ConsentCreate, ContactCreate


def create_contact(db: Session, payload: ContactCreate) -> Contact:
    contact = Contact(**payload.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def list_contacts(db: Session) -> list[Contact]:
    return db.query(Contact).order_by(Contact.created_at.desc()).all()


def get_contact(db: Session, contact_id: str) -> Contact | None:
    return db.get(Contact, str(contact_id))


def create_consent(db: Session, payload: ConsentCreate) -> Consent:
    consent = Consent(
        contact_id=str(payload.contact_id),
        channel=payload.channel,
        scope=payload.scope,
        source=payload.source,
        proof_text=payload.proof_text,
        granted_at=payload.granted_at,
    )
    db.add(consent)
    db.add(
        ActivityEvent(
            contact_id=str(payload.contact_id),
            event_type=EventType.CONSENT_GRANTED,
            occurred_at=utcnow(),
            metadata_json={"scope": payload.scope.value, "source": payload.source},
        )
    )
    db.commit()
    db.refresh(consent)
    return consent

