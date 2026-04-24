from __future__ import annotations

from fastapi import APIRouter, Request

from app.models.chat import ChatRequest, ChatResponse
from app.services.chatbot import ChatbotService

router = APIRouter(tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    response_model_exclude_none=True,
    response_model_exclude_defaults=True,
    response_model_exclude_unset=True,
)
async def chat(request: Request, payload: ChatRequest) -> ChatResponse:
    service: ChatbotService = request.app.state.chatbot_service
    return await service.handle_prompt(payload.prompt)
