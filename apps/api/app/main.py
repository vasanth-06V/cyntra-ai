from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ats.router import router as ats_router
from app.chat.router import router as chat_router
from app.core.config import settings, validate_config
from app.core.security import AuthenticatedUser, get_current_user
from app.interviews.router import router as interviews_router
from app.keys.router import router as keys_router
from app.llm.router import router as usage_router
from app.rag.router import router as rag_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Fail at boot, with a readable list, rather than on the first request.
    validate_config()
    yield


# The interactive docs/schema are for development only.
_docs = {} if not settings.is_production else {"docs_url": None, "redoc_url": None, "openapi_url": None}

app = FastAPI(title="CyntraAI API", lifespan=lifespan, **_docs)
app.include_router(keys_router)
app.include_router(chat_router)
app.include_router(rag_router)
app.include_router(ats_router)
app.include_router(interviews_router)
app.include_router(usage_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/authenticated")
async def health_authenticated(user: AuthenticatedUser = Depends(get_current_user)):
    return {"status": "ok", "user_id": user.user_id, "email": user.email}
