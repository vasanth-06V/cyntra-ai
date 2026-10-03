"""The public API shape is pinned. If this fails you changed a path, a
parameter or a response model: if that was on purpose, regenerate the
snapshot (python -m scripts.update_openapi_snapshot) and commit it together
with the change; if not, you found an accidental API change."""

import json

from scripts.update_openapi_snapshot import SNAPSHOT, current


def test_the_api_shape_matches_the_committed_snapshot():
    assert json.loads(current()) == json.loads(SNAPSHOT.read_text(encoding="utf-8")), (
        "The OpenAPI schema changed. If intended, run: python -m scripts.update_openapi_snapshot"
    )


def test_every_route_is_documented_and_the_known_surface_is_present():
    paths = json.loads(SNAPSHOT.read_text(encoding="utf-8"))["paths"]
    for expected in (
        "/health", "/ready", "/keys", "/chat/conversations", "/ats/score", "/interviews",
        "/interviews/{interview_id}/turns", "/interviews/{interview_id}/submissions",
        "/interviews/{interview_id}/problem", "/interviews/{interview_id}/report",
        "/jobs/{job_id}", "/reports", "/reports/{interview_id}", "/usage",
    ):
        assert expected in paths, expected
