"""In-memory stand-ins for Supabase and the provider adapters.

The fake Supabase client implements just the PostgREST builder surface the
backend uses (select/insert/upsert/update/delete, eq/gte, order, limit,
maybe_single, rpc) over plain Python lists, so ownership filters, ordering
and "no such row" behaviour are actually exercised instead of being stubbed
per call. It also emulates two Postgres behaviours that matter for error
paths: a malformed uuid in a filter raises PostgREST error 22P02, and
maybe_single() over several rows raises PGRST116.

Nothing here touches the network or any real API key.
"""

import asyncio
import copy
import time
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from postgrest.exceptions import APIError

from app.llm.options import LLMOptions
from app.providers.base import ProviderAdapter, ProviderRateLimitError

UUID_COLUMNS = {
    "id", "user_id", "resume_id", "interview_id", "conversation_id", "admin_id",
    "filter_resume_id",
}
INTERVIEW_TYPES = {
    "coding", "behavioral", "hr", "ml_ai", "webd", "sde", "system_design", "case_study",
}

DEFAULTS: dict[str, dict] = {
    "provider_keys": {"is_valid": False, "last_validated_at": None},
    "conversations": {"title": None},
    "chat_messages": {"provider": None},
    "resumes": {"parsed_text": None, "digest": None},
    "interviews": {
        "phase": None, "started_at": None, "ends_at": None, "running_summary": None,
        "brief": None, "summarized_through_turn": 0, "selected_question_ids": [],
        "current_question_index": 0, "provider": "gemini",
    },
    "question_bank": {"test_cases": None, "tags": None, "created_by": None},
    "notifications": {"is_read": False},
}


def _is_uuid(value) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, db: "FakeSupabase", table: str):
        self.db = db
        self.table = table
        self._op = "select"
        self._cols = "*"
        self._payload = None
        self._on_conflict = None
        self._filters: list[tuple] = []
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None
        self._offset: int = 0
        self._single = False

    # --- builder ---
    def select(self, cols="*", **_):
        self._op, self._cols = "select", cols
        return self

    def insert(self, payload, **_):
        self._op, self._payload = "insert", payload
        return self

    def upsert(self, payload, on_conflict=None, **_):
        self._op, self._payload, self._on_conflict = "upsert", payload, on_conflict
        return self

    def update(self, payload, **_):
        self._op, self._payload = "update", payload
        return self

    def delete(self, **_):
        self._op = "delete"
        return self

    def eq(self, col, val):
        self._check_value(col, val)
        self._filters.append(("eq", col, val))
        return self

    def gte(self, col, val):
        self._filters.append(("gte", col, val))
        return self

    def order(self, col, desc=False, **_):
        self._order = (col, bool(desc))
        return self

    def limit(self, n, **_):
        self._limit = n
        return self

    def range(self, start, end, **_):
        self._offset = start
        self._limit = end - start + 1
        return self

    def maybe_single(self):
        self._single = True
        return self

    # --- helpers ---
    def _check_value(self, col, val):
        if col in UUID_COLUMNS and not _is_uuid(val):
            raise APIError(
                {"message": f'invalid input syntax for type uuid: "{val}"', "code": "22P02",
                 "details": None, "hint": None}
            )
        if self.table in ("interviews", "question_bank") and col == "type" and val not in INTERVIEW_TYPES:
            raise APIError(
                {"message": f'invalid input value for enum interview_type: "{val}"',
                 "code": "22P02", "details": None, "hint": None}
            )

    def _match(self, row) -> bool:
        for op, col, val in self._filters:
            have = row.get(col)
            if op == "eq" and have != val:
                return False
            if op == "gte" and not (have is not None and have >= val):
                return False
        return True

    def _project(self, row):
        if self._cols == "*":
            return copy.deepcopy(row)
        cols = [c.strip() for c in self._cols.split(",")]
        for c in cols:
            if c not in row:
                raise APIError({"message": f"column {self.table}.{c} does not exist",
                                "code": "42703", "details": None, "hint": None})
        return {c: copy.deepcopy(row[c]) for c in cols}

    # --- execution ---
    def execute(self):
        rows = self.db.tables.setdefault(self.table, [])
        self.db.calls.append((self.table, self._op))
        hook = self.db.fail_on.get((self.table, self._op))
        if hook:
            raise hook

        if self._op == "select":
            snapshot = [r for r in rows if self._match(r)]
            if self._order:
                col, desc = self._order
                snapshot.sort(key=lambda r: r.get(col), reverse=desc)
            if self._offset:
                snapshot = snapshot[self._offset :]
            if self._limit is not None:
                snapshot = snapshot[: self._limit]
            out = [self._project(r) for r in snapshot]
            delay = self.db.select_delay.get(self.table, 0)
            if delay:
                time.sleep(delay)  # runs in a worker thread (asyncio.to_thread)
            if self._single:
                if len(out) > 1:
                    raise APIError({"message": "JSON object requested, multiple (or no) rows returned",
                                    "code": "PGRST116", "details": "The result contains 2 rows",
                                    "hint": None})
                return _Result(out[0]) if out else None
            return _Result(out)

        if self._op == "insert":
            payloads = self._payload if isinstance(self._payload, list) else [self._payload]
            made = []
            for p in payloads:
                row = {**copy.deepcopy(DEFAULTS.get(self.table, {})), **copy.deepcopy(p)}
                row.setdefault("id", str(uuid.uuid4()))
                row.setdefault("created_at", self.db.now())
                rows.append(row)
                made.append(copy.deepcopy(row))
            return _Result(made)

        if self._op == "upsert":
            keys = [k.strip() for k in (self._on_conflict or "id").split(",")]
            p = copy.deepcopy(self._payload)
            for row in rows:
                if all(row.get(k) == p.get(k) for k in keys):
                    row.update(p)
                    return _Result([copy.deepcopy(row)])
            row = {**copy.deepcopy(DEFAULTS.get(self.table, {})), **p}
            row.setdefault("id", str(uuid.uuid4()))
            row.setdefault("created_at", self.db.now())
            rows.append(row)
            return _Result([copy.deepcopy(row)])

        if self._op == "update":
            if not self._payload:
                # PostgREST rejects an UPDATE that sets no columns.
                raise APIError({"message": "Empty or invalid json", "code": "PGRST102",
                                "details": None, "hint": None})
            hit = [r for r in rows if self._match(r)]
            for r in hit:
                r.update(copy.deepcopy(self._payload))
            return _Result([copy.deepcopy(r) for r in hit])

        if self._op == "delete":
            hit = [r for r in rows if self._match(r)]
            self.db.tables[self.table] = [r for r in rows if r not in hit]
            return _Result([copy.deepcopy(r) for r in hit])
        raise AssertionError(self._op)


class _Rpc:
    def __init__(self, db, name, params):
        self.db, self.name, self.params = db, name, params

    def execute(self):
        return _Result(self.db.run_rpc(self.name, self.params))


class FakeSupabase:
    def __init__(self):
        self.tables: dict[str, list[dict]] = {}
        self.calls: list[tuple[str, str]] = []
        self.rpc_calls: list[tuple[str, dict]] = []
        self.fail_on: dict[tuple[str, str], Exception] = {}
        self.select_delay: dict[str, float] = {}
        self.similarity = 0.75
        self._clock = datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> str:
        self._clock += timedelta(microseconds=1)
        return self._clock.isoformat()

    def table(self, name):
        return _Query(self, name)

    def rpc(self, name, params):
        return _Rpc(self, name, params)

    def seed(self, table: str, **row) -> dict:
        row = {**copy.deepcopy(DEFAULTS.get(table, {})), **row}
        row.setdefault("id", str(uuid.uuid4()))
        row.setdefault("created_at", self.now())
        self.tables.setdefault(table, []).append(row)
        return row

    def rows(self, table: str, **match) -> list[dict]:
        return [r for r in self.tables.get(table, []) if all(r.get(k) == v for k, v in match.items())]

    def run_rpc(self, name, params):
        self.rpc_calls.append((name, params))
        if name == "match_resume_chunks":
            hits = [r for r in self.tables.get("resume_chunks", [])
                    if r["resume_id"] == params["filter_resume_id"]]
            hits.sort(key=lambda r: r["chunk_index"])
            return [
                {"id": r["id"], "content": r["content"], "chunk_index": r["chunk_index"],
                 "similarity": self.similarity}
                for r in hits[: params["match_count"]]
            ]
        if name == "match_question_bank":
            hits = [r for r in self.tables.get("question_bank", [])
                    if r["type"] == params["filter_type"]]
            return [
                {"id": r["id"], "question": r["question"], "test_cases": r.get("test_cases"),
                 "tags": r.get("tags"), "similarity": 0.9}
                for r in hits[: params["match_count"]]
            ]
        if name == "record_llm_usage":
            usage = self.tables.setdefault("llm_usage", [])
            day = datetime.now(UTC).date().isoformat()
            for r in usage:
                if (r["user_id"], r["provider"], r["kind"], r["day"]) == (
                    params["p_user_id"], params["p_provider"], params["p_kind"], day
                ):
                    r["requests"] += params["p_requests"]
                    r["input_tokens"] += params["p_input"]
                    r["output_tokens"] += params["p_output"]
                    return None
            usage.append({
                "user_id": params["p_user_id"], "provider": params["p_provider"],
                "kind": params["p_kind"], "day": day, "requests": params["p_requests"],
                "input_tokens": params["p_input"], "output_tokens": params["p_output"],
            })
            return None
        raise AssertionError(f"unexpected rpc {name}")


class FakeAdapter(ProviderAdapter):
    """Scriptable provider. Never performs I/O."""

    def __init__(self, name: str):
        self.name = name
        self.chat_calls: list[SimpleNamespace] = []
        self.embed_calls: list[SimpleNamespace] = []
        self.validate_calls: list[str] = []
        self.invalid_keys: set[str] = set()
        self.rate_limited_keys: set[str] = set()
        self.validate_error: Exception | None = None
        # Consumed one per chat() call: a str (the reply), an Exception (raised
        # before any output) or ("partial text", Exception) (raised mid-stream).
        self.script: list = []
        self.chat_delay = 0.0
        self.replies: dict[str, str] = {}

    def default_reply(self, options: LLMOptions) -> str:
        task, js = options.task, options.json_mode
        if task in self.replies:
            return self.replies[task]
        if task == "interview" and js:
            return '{"brief": "Senior Python role needing Kubernetes.", "opening": "Welcome! Tell me about your latest project."}'
        if task == "interview":
            return "Thanks. How would you design that for scale?"
        if task == "extract" and js:
            return '{"must_have": ["python", "kubernetes"], "nice_to_have": ["go"], "experience_level": "senior", "title": "Backend Engineer"}'
        if task == "extract":
            return "Senior engineer, 8 years of Python."
        if task == "summarize":
            return "Covered Python; candidate was solid."
        if task == "feedback":
            return "- Add Kubernetes\n- Add Go"
        return "Hello from the fake model."

    async def validate(self, api_key: str) -> bool:
        self.validate_calls.append(api_key)
        if self.validate_error:
            raise self.validate_error
        if api_key in self.rate_limited_keys:
            raise ProviderRateLimitError("quota")
        return api_key not in self.invalid_keys

    async def chat(self, api_key, messages, stream=True, options=None, usage=None):
        options = options or LLMOptions()
        self.chat_calls.append(SimpleNamespace(
            api_key=api_key, messages=list(messages), options=options, stream=stream))
        if api_key in self.rate_limited_keys:
            raise ProviderRateLimitError("quota")
        if self.script:
            item = self.script.pop(0)
            if isinstance(item, BaseException):
                raise item
            if isinstance(item, tuple):
                partial, exc = item
                yield partial
                raise exc
            text = item
        else:
            text = self.default_reply(options)
        if self.chat_delay:
            await asyncio.sleep(self.chat_delay)
        if usage is not None:
            usage.requests += 1
        if stream:
            words = text.split(" ")
            for i, w in enumerate(words):
                yield w if i == len(words) - 1 else w + " "
        else:
            yield text

    async def embed_many(self, api_key, texts, usage=None, kind="doc"):
        self.embed_calls.append(SimpleNamespace(api_key=api_key, texts=list(texts)))
        if api_key in self.rate_limited_keys:
            raise ProviderRateLimitError("quota")
        if usage is not None:
            usage.requests += 1
        return [[0.1, 0.2, 0.3] for _ in texts]
