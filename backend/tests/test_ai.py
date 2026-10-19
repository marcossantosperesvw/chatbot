"""Integração real do SDK com transporte HTTP falso: nenhuma chamada à OpenAI."""

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI

from app.api.schemas import ChatRequest
from app.agents import game_agent
from app.core.config import get_ai_settings
from app.core.errors import AIConfigurationError
from app.main import app
from app.services import chat_service


@pytest.fixture(autouse=True)
def ai_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-a-real-credential")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.delenv("OPENAI_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("OPENAI_MAX_OUTPUT_TOKENS", raising=False)


def request(history=None):
    return ChatRequest(conversation_id=uuid4(), message="O que recomenda?", history=history or [])


@pytest.mark.parametrize("key,value", [
    ("OPENAI_API_KEY", ""), ("OPENAI_API_KEY", "   "),
    ("OPENAI_MODEL", ""), ("OPENAI_TIMEOUT_SECONDS", "26"),
    ("OPENAI_TIMEOUT_SECONDS", "nan"), ("OPENAI_MAX_OUTPUT_TOKENS", "invalid"),
    ("OPENAI_MAX_OUTPUT_TOKENS", "0"),
])
def test_rejects_invalid_settings(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(AIConfigurationError):
        get_ai_settings()


def test_settings_mask_secret():
    assert "test-key-not-a-real-credential" not in repr(get_ai_settings())


def install_transport(monkeypatch, *, text="Recomendo um jogo cooperativo.", status=200):
    sent = []
    clients = []

    def handler(http_request):
        sent.append(json.loads(http_request.content))
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "segredo-do-provedor", "type": "api_error", "code": "test"}})
        return httpx.Response(200, json={
            "id": "resp_test", "object": "response", "created_at": 1,
            "model": "test-model", "status": "completed", "error": None,
            "incomplete_details": None, "instructions": None,
            "output": [{"id": "msg_test", "type": "message", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": text, "annotations": []}]}],
            "parallel_tool_calls": False, "tools": [], "tool_choice": "auto",
        })

    def make_client(**kwargs):
        assert kwargs["max_retries"] == 0
        assert kwargs["base_url"] == "https://api.openai.com/v1"
        client = AsyncOpenAI(**kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        clients.append(client)
        return client

    monkeypatch.setattr(chat_service, "AsyncOpenAI", make_client)
    return sent, clients


def test_sdk_sends_history_once_and_disables_storage_and_traces(monkeypatch):
    sent, clients = install_transport(monkeypatch)
    original_run = chat_service.Runner.run
    configs = []

    async def observed_run(*args, **kwargs):
        configs.append(kwargs["run_config"])
        assert kwargs["max_turns"] == 3
        return await original_run(*args, **kwargs)

    monkeypatch.setattr(chat_service.Runner, "run", observed_run)
    history = [{"role": "user", "content": "Jogo no PC."},
               {"role": "assistant", "content": "Você joga com amigos?"}]
    result = asyncio.run(chat_service.generate_reply(request(history)))

    assert result == "Recomendo um jogo cooperativo."
    assert len(sent) == 1
    assert sent[0]["model"] == "test-model"
    assert sent[0]["input"] == history + [{"role": "user", "content": "O que recomenda?"}]
    assert sent[0]["store"] is False
    assert sent[0]["max_output_tokens"] == 800
    assert "Chat Jogos" in sent[0]["instructions"]
    assert sent[0]["instructions"] == game_agent.load_instructions()
    assert configs[0].tracing_disabled is True
    assert clients[0].is_closed()


@pytest.mark.parametrize("rule", [
    "Multiplayer não comprova competição",
    "Não apresente 'o mais próximo' ignorando um requisito essencial",
    "Só ofereça aproximações se o usuário aceitar flexibilizar o requisito",
    "Não transfira características, plataformas, modos ou links entre jogos",
    "Não use Markdown",
])
def test_sdk_receives_recommendation_rules(monkeypatch, rule):
    """Confere configuração enviada; não avalia obediência de um modelo real."""
    sent, _ = install_transport(monkeypatch, text="Você quer competir de que forma?")
    asyncio.run(chat_service.generate_reply(request()))
    # Normalizar apenas espaços para permitir reformatar as linhas do prompt.
    assert rule in " ".join(sent[0]["instructions"].split())


def test_sdk_reads_saved_markdown_on_each_request(monkeypatch, tmp_path):
    path = tmp_path / "instructions.md"
    monkeypatch.setattr(game_agent, "INSTRUCTIONS_PATH", path)
    sent, _ = install_transport(monkeypatch)
    for text in ("# Perfil\nResponda de forma breve.", "# Perfil\nFaça uma pergunta por vez."):
        path.write_text(text, encoding="utf-8")
        asyncio.run(chat_service.generate_reply(request()))
        assert sent[-1]["instructions"] == text
    assert len(sent) == 2


@pytest.mark.parametrize("content", [None, "", "  \n\t "])
def test_invalid_instructions_return_503_without_provider_call(monkeypatch, tmp_path, content):
    path = tmp_path / "instructions.md"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(game_agent, "INSTRUCTIONS_PATH", path)
    sent, clients = install_transport(monkeypatch)
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        response = client.post("/api/chat", json=request().model_dump(mode="json"))
    assert response.status_code == 503
    assert not sent
    assert clients[0].is_closed()
    assert str(path) not in response.text


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
def test_provider_failure_is_safe_and_not_retried(monkeypatch, status, caplog):
    sent, clients = install_transport(monkeypatch, status=status)
    with TestClient(app) as client:
        response = client.post("/api/chat", json=request().model_dump(mode="json"))
    assert response.status_code == 502
    assert len(sent) == 1
    assert clients[0].is_closed()
    assert "segredo-do-provedor" not in response.text + caplog.text
    assert "test-key-not-a-real-credential" not in response.text + caplog.text


@pytest.mark.parametrize("text", ["", "   ", "a" * 4001])
def test_invalid_model_output_is_not_saved(monkeypatch, text):
    install_transport(monkeypatch, text=text)
    with TestClient(app) as client:
        response = client.post("/api/chat", json=request().model_dump(mode="json"))
    assert response.status_code == 502


def test_conversations_have_no_shared_history(monkeypatch):
    sent, _ = install_transport(monkeypatch)
    asyncio.run(chat_service.generate_reply(request([{"role": "user", "content": "Somente A"}])))
    asyncio.run(chat_service.generate_reply(request()))
    assert "Somente A" in json.dumps(sent[0])
    assert "Somente A" not in json.dumps(sent[1])


def test_missing_key_returns_503_but_health_works(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY")
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.post("/api/chat", json=request().model_dump(mode="json")).status_code == 503


def test_timeout_returns_504(monkeypatch):
    async def slow_runner(*args, **kwargs):
        raise TimeoutError("Detalhe interno")

    monkeypatch.setattr(chat_service.Runner, "run", slow_runner)
    with TestClient(app) as client:
        response = client.post("/api/chat", json=request().model_dump(mode="json"))
    assert response.status_code == 504
    assert "Detalhe interno" not in response.text


def test_deadline_cancels_slow_run_and_closes_client(monkeypatch):
    _, clients = install_transport(monkeypatch)
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "1")
    cancelled = []

    async def slow_runner(*args, **kwargs):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.append(True)

    monkeypatch.setattr(chat_service.Runner, "run", slow_runner)
    with TestClient(app) as client:
        response = client.post("/api/chat", json=request().model_dump(mode="json"))
    assert response.status_code == 504
    assert cancelled == [True]
    assert clients[0].is_closed()


@pytest.mark.parametrize("output", [None, {"text": "Não é texto simples"}])
def test_rejects_nontext_output(monkeypatch, output):
    install_transport(monkeypatch)

    async def fake_runner(*args, **kwargs):
        return SimpleNamespace(final_output=output)

    monkeypatch.setattr(chat_service.Runner, "run", fake_runner)
    with TestClient(app) as client:
        assert client.post("/api/chat", json=request().model_dump(mode="json")).status_code == 502


def test_accepts_output_at_unicode_limit_without_truncating(monkeypatch):
    install_transport(monkeypatch, text="🎮" * 4000)
    result = asyncio.run(chat_service.generate_reply(request()))
    assert result == "🎮" * 4000
