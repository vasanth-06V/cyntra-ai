from app.llm.ttl_cache import TTLCache


def test_expires_and_evicts():
    now = [0.0]
    cache = TTLCache(ttl_seconds=10, max_items=2, clock=lambda: now[0])
    cache.set("a", 1)
    assert cache.get("a") == 1
    now[0] = 11
    assert cache.get("a") is None
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)  # evicts oldest
    assert cache.get("a") is None and cache.get("c") == 3
