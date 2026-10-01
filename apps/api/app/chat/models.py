from datetime import datetime

from pydantic import BaseModel

from app.keys.models import ProviderName


class CreateConversationRequest(BaseModel):
    title: str | None = None


class ConversationOut(BaseModel):
    id: str
    title: str | None
    created_at: datetime


class ChatMessageOut(BaseModel):
    id: str
    role: str
    provider: str | None
    content: str
    created_at: datetime


class SendMessageRequest(BaseModel):
    provider: ProviderName
    content: str
