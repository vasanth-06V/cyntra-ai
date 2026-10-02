import pytest
from fastapi import HTTPException

from app.db import keys as keys_repo
from app.keys import service
from app.providers.base import ProviderRateLimitError, ProviderUnavailableError


class _Adapter:
    def __init__(self, outcome):
        self.outcome = outcome

    async def validate(self, api_key):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class _DB:
    def __init__(self):
        self.upserts = []

    def table(self, name):
        db = self

        class T:
            def upsert(self, data, on_conflict=None):
                db.upserts.append(data)
                return self

            def execute(self):
                class R:
                    data = [{"id": "k1", "provider": "gemini", "slot": "primary", "is_valid": True}]

                return R()

        return T()


@pytest.fixture
def db(monkeypatch):
    fake = _DB()
    monkeypatch.setattr(keys_repo, "get_supabase", lambda: fake)
    monkeypatch.setattr(service, "encrypt_key", lambda k: f"enc:{k}")
    return fake


@pytest.mark.asyncio
async def test_valid_key_is_stored_encrypted_and_marked_valid(monkeypatch, db):
    monkeypatch.setattr(service, "get_adapter", lambda p: _Adapter(True))

    row = await service.submit_key("u", "gemini", "primary", "secret")

    assert row["is_valid"] is True
    assert db.upserts[0]["encrypted_key"] == "enc:secret"
    assert db.upserts[0]["is_valid"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outcome,code",
    [(False, 400), (ProviderRateLimitError("x"), 429), (ProviderUnavailableError("x"), 503)],
)
async def test_unconfirmed_key_is_never_stored_so_a_working_key_survives(monkeypatch, db, outcome, code):
    monkeypatch.setattr(service, "get_adapter", lambda p: _Adapter(outcome))

    with pytest.raises(HTTPException) as exc:
        await service.submit_key("u", "gemini", "primary", "secret")

    assert exc.value.status_code == code
    assert db.upserts == []
