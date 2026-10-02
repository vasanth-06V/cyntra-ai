"""Shared fixtures: the real FastAPI app with Supabase and the provider
adapters swapped for in-memory fakes and the JWT dependency overridden.

Users are identified per request by an X-Test-User header (a uuid), so one
test can act as several users. A request without the header gets the same
401 the real dependency would give.
"""

import uuid
from types import SimpleNamespace

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import Header, HTTPException

from app.core import db as core_db
from app.core.config import settings
from app.core.security import AuthenticatedUser, encrypt_key, get_current_user
from app.llm import gateway
from app.llm.limiter import limiter
from app.main import app
from app.providers import registry
from app.rag import embeddings

from .fakes import FakeAdapter, FakeSupabase

USER_A = "11111111-1111-1111-1111-111111111111"
USER_B = "22222222-2222-2222-2222-222222222222"
OWNER = "33333333-3333-3333-3333-333333333333"
ADMIN_WITH_PERM = "44444444-4444-4444-4444-444444444444"
ADMIN_NO_PERM = "55555555-5555-5555-5555-555555555555"


def as_user(user_id: str) -> dict:
    return {"X-Test-User": user_id}


async def _fake_current_user(x_test_user: str | None = Header(default=None)):
    if not x_test_user:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return AuthenticatedUser(user_id=x_test_user, email=f"{x_test_user[:4]}@example.com")


@pytest.fixture
def env(monkeypatch):
    db = FakeSupabase()
    core_db.get_supabase.cache_clear()
    monkeypatch.setattr(core_db, "create_client", lambda *a, **kw: db)

    adapters = {n: FakeAdapter(n) for n in ("gemini", "claude", "groq")}
    for name, adapter in adapters.items():
        monkeypatch.setitem(registry._ADAPTERS, name, adapter)
    monkeypatch.setattr(embeddings, "_gemini", adapters["gemini"])

    monkeypatch.setattr(settings, "key_encryption_secret", Fernet.generate_key().decode())
    monkeypatch.setattr(gateway, "_RETRY_DELAYS", (0.0, 0.0))
    limiter._windows.clear()
    limiter._locks.clear()

    app.dependency_overrides[get_current_user] = _fake_current_user
    yield SimpleNamespace(
        db=db, gemini=adapters["gemini"], claude=adapters["claude"], groq=adapters["groq"],
    )
    app.dependency_overrides.clear()
    core_db.get_supabase.cache_clear()


@pytest.fixture
async def client(env):
    # raise_app_exceptions=False so an unhandled server error shows up as the
    # 500 a real client would see, instead of re-raising into the test.
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def seed_key(env, user_id: str, provider: str, slot: str, raw: str, valid: bool = True) -> dict:
    return env.db.seed(
        "provider_keys", user_id=user_id, provider=provider, slot=slot,
        encrypted_key=encrypt_key(raw), is_valid=valid,
    )


def seed_processed_resume(env, user_id: str, text: str | None = None, digest: str | None = "Digest.") -> dict:
    text = text or (
        "Jane Doe\njane@example.com\n+1 415 555 0100\n\nExperience\n"
        "Senior backend engineer building Python services on Kubernetes for eight years.\n\n"
        "Skills\nPython, Kubernetes, PostgreSQL, Docker\n"
    )
    resume = env.db.seed(
        "resumes", user_id=user_id, file_key=f"resumes/{user_id}/r.docx",
        parsed_text=text, digest=digest,
    )
    env.db.seed("resume_chunks", resume_id=resume["id"], chunk_index=0, content=text[:200],
                embedding=[0.1, 0.2, 0.3])
    return resume


def new_id() -> str:
    return str(uuid.uuid4())
