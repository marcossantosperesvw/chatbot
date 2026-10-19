"""Executa o agente usando somente o contexto recebido nesta requisição."""

import asyncio

from agents import AgentsException, RunConfig, Runner
from openai import APITimeoutError, AsyncOpenAI, OpenAIError

from app.agents.game_agent import create_game_agent
from app.api.schemas import ChatRequest
from app.catalog.igdb_client import IGDBClient
from app.core.config import get_ai_settings
from app.core.errors import AIProviderError, AITimeoutError
from app.tools.catalog import CatalogContext, validate_reply_urls


async def generate_reply(request: ChatRequest, *, catalog: IGDBClient | None = None) -> str:
    settings = get_ai_settings()
    messages = [item.model_dump() for item in request.history]
    messages.append({"role": "user", "content": request.message})
    context = CatalogContext(catalog=catalog)

    try:
        async with asyncio.timeout(settings.timeout_seconds):
            async with AsyncOpenAI(
                api_key=settings.api_key.get_secret_value(),
                base_url="https://api.openai.com/v1",
                timeout=settings.timeout_seconds,
                max_retries=0,
            ) as client:
                result = await Runner.run(
                    create_game_agent(settings, client),
                    input=messages,
                    context=context,
                    max_turns=3,  # Até duas rodadas de ferramenta e uma resposta final.
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
    return content.strip()
