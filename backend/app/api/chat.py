"""Rota de chat e tradução de falhas para respostas HTTP."""

import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.api.schemas import ChatRequest, ChatResponse, ErrorResponse
from app.core.errors import AIConfigurationError, AIProviderError, AITimeoutError
from app.services.chat_service import generate_reply


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Enviar uma mensagem ao agente especializado em jogos",
    responses={
        502: {"model": ErrorResponse, "description": "Falha na resposta da IA."},
        503: {"model": ErrorResponse, "description": "IA indisponível ou não configurada."},
        504: {"model": ErrorResponse, "description": "Tempo limite da IA excedido."},
        500: {
            "model": ErrorResponse,
            "description": "Falha inesperada ao processar a mensagem.",
        },
    },
)
async def chat(request: ChatRequest, http_request: Request) -> ChatResponse:
    try:
        message = await generate_reply(request, catalog=http_request.app.state.catalog,
                                       knowledge=http_request.app.state.knowledge,
                                       videos=http_request.app.state.videos)
        return ChatResponse(
            conversation_id=request.conversation_id,
            message=message,
        )
    except (AIConfigurationError, AIProviderError, AITimeoutError) as error:
        code, detail = {
            AIConfigurationError: (
                503,
                "A inteligência artificial está indisponível. "
                "Verifique a configuração do backend.",
            ),
            AIProviderError: (
                502,
                "Não foi possível obter uma resposta da inteligência artificial. "
                "Tente novamente.",
            ),
            AITimeoutError: (
                504,
                "A inteligência artificial demorou para responder. Tente novamente.",
            ),
        }[type(error)]
        logger.warning(
            "Falha de IA: %s; conversa %s", type(error).__name__, request.conversation_id
        )
        raise HTTPException(status_code=code, detail=detail) from None
    except Exception as error:
        # Não registrar corpo, chave, histórico ou mensagem original da exceção.
        logger.error(
            "Falha interna: %s; conversa %s", type(error).__name__, request.conversation_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível processar a mensagem. Tente novamente.",
        ) from None
