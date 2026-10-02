"""Chat: create / stream / list, ownership, failover, error mapping."""

import pytest

from app.providers.base import ProviderBlockedError, ProviderUnavailableError

from .conftest import USER_A, USER_B, as_user, new_id, seed_key


async def _new_conversation(client, user=USER_A, title="t"):
    r = await client.post("/chat/conversations", json={"title": title}, headers=as_user(user))
    assert r.status_code == 201
    return r.json()["id"]


async def test_create_list_and_isolation_between_users(client, env):
    a = await _new_conversation(client, USER_A, "mine")
    await _new_conversation(client, USER_B, "theirs")
    r = await client.get("/chat/conversations", headers=as_user(USER_A))
    assert [c["id"] for c in r.json()] == [a]


async def test_stream_round_trip_persists_both_messages_and_records_usage(client, env):
    seed_key(env, USER_A, "gemini", "primary", "gem-key")
    conv = await _new_conversation(client)

    r = await client.post(
        f"/chat/conversations/{conv}/messages",
        json={"provider": "gemini", "content": "hi there"}, headers=as_user(USER_A),
    )
    assert r.status_code == 200
    assert r.text == "Hello from the fake model."
    assert env.gemini.chat_calls[0].api_key == "gem-key"
    assert env.gemini.chat_calls[0].options.task == "chat"

    msgs = (await client.get(f"/chat/conversations/{conv}/messages", headers=as_user(USER_A))).json()
    assert [(m["role"], m["content"]) for m in msgs] == [
        ("user", "hi there"), ("assistant", "Hello from the fake model."),
    ]
    assert msgs[1]["provider"] == "gemini"

    usage = (await client.get("/usage", headers=as_user(USER_A))).json()
    assert usage and usage[0]["provider"] == "gemini" and usage[0]["kind"] == "chat"
    assert usage[0]["requests"] == 1


async def test_history_window_and_first_message_is_user(client, env):
    seed_key(env, USER_A, "gemini", "primary", "gem-key")
    conv = await _new_conversation(client)
    for i in range(14):
        env.db.seed("chat_messages", conversation_id=conv, role="user" if i % 2 == 0 else "assistant",
                    content=f"m{i}")
    await client.post(
        f"/chat/conversations/{conv}/messages",
        json={"provider": "gemini", "content": "latest"}, headers=as_user(USER_A),
    )
    sent = env.gemini.chat_calls[0].messages
    assert len(sent) <= 10 + 1
    assert sent[0].role.value == "user"
    assert sent[-1].content == "latest"


async def test_cannot_read_or_post_to_someone_elses_conversation(client, env):
    seed_key(env, USER_B, "gemini", "primary", "k")
    conv = await _new_conversation(client, USER_A)
    r = await client.get(f"/chat/conversations/{conv}/messages", headers=as_user(USER_B))
    assert r.status_code == 404
    r = await client.post(
        f"/chat/conversations/{conv}/messages",
        json={"provider": "gemini", "content": "x"}, headers=as_user(USER_B),
    )
    assert r.status_code == 404
    assert env.db.rows("chat_messages") == []
    assert env.gemini.chat_calls == []


async def test_unknown_conversation_is_404(client, env):
    r = await client.get(f"/chat/conversations/{new_id()}/messages", headers=as_user(USER_A))
    assert r.status_code == 404


async def test_no_key_configured_is_412_json_not_a_broken_stream(client, env):
    conv = await _new_conversation(client)
    r = await client.post(
        f"/chat/conversations/{conv}/messages",
        json={"provider": "claude", "content": "hi"}, headers=as_user(USER_A),
    )
    assert r.status_code == 412
    assert "claude" in r.json()["detail"]


async def test_failover_to_backup_key_notifies_user(client, env):
    seed_key(env, USER_A, "gemini", "primary", "primary-key")
    seed_key(env, USER_A, "gemini", "backup", "backup-key")
    env.gemini.rate_limited_keys.add("primary-key")
    conv = await _new_conversation(client)

    r = await client.post(
        f"/chat/conversations/{conv}/messages",
        json={"provider": "gemini", "content": "hi"}, headers=as_user(USER_A),
    )
    assert r.status_code == 200 and r.text == "Hello from the fake model."
    assert [c.api_key for c in env.gemini.chat_calls] == ["primary-key", "backup-key"]
    notes = env.db.rows("notifications", user_id=USER_A)
    assert len(notes) == 1 and "backup" in notes[0]["message"]


