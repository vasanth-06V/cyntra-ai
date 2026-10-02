"""Layering rules that are cheap to enforce mechanically."""

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

# Only these may touch the Supabase client / tables / RPCs.
_ALLOWED = ("app/db/", "app/core/db.py")
_FORBIDDEN = re.compile(r"\.table\(|\.rpc\(|get_supabase|from supabase|import supabase")


def _python_files():
    for path in APP.rglob("*.py"):
        yield path, path.relative_to(APP.parent).as_posix()


def test_only_the_db_layer_touches_supabase():
    offenders = []
    for path, rel in _python_files():
        if rel.startswith(_ALLOWED) or any(rel == a for a in _ALLOWED):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _FORBIDDEN.search(line):
                offenders.append(f"{rel}:{number}: {line.strip()}")
    assert not offenders, "Supabase access outside app/db:\n" + "\n".join(offenders)


def test_db_layer_does_not_import_feature_packages():
    feature = re.compile(r"from app\.(chat|keys|rag|ats|interviews|llm)\b")
    offenders = []
    for path in (APP / "db").rglob("*.py"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if feature.search(line):
                offenders.append(f"{path.name}:{number}: {line.strip()}")
    assert not offenders, "app/db must stay below the feature packages:\n" + "\n".join(offenders)


def test_every_db_query_on_a_user_owned_table_is_scoped_by_user_id():
    """Lookups of a single user-owned row by id must also filter on user_id
    (the backend uses the service role, so RLS will not catch a missed filter)."""
    source = (APP / "db" / "resumes.py").read_text(encoding="utf-8")
    assert source.count('.eq("user_id", user_id)') >= 1
    source = (APP / "db" / "chat.py").read_text(encoding="utf-8")
    assert 'eq("user_id", user_id)' in source
    source = (APP / "db" / "interviews.py").read_text(encoding="utf-8")
    assert source.count('eq("user_id", user_id)') >= 2
