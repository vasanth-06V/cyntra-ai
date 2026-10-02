from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchored to this file, not the process's working directory -- the server
# is launched from different directories (apps/api directly, or the repo
# root via the preview launcher), and a relative ".env" silently loaded
# nothing in the latter case.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""

    key_encryption_secret: str = ""

    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""

    judge0_api_url: str = ""
    judge0_api_key: str = ""

    environment: str = "development"
    # Comma-separated list of browser origins allowed to call the API.
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in ("production", "prod")


settings = Settings()


def config_problems(cfg: Settings) -> list[str]:
    """What is wrong with the configuration, as human-readable lines (empty
    when it is fine). Checked at startup so a missing secret fails loudly at
    boot instead of as a 500 on the first user's request."""
    problems: list[str] = []
    for name in ("supabase_url", "supabase_service_role_key", "key_encryption_secret"):
        if not getattr(cfg, name):
            problems.append(f"{name.upper()} is not set")

    if cfg.key_encryption_secret:
        try:
            from cryptography.fernet import Fernet

            Fernet(cfg.key_encryption_secret)
        except Exception:
            problems.append(
                "KEY_ENCRYPTION_SECRET is not a valid Fernet key "
                "(generate one with Fernet.generate_key())"
            )

    if cfg.is_production:
        for name in ("r2_account_id", "r2_access_key_id", "r2_secret_access_key", "r2_bucket_name"):
            if not getattr(cfg, name):
                problems.append(f"{name.upper()} is required in production")
        if not cfg.cors_origin_list:
            problems.append("CORS_ORIGINS must list the production web origin")
        if any("localhost" in o for o in cfg.cors_origin_list):
            problems.append("CORS_ORIGINS still contains localhost in production")
    return problems


def validate_config(cfg: Settings = settings) -> None:
    problems = config_problems(cfg)
    if problems:
        raise RuntimeError("Invalid configuration:\n  - " + "\n  - ".join(problems))
