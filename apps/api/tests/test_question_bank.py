import pytest
from fastapi import HTTPException

from app.interviews import question_bank


async def _async_value(value):
    return value


class _FakeTable:
    def __init__(self, name, stored):
        self.name = name
        self.stored = stored
        self._filters = {}

    def insert(self, data):
        self.stored.setdefault("inserts", []).append((self.name, data))
        self._last_insert = data
        return self

    def update(self, data):
        self.stored.setdefault("updates", []).append((self.name, data))
        return self

    def delete(self):
        self.stored.setdefault("deletes", []).append(self.name)
        return self

    def select(self, *a, **kw):
        return self

    def eq(self, field, value):
        self._filters[field] = value
        return self

    def maybe_single(self):
        return self

    def execute(self):
        class _Result:
            data = [{"id": "question-1"}]

        return _Result()


class _FakeSupabase:
    def __init__(self, stored):
        self.stored = stored

    def table(self, name):
        return _FakeTable(name, self.stored)


@pytest.fixture
def stored():
    return {}


@pytest.fixture(autouse=True)
def _patch_embed(monkeypatch):
    async def fake_embed_text(api_key, text):
        return [0.1, 0.2]

    monkeypatch.setattr(question_bank, "embed_text", fake_embed_text)
    monkeypatch.setattr(question_bank, "decrypt_key", lambda encrypted: encrypted)


@pytest.mark.asyncio
async def test_create_question_denied_for_plain_user(monkeypatch, stored):
    monkeypatch.setattr(question_bank, "_is_owner_or_has_permission", lambda *a: _async_value(False))

    with pytest.raises(HTTPException) as exc_info:
        await question_bank.create_question("user-1", "coding", "Reverse a linked list", None, None)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_create_question_requires_gemini_key(monkeypatch, stored):
    monkeypatch.setattr(question_bank, "_is_owner_or_has_permission", lambda *a: _async_value(True))
    monkeypatch.setattr(question_bank, "get_key_row", lambda *a, **kw: _async_value(None))

    with pytest.raises(HTTPException) as exc_info:
        await question_bank.create_question("owner-1", "coding", "Reverse a linked list", None, None)

    assert exc_info.value.status_code == 412


@pytest.mark.asyncio
async def test_create_question_succeeds_for_owner_and_embeds(monkeypatch, stored):
    monkeypatch.setattr(question_bank, "_is_owner_or_has_permission", lambda *a: _async_value(True))
    monkeypatch.setattr(
        question_bank,
        "get_key_row",
        lambda *a, **kw: _async_value({"id": "key-1", "encrypted_key": "gemini-key"}),
    )
    monkeypatch.setattr(question_bank, "get_supabase", lambda: _FakeSupabase(stored))

    result = await question_bank.create_question(
        "owner-1", "coding", "Reverse a linked list", [{"input": "1,2,3", "output": "3,2,1"}], ["lists"]
    )

    assert result == {"id": "question-1"}
    table_name, inserted = stored["inserts"][0]
    assert table_name == "question_bank"
    assert inserted["embedding"] == [0.1, 0.2]
    assert inserted["created_by"] == "owner-1"


@pytest.mark.asyncio
async def test_delete_question_denied_without_permission(monkeypatch, stored):
    monkeypatch.setattr(question_bank, "_is_owner_or_has_permission", lambda *a: _async_value(False))

    with pytest.raises(HTTPException) as exc_info:
        await question_bank.delete_question("user-1", "question-1")

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_is_owner_or_has_permission_true_for_owner(monkeypatch, stored):
    class _RoleTable(_FakeTable):
        def execute(self):
            class _Result:
                data = {"role": "owner"}

            return _Result()

    class _Supabase:
        def table(self, name):
            return _RoleTable(name, stored)

    monkeypatch.setattr(question_bank, "get_supabase", lambda: _Supabase())

    assert await question_bank._is_owner_or_has_permission("owner-1", "manage_question_bank")


@pytest.mark.asyncio
async def test_is_owner_or_has_permission_false_for_plain_user(monkeypatch, stored):
    class _RoleTable(_FakeTable):
        def execute(self):
            class _Result:
                data = {"role": "user"}

            return _Result()

    class _Supabase:
        def table(self, name):
            return _RoleTable(name, stored)

    monkeypatch.setattr(question_bank, "get_supabase", lambda: _Supabase())

    assert not await question_bank._is_owner_or_has_permission("user-1", "manage_question_bank")
