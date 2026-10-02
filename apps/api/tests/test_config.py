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
