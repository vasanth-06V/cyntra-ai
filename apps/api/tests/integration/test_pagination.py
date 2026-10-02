"""List endpoints are paged; chat messages load as the latest N, oldest first."""

from .conftest import USER_A, as_user, seed_key
from .test_chat_flow import _new_conversation


async def test_conversation_list_honours_limit_and_offset(client, env):
    ids = [await _new_conversation(client, USER_A, f"c{i}") for i in range(5)]

    first = (await client.get("/chat/conversations?limit=2", headers=as_user(USER_A))).json()
    second = (await client.get("/chat/conversations?limit=2&offset=2", headers=as_user(USER_A))).json()
    everything = (await client.get("/chat/conversations", headers=as_user(USER_A))).json()

    assert len(first) == 2 and len(second) == 2 and len(everything) == 5
    assert {c["id"] for c in first}.isdisjoint({c["id"] for c in second})
    assert {c["id"] for c in everything} == set(ids)


async def test_page_parameters_are_validated(client, env):
    for query in ("limit=0", "limit=100000", "offset=-1"):
        r = await client.get(f"/chat/conversations?{query}", headers=as_user(USER_A))
        assert r.status_code == 422, query
        assert r.json()["error"]["code"] == "validation_failed"


async def test_messages_load_the_latest_page_oldest_first(client, env):
    seed_key(env, USER_A, "gemini", "primary", "gem-key")
    conv = await _new_conversation(client)
    for i in range(3):
        r = await client.post(
            f"/chat/conversations/{conv}/messages",
            json={"provider": "gemini", "content": f"question {i}"}, headers=as_user(USER_A),
        )
        assert r.status_code == 200

    page = (await client.get(f"/chat/conversations/{conv}/messages?limit=2", headers=as_user(USER_A))).json()
    assert len(page) == 2
    assert page[-1]["role"] == "assistant"  # the newest message is last
    everything = (await client.get(f"/chat/conversations/{conv}/messages", headers=as_user(USER_A))).json()
    assert [m["id"] for m in everything][-2:] == [m["id"] for m in page]  # same tail, same order
