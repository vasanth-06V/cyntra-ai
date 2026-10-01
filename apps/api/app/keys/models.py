from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ProviderName(str, Enum):
    GEMINI = "gemini"
    CLAUDE = "claude"
    GROQ = "groq"


class KeySlot(str, Enum):
    PRIMARY = "primary"
    BACKUP = "backup"


class SubmitKeyRequest(BaseModel):
    provider: ProviderName
    slot: KeySlot
    api_key: str


class ProviderKeyOut(BaseModel):
    id: str
    provider: ProviderName
    slot: KeySlot
    is_valid: bool
    last_validated_at: datetime | None
