from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse

from app.chat import service
from app.chat.models import (
    ChatMessageOut,
    ConversationOut,
    CreateConversationRequest,
    RenameConversationRequest,
    SendMessageRequest,
)
from app.core.ids import UuidStr
from app.core.pagination import Page, page_params
from app.core.security import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED
)
async def create_conversation(
    body: CreateConversationRequest, user: AuthenticatedUser = Depends(get_current_user)
):
    return await service.create_conversation(user.user_id, body.title)


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
async def rename_conversation(
    conversation_id: UuidStr,
    body: RenameConversationRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    return await service.rename_conversation(user.user_id, conversation_id, body.title)


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    user: AuthenticatedUser = Depends(get_current_user), page: Page = Depends(page_params)
):
    return await service.list_conversations(user.user_id, page.limit, page.offset)


@router.get("/conversations/{conversation_id}/messages", response_model=list[ChatMessageOut])
async def list_messages(
    conversation_id: UuidStr,
    user: AuthenticatedUser = Depends(get_current_user),
    limit: int = Query(service.DEFAULT_MESSAGE_PAGE, ge=1, le=500),
):
    """The latest `limit` messages, oldest first."""
    return await service.list_messages(user.user_id, conversation_id, limit)


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: UuidStr,
    body: SendMessageRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    replies = service.stream_reply(
        user.user_id, conversation_id, body.provider.value, body.content
    )

    # Pull the first chunk *before* returning the StreamingResponse. Once a
    # streaming response has started its 200 status is already sent, so any
    # failure after that point can only cut the stream off mid-air -- and an
    # error raised from inside the stream also bypasses CORS, which the
    # browser reports as an opaque "something went wrong". Failing here
    # instead (no key, rate limit, provider overloaded) produces a normal
    # JSON error with the right status and a readable message.
    try:
        first_chunk = await replies.__anext__()
    except StopAsyncIteration:
        first_chunk = None

    async def body_stream():
        try:
            if first_chunk is not None:
                yield first_chunk
            async for chunk in replies:
                yield chunk
        finally:
            # On a client disconnect Starlette closes THIS generator; close the
            # inner one explicitly so the partial reply is saved and the
            # per-conversation guard is released now, not whenever GC runs.
            await replies.aclose()

    return StreamingResponse(body_stream(), media_type="text/plain")
