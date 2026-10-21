"""Ferramenta e ciclo real do SDK, sempre com catálogos/transporte simulados."""

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from agents.tool_context import ToolContext
from openai import AsyncOpenAI

from app.api.schemas import ChatRequest
from app.catalog.errors import (
    CatalogConfigurationError, CatalogFilterError, CatalogProviderError,
    CatalogRateLimitError, CatalogTimeoutError,
)
from app.catalog.schemas import CatalogGame, CatalogSearchResult, StoreLink
from app.core.errors import AIProviderError
from app.services import chat_service
from app.tools.catalog import CatalogContext, search_games, validate_reply_urls


URL = "https://store.steampowered.com/app/42/test/"
SOURCE = "https://www.igdb.com/games/test"


def result(*, empty=False):
    return CatalogSearchResult(query="", retrieved_at=datetime.now(UTC), games=[] if empty else [
        CatalogGame(id=42, name="Teste", summary="s" * 1000, platforms=["PC"],
                    genres=["Simulator"], game_modes=["Single player"], source_url=SOURCE,
                    store_links=[StoreLink(store="Steam", url=URL)]),
    ])


def fake_catalog(*, error=None, empty=False):
    calls = []

    async def search(params):
        calls.append(params)
        if error:
            raise error
        return result(empty=empty)

    return SimpleNamespace(search=search), calls


async def invoke(state, **arguments):
    arguments = dict.fromkeys(("query", "platform", "genre", "game_mode")) | arguments
    raw = json.dumps(arguments)
    return json.loads(await search_games.on_invoke_tool(
        ToolContext(context=state, tool_name="search_games", tool_call_id="test_call", tool_arguments=raw), raw,
    ))


def test_tool_contract_does_not_expose_dependencies_or_raw_queries():
    properties = search_games.params_json_schema["properties"]
    assert set(properties) == {"query", "platform", "genre", "game_mode"}
    assert search_games.params_json_schema["additionalProperties"] is False


def test_tool_passes_filters_and_returns_compact_sourced_data():
    catalog, calls = fake_catalog()
    state = CatalogContext(catalog)
    body = asyncio.run(invoke(state, platform="PC", genre="Simulator", game_mode="Single player"))
    assert body["status"] == "ok"
    assert body["source"] == "IGDB"
    assert body["retrieved_at"]
    assert calls[0].query is None
    assert calls[0].platform == "PC"
    assert calls[0].genre == "Simulator"
    assert calls[0].game_mode == "Single player"
    assert calls[0].limit == 5
    assert len(body["games"][0]["summary"]) == 500
    assert state.allowed_urls == {URL, SOURCE}


@pytest.mark.parametrize("error,status", [
    (CatalogConfigurationError("secret"), "unavailable"),
    (CatalogProviderError("secret"), "unavailable"),
    (CatalogTimeoutError("secret"), "unavailable"),
    (CatalogRateLimitError(7), "rate_limited"),
    (CatalogFilterError("genre"), "unknown_filter"),
    (RuntimeError("secret"), "unavailable"),
])
def test_tool_errors_are_safe(error, status):
    catalog, _ = fake_catalog(error=error)
    body = asyncio.run(invoke(CatalogContext(catalog), query="Teste"))
    assert body["status"] == status
    assert "secret" not in json.dumps(body)
    assert "games" not in body


def test_empty_result_is_not_a_provider_failure():
    catalog, _ = fake_catalog(empty=True)
    state = CatalogContext(catalog)
    body = asyncio.run(invoke(state, query="Inexistente"))
    assert body["status"] == "empty"
    assert body["games"] == []
    assert not state.allowed_urls


def test_empty_or_invalid_preferences_do_not_query_catalog():
    catalog, calls = fake_catalog()
    for arguments in ({}, {"platform": "  "}, {"query": "a" * 121}):
        body = asyncio.run(invoke(CatalogContext(catalog), **arguments))
        assert body["status"] == "invalid_query"
    assert not calls