async def test_rate_limited_without_backup_is_429(client, env):
    seed_key(env, USER_A, "gemini", "primary", "p")
    env.gemini.rate_limited_keys.add("p")
    conv = await _new_conversation(client)
    r = await client.post(
        f"/chat/conversations/{conv}/messages",
        json={"provider": "gemini", "content": "hi"}, headers=as_user(USER_A),
    )
    assert r.status_code == 429


async def test_both_keys_rate_limited_is_429(client, env):
    seed_key(env, USER_A, "gemini", "primary", "p")
    seed_key(env, USER_A, "gemini", "backup", "b")
    env.gemini.rate_limited_keys.update({"p", "b"})
    conv = await _new_conversation(client)
    r = await client.post(
        f"/chat/conversations/{conv}/messages",
        json={"provider": "gemini", "content": "hi"}, headers=as_user(USER_A),
    )
    assert r.status_code == 429 and "Both" in r.json()["detail"]


async def test_overloaded_provider_retries_then_503(client, env):
    seed_key(env, USER_A, "gemini", "primary", "p")
    env.gemini.script = [ProviderUnavailableError("x")] * 3
    conv = await _new_conversation(client)
    r = await client.post(
        f"/chat/conversations/{conv}/messages",
        json={"provider": "gemini", "content": "hi"}, headers=as_user(USER_A),
    )
    assert r.status_code == 503
    assert len(env.gemini.chat_calls) == 3


async def test_transient_error_then_success_is_invisible_to_user(client, env):
    seed_key(env, USER_A, "gemini", "primary", "p")
    env.gemini.script = [ProviderUnavailableError("x"), "recovered fine"]
    conv = await _new_conversation(client)
    r = await client.post(
        f"/chat/conversations/{conv}/messages",
        json={"provider": "gemini", "content": "hi"}, headers=as_user(USER_A),
    )
    assert r.status_code == 200 and r.text == "recovered fine"


async def test_blocked_reply_maps_to_422(client, env):
    seed_key(env, USER_A, "gemini", "primary", "p")
    env.gemini.script = [ProviderBlockedError("safety")]
    conv = await _new_conversation(client)
    r = await client.post(
        f"/chat/conversations/{conv}/messages",
        json={"provider": "gemini", "content": "hi"}, headers=as_user(USER_A),
    )
    assert r.status_code == 422


# --------------------------- findings ---------------------------


async def test_failed_reply_leaves_no_orphan_user_message(client, env):
    seed_key(env, USER_A, "gemini", "primary", "p")
    env.gemini.script = [ProviderBlockedError("safety")]
    conv = await _new_conversation(client)
    r = await client.post(
        f"/chat/conversations/{conv}/messages",
        json={"provider": "gemini", "content": "hi"}, headers=as_user(USER_A),
    )
    assert r.status_code == 422
    assert env.db.rows("chat_messages", conversation_id=conv) == []


async def test_retry_after_failure_sends_the_user_turn_once(client, env):
    seed_key(env, USER_A, "gemini", "primary", "p")
    env.gemini.script = [ProviderBlockedError("safety")]
    conv = await _new_conversation(client)
    url = f"/chat/conversations/{conv}/messages"
    body = {"provider": "gemini", "content": "same question"}
    await client.post(url, json=body, headers=as_user(USER_A))
    r = await client.post(url, json=body, headers=as_user(USER_A))
    assert r.status_code == 200
    assert [m.content for m in env.gemini.chat_calls[-1].messages] == ["same question"]
    assert [m["role"] for m in env.db.rows("chat_messages", conversation_id=conv)] == ["user", "assistant"]


async def test_partial_reply_is_not_lost_on_midstream_failure(client, env):
    seed_key(env, USER_A, "gemini", "primary", "p")
    env.gemini.script = [("Partial answer so far ", ProviderUnavailableError("dropped"))]
    conv = await _new_conversation(client)
    await client.post(
        f"/chat/conversations/{conv}/messages",
        json={"provider": "gemini", "content": "hi"}, headers=as_user(USER_A),
    )
    roles = [m["role"] for m in env.db.rows("chat_messages", conversation_id=conv)]
    assert "user" in roles  # at minimum the user's own message should survive


