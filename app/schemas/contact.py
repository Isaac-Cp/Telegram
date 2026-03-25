from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import ConsentChannel, ConsentScope, ContactStatus


class ContactCreate(BaseModel):
    telegram_user_id: int | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    locale: str | None = None
    source: str = "telegram"


class ContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    telegram_user_id: int | None
    username: str | None
    first_name: str | None
    last_name: str | None
    locale: str | None
    source: str
    status: ContactStatus
    last_inbound_at: datetime | None
    last_outbound_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConsentCreate(BaseModel):
    contact_id: UUID
    channel: ConsentChannel = ConsentChannel.TELEGRAM
    scope: ConsentScope
    source: str = "telegram_bot"
    proof_text: str | None = None
    granted_at: datetime


class ConsentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contact_id: UUID
    channel: ConsentChannel
    scope: ConsentScope
    source: str
    proof_text: str | None
    granted_at: datetime
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime

