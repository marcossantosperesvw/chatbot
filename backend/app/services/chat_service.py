"""Executa o agente usando somente o contexto recebido nesta requisição."""

import asyncio

from agents import AgentsException, RunConfig, Runner
from openai import APITimeoutError, AsyncOpenAI, OpenAIError

from app.agents.game_agent import create_game_agent
from app.api.schemas import ChatRequest
from app.catalog.igdb_client import IGDBClient
from app.core.config import get_ai_settings
from app.core.errors import AIProviderError, AITimeoutError
from app.rag.retrieval import KnowledgeStore
from app.tools.catalog import CatalogContext, validate_reply_urls
from app.tools.knowledge import validate_reply_citations


async def generate_reply(
    request: ChatRequest, *, catalog: IGDBClient | None = None,
    knowledge: KnowledgeStore | None = None,
) -> str:
    settings = get_ai_settings()
    messages = [item.model_dump() for item in request.history]
    messages.append({"role": "user", "content": request.message})
    context = CatalogContext(catalog=catalog, knowledge=knowledge)

    try:
        async with asyncio.timeout(settings.timeout_seconds):
            async with AsyncOpenAI(
                api_key=settings.api_key.get_secret_value(),
                base_url="https://api.openai.com/v1",
                timeout=settings.timeout_seconds,
                max_retries=0,
            ) as client:
                context.embedding_client = client
                result = await Runner.run(
                    create_game_agent(settings, client),
                    input=messages,
                    context=context,
                    max_turns=5 if knowledge else 3,
                    run_config=RunConfig(tracing_disabled=True),
                )
    except (TimeoutError, APITimeoutError):
        raise AITimeoutError() from None
    except (OpenAIError, AgentsException):
        raise AIProviderError() from None

    content = result.final_output
    if not isinstance(content, str) or not 1 <= len(content.strip()) <= 4000:
        # Não cortar silenciosamente nem invalidar o histórico do próximo turno.
        raise AIProviderError()
    validate_reply_urls(content, context)
    validate_reply_citations(content, context)
    return content.strip()
