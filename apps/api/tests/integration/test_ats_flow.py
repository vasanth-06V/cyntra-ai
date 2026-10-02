"""POST /ats/score end to end."""

import pytest

from app.ats import requirements_extractor

from .conftest import USER_A, USER_B, as_user, new_id, seed_key, seed_processed_resume

JD = "We need a senior backend engineer with Python and Kubernetes. Go is a plus."


@pytest.fixture(autouse=True)
def _clear_requirements_cache():
    requirements_extractor._cache._data.clear()
    yield
    requirements_extractor._cache._data.clear()


def _body(resume_id, jd=JD, provider="gemini"):
    return {"resume_id": resume_id, "jd_text": jd, "provider": provider}


async def test_score_success_has_all_subscores_and_costs_expected_requests(client, env):
    seed_key(env, USER_A, "gemini", "primary", "gem")
    resume = seed_processed_resume(env, USER_A)

    r = await client.post("/ats/score", json=_body(resume["id"]), headers=as_user(USER_A))
    assert r.status_code == 200
    d = r.json()
    assert set(d) == {"composite_score", "keyword_score", "semantic_score", "formatting_score",
                      "feedback", "missing_must_have", "missing_nice_to_have"}
    assert 0 <= d["composite_score"] <= 100
    assert d["keyword_score"] > 0.5            # python + kubernetes are in the resume
    assert d["semantic_score"] == pytest.approx(0.75)
    assert d["formatting_score"] == 1.0
    assert "Kubernetes" in d["feedback"]
    # 1 batched embedding + exactly 2 LLM calls (extract, feedback)
    assert len(env.gemini.embed_calls) == 1
    assert [c.options.task for c in env.gemini.chat_calls] == ["extract", "feedback"]
    assert env.gemini.chat_calls[0].options.json_mode is True


async def test_second_score_with_same_jd_reuses_cached_requirements(client, env):
    seed_key(env, USER_A, "gemini", "primary", "gem")
    r1 = seed_processed_resume(env, USER_A)
    r2 = seed_processed_resume(env, USER_A)
    await client.post("/ats/score", json=_body(r1["id"]), headers=as_user(USER_A))
    await client.post("/ats/score", json=_body(r2["id"]), headers=as_user(USER_A))
    tasks = [c.options.task for c in env.gemini.chat_calls]
    assert tasks.count("extract") == 1 and tasks.count("feedback") == 2


async def test_requirements_cache_is_not_shared_between_users(client, env):
    for u in (USER_A, USER_B):
        seed_key(env, u, "gemini", "primary", f"gem-{u[:2]}")
    ra, rb = seed_processed_resume(env, USER_A), seed_processed_resume(env, USER_B)
    await client.post("/ats/score", json=_body(ra["id"]), headers=as_user(USER_A))
    await client.post("/ats/score", json=_body(rb["id"]), headers=as_user(USER_B))
    assert [c.options.task for c in env.gemini.chat_calls].count("extract") == 2


async def test_cannot_score_someone_elses_resume(client, env):
    seed_key(env, USER_B, "gemini", "primary", "g")
    resume = seed_processed_resume(env, USER_A)
    r = await client.post("/ats/score", json=_body(resume["id"]), headers=as_user(USER_B))
    assert r.status_code == 404 and env.gemini.chat_calls == []


async def test_unprocessed_resume_is_422_and_no_key_is_412(client, env):
    seed_key(env, USER_A, "gemini", "primary", "g")
    raw = env.db.seed("resumes", user_id=USER_A, file_key="k.pdf")
    r = await client.post("/ats/score", json=_body(raw["id"]), headers=as_user(USER_A))
    assert r.status_code == 422

    resume = seed_processed_resume(env, USER_B)
    r = await client.post("/ats/score", json=_body(resume["id"]), headers=as_user(USER_B))
    assert r.status_code == 412


