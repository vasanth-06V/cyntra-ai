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


settings = Settings()
