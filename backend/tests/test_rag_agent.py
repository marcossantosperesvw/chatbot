"""Ciclo completo do RAG no SDK e na API com HTTP/embeddings simulados."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from agents.tool_context import ToolContext
from fastapi.testclient import TestClient
from openai import AsyncOpenAI

from app.api.schemas import ChatRequest
from app.core.errors import AIProviderError
from app.main import app
from app.rag.config import BACKEND_ROOT, get_rag_settings
from app.rag.errors import RagError
from app.rag.index import KnowledgeIndex, build_index, save_index
from app.rag.retrieval import KnowledgeStore
from app.services import chat_service
from app.tools.catalog import CatalogContext, validate_reply_urls
from app.tools.knowledge import search_knowledge, validate_reply_citations


FIXTURES = Path(__file__).parent / "fixtures" / "rag"
GAME = "Cidade Aurora — jogo fictício"
URL = "https://example.com/guia"
CITATION = "[RAG:cidade-aurora-teste:2]"


def store(mode="lexical"):
    index = build_index(FIXTURES, allow_synthetic=True)
    data = index.model_dump(mode="json")
    for passage in data["passages"]:
        passage["chunk"]["metadata"]["source_url"] = URL
        if mode == "semantic":
            passage["vector"] = [1.0, 0.0]
    if mode == "semantic":
        data.update(mode="semantic", embedding_model="fake-embedding-model")
    return KnowledgeStore(KnowledgeIndex.model_validate(data), min_score=0)


async def invoke(state, **arguments):
    raw = json.dumps({"query": "bairros ruas", "game": GAME, "platform": None, "game_version": None} | arguments)
    return json.loads(await search_knowledge.on_invoke_tool(
        ToolContext(context=state, tool_name="search_knowledge", tool_call_id="test", tool_arguments=raw), raw,
    ))


def test_tool_returns_evidence_and_only_current_source_permissions():
    state = CatalogContext(None, knowledge=store())
    result = asyncio.run(invoke(state))
    assert result["status"] == "ok"
    assert result["passages"][0]["citation"] == CITATION
    assert result["passages"][0]["synthetic"] is True
    assert result["passages"][0]["source_url"] == URL
    assert state.allowed_urls == {URL}
    assert CITATION in state.allowed_citations
    validate_reply_urls(URL, state)
    validate_reply_citations(CITATION, state)
    assert not CatalogContext(None, knowledge=state.knowledge).allowed_citations


def test_tool_never_relaxes_filters_or_invents_evidence():
    state = CatalogContext(None, knowledge=store())
    result = asyncio.run(invoke(state, platform="Unknown"))
    assert result["status"] == "empty"
    assert not state.allowed_urls and not state.allowed_citations


def test_tool_quota_even_when_requested_concurrently():
    state = CatalogContext(None, knowledge=store())

    async def run():
        return await asyncio.gather(*(invoke(state) for _ in range(4)))

    assert [item["status"] for item in asyncio.run(run())] == ["ok", "ok", "limit_reached", "limit_reached"]


def test_disabled_and_invalid_query_are_safe():
    assert asyncio.run(invoke(CatalogContext(None)))["status"] == "unavailable"
    assert asyncio.run(invoke(CatalogContext(None), query=""))["status"] == "invalid_query"
    assert set(search_knowledge.params_json_schema["properties"]) == {"query", "game", "platform", "game_version"}


def test_failure_does_not_expose_documents_or_provider_details():
    async def fail(*args, **kwargs):
        raise RagError("secret document contents")

    result = asyncio.run(invoke(CatalogContext(None, knowledge=SimpleNamespace(search=fail))))
    assert result["status"] == "unavailable"
    assert "secret" not in json.dumps(result)


@pytest.mark.parametrize("marker", [CITATION, "[RAG:invented:1]", "[RAG:../secret]"])
def test_unknown_or_historical_citation_is_rejected(marker):
    with pytest.raises(AIProviderError):
        validate_reply_citations(marker, CatalogContext(None))


def install_sdk_transport(monkeypatch, *, invented=False):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    monkeypatch.setenv("OPENAI_MODEL", "fake-model")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "25")
    monkeypatch.setenv("OPENAI_MAX_OUTPUT_TOKENS", "800")
    sent, embedding_calls = [], []

    def handler(request):
        body = json.loads(request.content)
        if request.url.path.endswith("/embeddings"):
            embedding_calls.append(body)
            return httpx.Response(200, json={
                "object": "list", "model": "fake-embedding-model",
                "data": [{"object": "embedding", "index": 0, "embedding": [1.0, 0.0]}],
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            })
        sent.append(body)
        if len(sent) == 1:
            output = [{"type": "function_call", "id": "fc_rag", "call_id": "call_rag", "name": "search_knowledge",
                       "arguments": json.dumps({"query": "bairros ruas", "game": GAME, "platform": None, "game_version": None}),
                       "status": "completed"}]
        else:
            marker = "[RAG:invented:1]" if invented else CITATION
            output = [{"id": "msg_rag", "type": "message", "role": "assistant", "status": "completed",
                       "content": [{"type": "output_text", "text": f"Demonstração fictícia: conecte ruas aos bairros. {marker} Fonte: {URL}", "annotations": []}]}]
        return httpx.Response(200, json={
            "id": f"resp_{len(sent)}", "object": "response", "created_at": 1, "model": "fake-model",
            "status": "completed", "error": None, "incomplete_details": None, "instructions": None,
            "output": output, "parallel_tool_calls": False, "tools": [], "tool_choice": "auto",
        })

    def make_client(**kwargs):
        assert kwargs["max_retries"] == 0
        return AsyncOpenAI(**kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    monkeypatch.setattr(chat_service, "AsyncOpenAI", make_client)
    return sent, embedding_calls


@pytest.mark.parametrize("mode", ["lexical", "semantic"])
def test_real_sdk_retrieves_context_and_generates_cited_reply(monkeypatch, mode):
    sent, embeddings = install_sdk_transport(monkeypatch)
    request = ChatRequest(conversation_id=uuid4(), message="Como conectar ruas e bairros na Cidade Aurora?")
    reply = asyncio.run(chat_service.generate_reply(request, knowledge=store(mode)))
    assert CITATION in reply and URL in reply
    assert len(sent) == 2
    tool_output = next(item for item in sent[1]["input"] if item.get("type") == "function_call_output")
    evidence = json.loads(tool_output["output"])
    assert evidence["status"] == "ok"
    assert evidence["passages"][0]["synthetic"] is True
    assert {tool["name"] for tool in sent[0]["tools"]} == {"search_games", "search_knowledge"}
    assert len(embeddings) == (1 if mode == "semantic" else 0)
    if embeddings:
        assert embeddings[0]["model"] == "fake-embedding-model"


def test_api_loads_local_index_and_preserves_chat_contract(monkeypatch, tmp_path):
    path = tmp_path / "index.json"
    save_index(store().index, path)
    monkeypatch.setenv("RAG_ENABLED", "true")
    monkeypatch.setenv("RAG_INDEX_PATH", str(path))
    monkeypatch.setenv("RAG_ALLOW_SYNTHETIC", "true")
    monkeypatch.setenv("RAG_MIN_SCORE", "0")
    install_sdk_transport(monkeypatch)
    identifier = str(uuid4())
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"conversation_id": identifier, "message": "bairros ruas"})
    assert response.status_code == 200
    assert set(response.json()) == {"conversation_id", "message"}
    assert response.json()["conversation_id"] == identifier
    assert CITATION in response.json()["message"]["content"]


def test_fabricated_citation_is_rejected_in_final_reply(monkeypatch):
    install_sdk_transport(monkeypatch, invented=True)
    with pytest.raises(AIProviderError):
        asyncio.run(chat_service.generate_reply(
            ChatRequest(conversation_id=uuid4(), message="bairros ruas"), knowledge=store()))


@pytest.mark.parametrize("configuration", ["missing", "synthetic-blocked", "invalid"])
def test_invalid_optional_rag_does_not_break_health_or_basic_chat(monkeypatch, tmp_path, configuration):
    path = tmp_path / "index.json"
    if configuration == "synthetic-blocked":
        save_index(store().index, path)
    elif configuration == "invalid":
        path.write_text("invalid", encoding="utf-8")
    monkeypatch.setenv("RAG_ENABLED", "true")
    monkeypatch.setenv("RAG_INDEX_PATH", str(path))
    monkeypatch.setenv("RAG_ALLOW_SYNTHETIC", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    monkeypatch.setenv("OPENAI_MODEL", "fake-model")

    async def fake_run(*args, **kwargs):
        assert kwargs["context"].knowledge is None
        return SimpleNamespace(final_output="Posso explicar conceitos gerais de jogos.")

    monkeypatch.setattr(chat_service.Runner, "run", fake_run)
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert app.state.knowledge is None
        assert client.post("/api/chat", json={"conversation_id": str(uuid4()), "message": "O que é um RPG?"}).status_code == 200


def test_config_defaults_and_path_resolution(monkeypatch):
    monkeypatch.delenv("RAG_ENABLED", raising=False)
    assert get_rag_settings().enabled is False
    monkeypatch.setenv("RAG_ENABLED", "true")
    monkeypatch.setenv("RAG_INDEX_PATH", ".data/example.json")
    assert get_rag_settings().index_path == BACKEND_ROOT / ".data/example.json"
    monkeypatch.setenv("RAG_ENABLED", "nonsense")
    with pytest.raises(RagError):
        get_rag_settings()
