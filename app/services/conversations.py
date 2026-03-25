from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent
from app.models.consent import Consent
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.enums import (
    ConsentChannel,
    ConsentScope,
    ContactStatus,
    ConversationStatus,
    EventType,
    MessageDirection,
)
from app.schemas.conversation import ConversationCreate, TelegramInboundMessage


def create_conversation(db: Session, payload: ConversationCreate) -> Conversation:
    conversation = Conversation(
        contact_id=str(payload.contact_id),
        topic=payload.topic,
        assigned_agent=payload.assigned_agent,
        opened_at=payload.opened_at,
        status=ConversationStatus.OPEN,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def ingest_inbound_message(db: Session, payload: TelegramInboundMessage) -> Conversation:
    contact = (
        db.query(Contact)
        .filter(Contact.telegram_user_id == payload.telegram_user_id)
        .one_or_none()
    )

    if contact is None:
        contact = Contact(
            telegram_user_id=payload.telegram_user_id,
            username=payload.username,
            first_name=payload.first_name,
            last_name=payload.last_name,
            locale=payload.locale,
            source="telegram_bot",
            status=ContactStatus.ACTIVE,
            last_inbound_at=payload.received_at,
        )
        db.add(contact)
        db.flush()
        db.add(
            ActivityEvent(
                contact_id=contact.id,
                event_type=EventType.USER_STARTED_CHAT,
                occurred_at=payload.received_at,
                metadata_json={"source": "telegram_bot"},
            )
        )
    else:
        contact.username = payload.username or contact.username
        contact.first_name = payload.first_name or contact.first_name
        contact.last_name = payload.last_name or contact.last_name
        contact.locale = payload.locale or contact.locale
        contact.last_inbound_at = payload.received_at
        if contact.status == ContactStatus.NEW:
            contact.status = ContactStatus.ACTIVE

    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.contact_id == contact.id,
            Conversation.status.in_([ConversationStatus.OPEN, ConversationStatus.PENDING]),
        )
        .order_by(Conversation.created_at.desc())
        .first()
    )

    if conversation is None:
        conversation = Conversation(
            contact_id=contact.id,
            topic=payload.topic,
            opened_at=payload.received_at,
            status=ConversationStatus.OPEN,
        )
        db.add(conversation)
        db.flush()

    db.add(
        Message(
            conversation_id=conversation.id,
            contact_id=contact.id,
            direction=MessageDirection.INBOUND,
            external_message_id=payload.external_message_id,
            body=payload.text,
            sent_at=payload.received_at,
            metadata_json={"channel": "telegram"},
        )
    )

    for scope in payload.consent_scopes:
        existing = (
            db.query(Consent)
            .filter(
                Consent.contact_id == contact.id,
                Consent.scope == scope,
                Consent.channel == ConsentChannel.TELEGRAM,
                Consent.revoked_at.is_(None),
            )
            .first()
        )
        if existing is None:
            db.add(
                Consent(
                    contact_id=contact.id,
                    channel=ConsentChannel.TELEGRAM,
                    scope=scope,
                    source="telegram_bot",
                    proof_text="Inbound opt-in captured during Telegram conversation",
                    granted_at=payload.received_at,
                )
            )
            db.add(
                ActivityEvent(
                    contact_id=contact.id,
                    event_type=EventType.CONSENT_GRANTED,
                    occurred_at=payload.received_at,
                    metadata_json={"scope": scope.value, "source": "telegram_bot"},
                )
            )

    db.add(
        ActivityEvent(
            contact_id=contact.id,
            event_type=EventType.MESSAGE_RECEIVED,
            occurred_at=payload.received_at,
            metadata_json={"conversation_id": conversation.id},
        )
    )
    db.commit()
    db.refresh(conversation)
    return conversation
