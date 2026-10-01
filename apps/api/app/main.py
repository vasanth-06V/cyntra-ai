from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.chat.router import router as chat_router
from app.core.config import settings
from app.core.security import AuthenticatedUser, get_current_user
from app.keys.router import router as keys_router
from app.rag.router import router as rag_router

app = FastAPI(title="CyntraAI API")
app.include_router(keys_router)
app.include_router(chat_router)
app.include_router(rag_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment}


@app.get("/health/authenticated")
async def health_authenticated(user: AuthenticatedUser = Depends(get_current_user)):
    return {"status": "ok", "user_id": user.user_id, "email": user.email}