async def test_unknown_resume_is_404_and_bad_provider_is_422(client, env):
    seed_key(env, USER_A, "gemini", "primary", "g")
    assert (await client.post("/ats/score", json=_body(new_id()), headers=as_user(USER_A))).status_code == 404
    r = await client.post("/ats/score", json=_body(new_id(), provider="openai"), headers=as_user(USER_A))
    assert r.status_code == 422


async def test_chosen_provider_must_have_its_own_key(client, env):
    seed_key(env, USER_A, "gemini", "primary", "g")
    resume = seed_processed_resume(env, USER_A)
    r = await client.post("/ats/score", json=_body(resume["id"], provider="groq"), headers=as_user(USER_A))
    assert r.status_code == 412


async def test_quota_exhausted_during_feedback_is_429(client, env):
    seed_key(env, USER_A, "gemini", "primary", "g")
    resume = seed_processed_resume(env, USER_A)
    from app.providers.base import ProviderRateLimitError
    env.gemini.script = [
        '{"must_have": ["python"], "nice_to_have": []}',
        ProviderRateLimitError("quota"),
    ]
    r = await client.post("/ats/score", json=_body(resume["id"]), headers=as_user(USER_A))
    assert r.status_code == 429


# --------------------------- findings ---------------------------


async def test_unparseable_extractor_reply_is_not_a_500(client, env):
    seed_key(env, USER_A, "gemini", "primary", "g")
    resume = seed_processed_resume(env, USER_A)
    env.gemini.script = ["Sorry, I cannot help with that."]
    r = await client.post("/ats/score", json=_body(resume["id"]), headers=as_user(USER_A))
    assert r.status_code != 500


async def test_wrongly_shaped_requirements_are_not_a_500(client, env):
    seed_key(env, USER_A, "gemini", "primary", "g")
    resume = seed_processed_resume(env, USER_A)
    env.gemini.script = ['{"must_have": "python, kubernetes", "nice_to_have": [{"skill": "go"}]}']
    r = await client.post("/ats/score", json=_body(resume["id"]), headers=as_user(USER_A))
    assert r.status_code != 500


async def test_absent_skills_are_not_matched_by_substring_accidents(client, env):
    seed_key(env, USER_A, "gemini", "primary", "g")
    resume = seed_processed_resume(
        env, USER_A, text="Wrote HTML pages. Made specific decisions and maintained sites.\nExperience\nSkills"
    )
    env.gemini.script = [
        '{"must_have": ["machine learning", "continuous integration", "artificial intelligence"], "nice_to_have": []}'
    ]
    r = await client.post("/ats/score", json=_body(resume["id"]), headers=as_user(USER_A))
    assert r.status_code == 200
    assert r.json()["keyword_score"] < 1.0
    assert r.json()["missing_must_have"]


async def test_java_is_not_javascript(client, env):
    seed_key(env, USER_A, "gemini", "primary", "g")
    resume = seed_processed_resume(env, USER_A, text="Experience\nSkills\nJavaScript, TypeScript, React")
    env.gemini.script = ['{"must_have": ["java"], "nice_to_have": []}']
    r = await client.post("/ats/score", json=_body(resume["id"]), headers=as_user(USER_A))
    assert r.json()["missing_must_have"] == ["java"]


async def test_empty_requirements_are_refused_not_scored_near_perfect(client, env):
    seed_key(env, USER_A, "gemini", "primary", "g")
    resume = seed_processed_resume(env, USER_A, text="x")
    env.gemini.script = ['{"must_have": [], "nice_to_have": []}']
    r = await client.post("/ats/score", json=_body(resume["id"], jd="asdf asdf asdf asdf"), headers=as_user(USER_A))
    assert r.status_code == 422


async def test_empty_and_giant_jd_rejected(client, env):
    seed_key(env, USER_A, "gemini", "primary", "g")
    resume = seed_processed_resume(env, USER_A)
    r1 = await client.post("/ats/score", json=_body(resume["id"], jd=""), headers=as_user(USER_A))
    r2 = await client.post("/ats/score", json=_body(resume["id"], jd="x" * 5_000_000), headers=as_user(USER_A))
    assert r1.status_code == 422 and r2.status_code == 422
