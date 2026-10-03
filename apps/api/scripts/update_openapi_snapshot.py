"""Rewrites tests/openapi_snapshot.json from the app's current API shape.

tests/test_openapi_snapshot.py fails whenever the API's paths, parameters or
schemas change, so an accidental change cannot slip through. After a
DELIBERATE API change, run this and commit the new snapshot with the change:

    python -m scripts.update_openapi_snapshot
"""

import json
from pathlib import Path

from app.main import app

SNAPSHOT = Path(__file__).resolve().parent.parent / "tests" / "openapi_snapshot.json"


def current() -> str:
    return json.dumps(app.openapi(), indent=1, sort_keys=True) + "\n"


if __name__ == "__main__":
    SNAPSHOT.write_text(current(), encoding="utf-8", newline="\n")
    print(f"wrote {SNAPSHOT}")
