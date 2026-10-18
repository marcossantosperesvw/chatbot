"""Rota de chat e tradução de falhas para respostas HTTP."""

import logging

from fastapi import APIRouter, HTTPException, status

from app.api.schemas import AssistantMessage, ChatRequest, ChatResponse, ErrorResponse
from app.services.chat_service import generate_reply


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Enviar uma mensagem ao chat simulado",
    responses={
        500: {
            "model": ErrorResponse,
            "description": "Falha inesperada ao processar a mensagem.",
        },
    },
)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        content = generate_reply(request.message)
        return ChatResponse(
            conversation_id=request.conversation_id,
            message=AssistantMessage(content=content),
        )
    except Exception:
        logger.exception(
            "Falha ao processar a conversa %s", request.conversation_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível processar a mensagem. Tente novamente.",
        ) from None
