"""Configuração do agente; comportamento editável no Markdown ao lado deste módulo."""

from pathlib import Path

from agents import Agent, ModelSettings, OpenAIResponsesModel
from openai import AsyncOpenAI

from app.core.config import AISettings
from app.core.errors import AIConfigurationError
from app.tools.catalog import CatalogContext, search_games


INSTRUCTIONS_PATH = Path(__file__).resolve().with_suffix(".md")


def load_instructions() -> str:
    """Ler a versão salva em UTF-8 a cada criação do agente, sem cache ou fallback."""
    try:
        instructions = INSTRUCTIONS_PATH.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        raise AIConfigurationError() from None
    if not instructions:
        raise AIConfigurationError()
    return instructions


def create_game_agent(settings: AISettings, client: AsyncOpenAI) -> Agent[CatalogContext]:
    return Agent(
        name="Chat Jogos",
        instructions=load_instructions(),
        model=OpenAIResponsesModel(model=settings.model, openai_client=client),
        model_settings=ModelSettings(
            max_tokens=settings.max_output_tokens, store=False, parallel_tool_calls=False,
        ),
        tools=[search_games],
    )
