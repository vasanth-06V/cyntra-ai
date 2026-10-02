import os
from pathlib import Path

from app.core.config import Settings


def test_env_file_is_anchored_to_apps_api_not_the_working_directory(tmp_path, monkeypatch):
    env_file = Settings.model_config["env_file"]

    assert Path(env_file).is_absolute()
    assert Path(env_file) == Path(__file__).resolve().parents[1] / ".env"

    # Launching from an unrelated directory must not change where it looks.
    monkeypatch.chdir(tmp_path)
    assert Settings.model_config["env_file"] == env_file
    assert os.getcwd() == str(tmp_path)


# --- startup validation ---


def _settings(**overrides):
    from cryptography.fernet import Fernet

    from app.core.config import Settings

    base = dict(
        supabase_url="https://x.supabase.co",
        supabase_service_role_key="svc",
        key_encryption_secret=Fernet.generate_key().decode(),
        environment="development",
    )
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_valid_development_config_has_no_problems():
    from app.core.config import config_problems

    assert config_problems(_settings()) == []


def test_missing_required_values_are_all_reported():
    from app.core.config import config_problems

    problems = config_problems(
        _settings(supabase_url="", supabase_service_role_key="", key_encryption_secret="")
    )
    assert len(problems) == 3


def test_invalid_fernet_secret_is_reported():
    from app.core.config import config_problems

    problems = config_problems(_settings(key_encryption_secret="not-a-fernet-key"))
    assert any("Fernet" in p for p in problems)


def test_production_requires_r2_and_a_non_localhost_origin():
    from app.core.config import config_problems

    problems = config_problems(_settings(environment="production"))
    assert any("R2_BUCKET_NAME" in p for p in problems)
    assert any("localhost" in p for p in problems)

    ok = _settings(
        environment="production",
        r2_account_id="a", r2_access_key_id="b", r2_secret_access_key="c", r2_bucket_name="d",
        cors_origins="https://app.example.com",
    )
    assert config_problems(ok) == []


def test_validate_config_raises_with_a_readable_list():
    import pytest

    from app.core.config import validate_config

    with pytest.raises(RuntimeError, match="SUPABASE_URL is not set"):
        validate_config(_settings(supabase_url=""))


def test_cors_origins_are_parsed_from_a_comma_list():
    assert _settings(cors_origins="https://a.com, https://b.com").cors_origin_list == [
        "https://a.com",
        "https://b.com",
    ]


def test_health_does_not_leak_the_environment():
    from fastapi.testclient import TestClient

    from app.main import app

    assert TestClient(app).get("/health").json() == {"status": "ok"}
