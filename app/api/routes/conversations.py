from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.conversation import (
    ConversationCreate,
    ConversationRead,
    TelegramInboundMessage,
)
from app.services.conversations import create_conversation, ingest_inbound_message

router = APIRouter()


@router.post("/conversations", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation_endpoint(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
) -> ConversationRead:
    return create_conversation(db, payload)


@router.post("/messages/inbound", response_model=ConversationRead, status_code=status.HTTP_202_ACCEPTED)
def ingest_inbound_message_endpoint(
    payload: TelegramInboundMessage,
    db: Session = Depends(get_db),
) -> ConversationRead:
    return ingest_inbound_message(db, payload)