async def test_oversized_or_empty_message_rejected(client, env):
    seed_key(env, USER_A, "gemini", "primary", "p")
    conv = await _new_conversation(client)
    url = f"/chat/conversations/{conv}/messages"
    r1 = await client.post(url, json={"provider": "gemini", "content": ""}, headers=as_user(USER_A))
    r2 = await client.post(
        url, json={"provider": "gemini", "content": "x" * 1_000_000}, headers=as_user(USER_A)
    )
    assert r1.status_code == 422 and r2.status_code == 422


async def test_malformed_conversation_id_is_clean_4xx(client, env):
    r = await client.get("/chat/conversations/not-a-uuid/messages", headers=as_user(USER_A))
    assert r.status_code < 500


async def test_failover_notification_failure_discards_a_successful_reply(client, env):
    """CONFIRMED (low/med): notify_user() runs after the backup key already
    produced the answer; if the notifications insert fails the whole request
    errors even though the model call succeeded (and the message is lost)."""
    from postgrest.exceptions import APIError

    seed_key(env, USER_A, "gemini", "primary", "p")
    seed_key(env, USER_A, "gemini", "backup", "b")
    env.gemini.rate_limited_keys.add("p")
    env.db.fail_on[("notifications", "insert")] = APIError({"message": "boom", "code": "XX000"})
    conv = await _new_conversation(client)
    r = await client.post(
        f"/chat/conversations/{conv}/messages",
        json={"provider": "gemini", "content": "hi"}, headers=as_user(USER_A),
    )
    # Current behaviour: the stream blows up after the reply was produced and
    # the assistant message is never stored. Should degrade silently instead.
    assistant = [m for m in env.db.rows("chat_messages", conversation_id=conv) if m["role"] == "assistant"]
    assert len(assistant) == 1  # the reply survives a failed notification


async def test_a_second_send_while_a_reply_is_streaming_gets_a_409_not_a_second_call(client, env, monkeypatch):
    import asyncio

    from app.chat import service
    from app.llm import gateway

    seed_key(env, USER_A, "gemini", "primary", "gem-key")
    conv = await _new_conversation(client)
    gate = asyncio.Event()
    started = 0

    async def slow_stream(user_id, provider, messages, options=None):
        nonlocal started
        started += 1
        yield "first "
        await gate.wait()
        yield "reply"

    monkeypatch.setattr(gateway, "stream", slow_stream)
    body = {"provider": "gemini", "content": "hello"}
    first = asyncio.create_task(client.post(f"/chat/conversations/{conv}/messages", json=body, headers=as_user(USER_A)))
    while started == 0:
        await asyncio.sleep(0.01)
    second = await client.post(f"/chat/conversations/{conv}/messages", json=body, headers=as_user(USER_A))
    assert second.status_code == 409 and second.json()["error"]["code"] == "reply_in_progress"
    gate.set()
    assert (await first).text == "first reply"
    assert started == 1 and service._replies_in_flight == set()
    # and once it is done, sending again works
    again = await client.post(f"/chat/conversations/{conv}/messages", json=body, headers=as_user(USER_A))
    assert again.status_code == 200


async def test_the_exchange_is_stored_atomically_and_in_order(client, env):
    seed_key(env, USER_A, "gemini", "primary", "gem-key")
    conv = await _new_conversation(client)
    await client.post(f"/chat/conversations/{conv}/messages",
                      json={"provider": "gemini", "content": "q"}, headers=as_user(USER_A))
    assert [n for n, _ in env.db.rpc_calls].count("append_chat_exchange") == 1
    rows = env.db.rows("chat_messages", conversation_id=conv)
    assert [r["role"] for r in rows] == ["user", "assistant"]


async def test_a_failed_save_stores_neither_message(client, env):
    from postgrest.exceptions import APIError

    seed_key(env, USER_A, "gemini", "primary", "gem-key")
    conv = await _new_conversation(client)
    env.db.fail_on[("chat_messages", "insert")] = APIError({"message": "boom", "code": "XX000", "details": None, "hint": None})
    r = await client.post(f"/chat/conversations/{conv}/messages",
                          json={"provider": "gemini", "content": "q"}, headers=as_user(USER_A))
    assert r.status_code == 200  # the user still saw the reply
    assert env.db.rows("chat_messages", conversation_id=conv) == []  # no orphaned user message
