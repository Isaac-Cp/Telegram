from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ConsentScope, ConversationStatus


class ConversationCreate(BaseModel):
    contact_id: UUID
    topic: str | None = None
    assigned_agent: str | None = None
    opened_at: datetime


class TelegramInboundMessage(BaseModel):
    telegram_user_id: int = Field(..., description="Telegram user ID from an approved inbound integration")
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    locale: str | None = None
    text: str
    external_message_id: str | None = None
    received_at: datetime
    topic: str | None = None
    consent_scopes: list[ConsentScope] = Field(default_factory=list)


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contact_id: UUID
    channel: str
    status: ConversationStatus
    topic: str | None
    assigned_agent: str | None
    opened_at: datetime
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime
