import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.ats.router import router as ats_router
from app.chat.router import router as chat_router
from app.coding.router import router as coding_router
from app.core import background
from app.db import readiness
from app.core.config import settings, validate_config
from app.core.errors import install_error_handlers
from app.core.jsonlog import setup_logging
from app.core.middleware import RequestContextMiddleware
from app.core.security import AuthenticatedUser, get_current_user
from app.interviews.router import router as interviews_router
from app.jobs import recovery as job_recovery
from app.jobs.router import router as jobs_router
from app.keys.router import router as keys_router
from app.llm.router import router as usage_router
from app.reports import service as reports_service
from app.reports.router import router as reports_router
from app.team.router import router as team_router
from app.rag.router import router as rag_router


setup_logging()


async def _recover_jobs() -> None:
    """At boot: fail the jobs whose process is gone (stale heartbeat) and tidy
    what they were about. Live jobs of another instance are left alone."""
    await job_recovery.fail_stale_jobs()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Fail at boot, with a readable list, rather than on the first request.
    validate_config()
    await _recover_jobs()
    # Expired reports are refused at read time regardless; this also deletes them.
    sweepers = [
        asyncio.create_task(reports_service.sweep_forever(), name="report-sweep"),
        asyncio.create_task(job_recovery.sweep_forever(), name="job-sweep"),
    ]
    try:
        yield
    finally:
        for task in sweepers:
            task.cancel()
    # Let in-flight housekeeping (summaries, digests) finish rather than drop it.
    try:
        await asyncio.wait_for(background.drain(), timeout=8)
    except TimeoutError:
        pass


# The interactive docs/schema are for development only.
_docs = {} if not settings.is_production else {"docs_url": None, "redoc_url": None, "openapi_url": None}

app = FastAPI(title="CyntraAI API", lifespan=lifespan, **_docs)
app.include_router(keys_router)
app.include_router(chat_router)
app.include_router(rag_router)
app.include_router(ats_router)
app.include_router(coding_router)
app.include_router(interviews_router)
app.include_router(jobs_router)
app.include_router(usage_router)
app.include_router(reports_router)
app.include_router(team_router)

install_error_handlers(app)

# Middleware order: the last one added is outermost. The request-context layer
# (request id, access log, catch-all 500) sits *inside* CORS so even error
# responses carry CORS headers and the browser can read them.
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.get("/ready")
async def ready():
    """Is the API able to do real work (can it reach the database)? /health
    stays dependency-free so a platform health check never flaps with the
    database; this one is for humans and deploy scripts. Says nothing about
    why it failed."""
    try:
        await readiness.database_reachable()
    except Exception:
        logging.getLogger(__name__).warning("Readiness check failed", exc_info=True)
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return {"status": "ready"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/authenticated")
async def health_authenticated(user: AuthenticatedUser = Depends(get_current_user)):
    return {"status": "ok", "user_id": user.user_id, "email": user.email}