def test_quota_is_per_request_even_if_model_asks_in_parallel():
    catalog, calls = fake_catalog()
    state = CatalogContext(catalog)

    async def run():
        return await asyncio.gather(*(invoke(state, query="Teste") for _ in range(4)))

    bodies = asyncio.run(run())
    assert [body["status"] for body in bodies] == ["ok", "ok", "limit_reached", "limit_reached"]
    assert len(calls) == 2
    assert asyncio.run(invoke(CatalogContext(catalog), query="Teste"))["status"] == "ok"


@pytest.mark.parametrize("text", [f"Loja: {URL}", f"Fonte: {SOURCE}.", f"[Loja]({URL})"])
def test_only_current_source_urls_are_accepted(text):
    validate_reply_urls(text, CatalogContext(None, allowed_urls={URL, SOURCE}))


@pytest.mark.parametrize("text", ["https://example.com/falso", URL.replace("42", "43"), "HTTP://example.com"])
def test_fabricated_urls_are_rejected(text):
    with pytest.raises(AIProviderError):
        validate_reply_urls(text, CatalogContext(None, allowed_urls={URL}))


@pytest.mark.parametrize("tool_rounds", [1, 2, 3])
def test_sdk_completes_tool_cycle_with_filters_without_network(monkeypatch, tool_rounds):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    monkeypatch.setenv("OPENAI_MODEL", "fake-model")
    monkeypatch.delenv("OPENAI_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("OPENAI_MAX_OUTPUT_TOKENS", raising=False)
    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        output = [{"type": "function_call", "id": "fc_1", "call_id": "call_1",
                   "name": "search_games", "arguments": json.dumps({
                       "query": None, "platform": "PC", "genre": "Simulator", "game_mode": "Single player",
                   }), "status": "completed"}] if len(sent) <= tool_rounds else [
            {"id": "msg_1", "type": "message", "role": "assistant", "status": "completed",
             "content": [{"type": "output_text", "text": f"Teste, segundo a IGDB. Loja: {URL}", "annotations": []}]},
        ]
        return httpx.Response(200, json={
            "id": f"resp_{len(sent)}", "object": "response", "created_at": 1,
            "model": "fake-model", "status": "completed", "error": None,
            "incomplete_details": None, "instructions": None, "output": output,
            "parallel_tool_calls": False, "tools": [], "tool_choice": "auto",
        })

    def make_client(**kwargs):
        return AsyncOpenAI(**kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    monkeypatch.setattr(chat_service, "AsyncOpenAI", make_client)
    catalog, calls = fake_catalog()
    request = ChatRequest(conversation_id=uuid4(), message="Construção de cidades para PC e solo.")
    if tool_rounds == 3:
        # Um modelo que insiste em ferramentas não pode manter um loop infinito.
        with pytest.raises(AIProviderError):
            asyncio.run(chat_service.generate_reply(request, catalog=catalog))
        assert len(sent) == 3
        assert len(calls) == 2
        return
    text = asyncio.run(chat_service.generate_reply(request, catalog=catalog))
    assert URL in text.content
    assert len(sent) == tool_rounds + 1
    assert len(calls) == tool_rounds
    assert calls[0].game_mode == "Single player"
    assert sent[0]["parallel_tool_calls"] is False
    assert sent[0]["store"] is False
    assert sent[0]["tools"][0]["name"] == "search_games"
    tool_output = next(item for item in sent[1]["input"] if item.get("type") == "function_call_output")
    assert json.loads(tool_output["output"])["source"] == "IGDB"
    assert "fake-key" not in tool_output["output"]


def test_link_from_history_is_not_whitelisted(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    monkeypatch.setenv("OPENAI_MODEL", "fake-model")

    async def fake_run(*args, **kwargs):
        return SimpleNamespace(final_output=URL)

    monkeypatch.setattr(chat_service.Runner, "run", fake_run)
    request = ChatRequest(conversation_id=uuid4(), message="Repita o link", history=[
        {"role": "assistant", "content": URL},
    ])
    with pytest.raises(AIProviderError):
        asyncio.run(chat_service.generate_reply(request))
