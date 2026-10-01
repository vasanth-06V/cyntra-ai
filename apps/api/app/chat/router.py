from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse

from app.chat import service
from app.chat.models import (
    ChatMessageOut,
    ConversationOut,
    CreateConversationRequest,
    SendMessageRequest,
)
from app.core.security import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED
)
async def create_conversation(
    body: CreateConversationRequest, user: AuthenticatedUser = Depends(get_current_user)
):
    return await service.create_conversation(user.user_id, body.title)


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(user: AuthenticatedUser = Depends(get_current_user)):
    return await service.list_conversations(user.user_id)


@router.get("/conversations/{conversation_id}/messages", response_model=list[ChatMessageOut])
async def list_messages(
    conversation_id: str, user: AuthenticatedUser = Depends(get_current_user)
):
    return await service.list_messages(user.user_id, conversation_id)


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    body: SendMessageRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    return StreamingResponse(
        service.stream_reply(user.user_id, conversation_id, body.provider.value, body.content),
        media_type="text/plain",
    )
