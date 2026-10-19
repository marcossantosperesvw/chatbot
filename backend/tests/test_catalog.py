"""Contrato e cliente IGDB usando HTTP falso, sem Twitch ou OpenAI reais."""

import asyncio
import json
from types import SimpleNamespace
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient

from app.catalog import igdb_client as catalog
from app.catalog.config import IGDBSettings, get_igdb_settings
from app.catalog.errors import CatalogConfigurationError
from app.catalog.schemas import CatalogQuery
from app.main import app


GAME = {
    "id": 42, "name": "Jogo de teste", "summary": "Construção de cidades.",
    "platforms": [{"name": "PC"}], "genres": [{"name": "Simulator"}],
    "game_modes": [{"name": "Single player"}], "first_release_date": 1704067200,
    "url": "https://www.igdb.com/games/jogo-de-teste",
    "websites": [{"url": "https://store.steampowered.com/app/42/test/"}],
}


@pytest.fixture(autouse=True)
def fake_credentials(monkeypatch):
    monkeypatch.setenv("IGDB_CLIENT_ID", "test-client")
    monkeypatch.setenv("IGDB_CLIENT_SECRET", "test-secret")
    monkeypatch.delenv("IGDB_TIMEOUT_SECONDS", raising=False)


def handler_for(games=None, *, token_status=200, games_status=200, retry_after="5"):
    requests = []

    def handler(request):
        requests.append(request)
        if str(request.url) == catalog.TOKEN_URL:
            if token_status != 200:
                return httpx.Response(token_status, json={"message": "test-secret"})
            return httpx.Response(200, json={
                "access_token": "test-access-token", "expires_in": 3600, "token_type": "bearer",
            })
        if str(request.url) == catalog.VALIDATE_URL:
            assert request.headers["Authorization"] == "OAuth test-access-token"
            return httpx.Response(200, json={"client_id": "test-client", "expires_in": 3600})
        assert str(request.url) == catalog.GAMES_URL
        if games_status != 200:
            return httpx.Response(games_status, json={"message": "test-access-token"},
                                  headers={"Retry-After": retry_after})
        return httpx.Response(200, json=[GAME] if games is None else games)

    return handler, requests


@pytest.fixture
def client(monkeypatch):
    handler, requests = handler_for()
    real_client = httpx.AsyncClient

    def make_http(**kwargs):
        return real_client(**kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(httpx, "AsyncClient", make_http)
    with TestClient(app) as test_client:
        yield test_client, requests


def test_catalog_endpoint_returns_normalized_data_and_real_provider_urls(client):
    http, requests = client
    response = http.get("/api/games", params={"query": "  Jogo de teste  "})
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "IGDB"
    assert body["query"] == "Jogo de teste"
    assert body["cached"] is False
    game = body["games"][0]
    assert game["platforms"] == ["PC"]
    assert game["genres"] == ["Simulator"]
    assert game["game_modes"] == ["Single player"]
    assert game["release_date"] == "2024-01-01"
    assert game["source_url"] == GAME["url"]
    assert game["store_links"] == [{"store": "Steam", "url": GAME["websites"][0]["url"]}]
    assert len(requests) == 3
    token_request, _, game_request = requests
    assert not token_request.url.query
    assert parse_qs(token_request.content.decode()) == {
        "client_id": ["test-client"], "client_secret": ["test-secret"],
        "grant_type": ["client_credentials"],
    }
    assert game_request.headers["Authorization"] == "Bearer test-access-token"
    assert game_request.headers["Client-ID"] == "test-client"
    assert body["retrieved_at"]
    assert "test-secret" not in response.text
    assert "test-access-token" not in response.text


@pytest.mark.parametrize("params", [
    {}, {"query": ""}, {"query": "   "}, {"query": "a" * 121},
    {"query": "a\nb"}, {"query": "test", "limit": 0},
    {"query": "test", "limit": 11}, {"query": "test", "limit": "invalid"},
    {"query": "test", "extra": "fields *;"},
])
def test_rejects_invalid_query_before_requesting_provider(client, params):
    http, requests = client
    assert http.get("/api/games", params=params).status_code == 422
    assert not requests


def test_missing_credentials_only_blocks_catalog(client, monkeypatch):
    http, requests = client
    monkeypatch.delenv("IGDB_CLIENT_SECRET")
    assert http.get("/api/games", params={"query": "test"}).status_code == 503
    assert http.get("/api/health").status_code == 200
    assert not requests


@pytest.mark.parametrize("name,value", [
    ("IGDB_CLIENT_ID", ""), ("IGDB_CLIENT_SECRET", "  "),
    ("IGDB_TIMEOUT_SECONDS", "nan"), ("IGDB_TIMEOUT_SECONDS", "0"),
    ("IGDB_TIMEOUT_SECONDS", "16"),
])
def test_invalid_settings_are_safe(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(CatalogConfigurationError) as error:
        get_igdb_settings()
    assert "test-secret" not in str(error.value)


def test_settings_repr_masks_credentials():
    assert "test-secret" not in repr(get_igdb_settings())
    assert "test-client" not in repr(get_igdb_settings())


def test_cache_reuses_token_and_results_without_sharing_mutable_data():
    handler, requests = handler_for()

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = catalog.IGDBClient(http)
            first = await client.search(CatalogQuery(query="Test"))
            first.games[0].name = "Alterado por um consumidor"
            second = await client.search(CatalogQuery(query="test"))
            assert second.cached is True
            assert second.query == "test"
            assert second.games[0].name == GAME["name"]
            assert second.retrieved_at == first.retrieved_at
            assert len(requests) == 3
            await client.search(CatalogQuery(query="Outro jogo"))
            assert len(requests) == 4  # Mesmo token para outra consulta.

    asyncio.run(scenario())


def test_expired_cache_and_token_are_renewed_and_cache_is_bounded(monkeypatch):
    handler, requests = handler_for()
    clock = [100.0]
    monkeypatch.setattr(catalog, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(catalog, "CACHE_MAX_ENTRIES", 1)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = catalog.IGDBClient(http)
            await client.search(CatalogQuery(query="A"))
            clock[0] += 301
            assert (await client.search(CatalogQuery(query="A"))).cached is False
            assert len(requests) == 4
            clock[0] += 3600
            await client.search(CatalogQuery(query="B"))
            assert len(requests) == 7
            clock[0] += 1
            assert (await client.search(CatalogQuery(query="A"))).cached is False
            assert len(requests) == 8

    asyncio.run(scenario())


@pytest.mark.parametrize("token_status,games_status,expected", [
    (401, 200, 502), (403, 200, 502), (500, 200, 502),
    (200, 403, 502), (200, 500, 502), (200, 429, 429),
])
def test_provider_failures_have_safe_http_mapping(client, monkeypatch, caplog, token_status, games_status, expected):
    http, _ = client
    handler, requests = handler_for(token_status=token_status, games_status=games_status)
    monkeypatch.setattr(app.state.catalog._http, "_transport", httpx.MockTransport(handler))
    response = http.get("/api/games", params={"query": "test"})
    assert response.status_code == expected
    assert "test-secret" not in response.text + caplog.text
    assert "test-access-token" not in response.text + caplog.text
    assert len(requests) == (1 if token_status != 200 else 3)
    if expected == 429:
        assert response.headers["Retry-After"] == "5"
        again = http.get("/api/games", params={"query": "other"})
        assert again.status_code == 429
        assert len(requests) == 3


def test_unauthorized_token_is_renewed_once(client, monkeypatch):
    http, _ = client
    handler, requests = handler_for()
    game_calls = []

    def handler_with_expiry(request):
        if str(request.url) == catalog.GAMES_URL:
            game_calls.append(request)
            if len(game_calls) == 1:
                return httpx.Response(401)
        return handler(request)

    monkeypatch.setattr(app.state.catalog._http, "_transport", httpx.MockTransport(handler_with_expiry))
    assert http.get("/api/games", params={"query": "test"}).status_code == 200
    assert len(game_calls) == 2
    assert sum(str(request.url) == catalog.TOKEN_URL for request in requests) == 2


def test_repeated_unauthorized_response_stops_after_one_retry(client, monkeypatch):
    http, _ = client
    handler, requests = handler_for(games_status=401)
    monkeypatch.setattr(app.state.catalog._http, "_transport", httpx.MockTransport(handler))
    assert http.get("/api/games", params={"query": "test"}).status_code == 502
    assert len(requests) == 6


@pytest.mark.parametrize("exception,expected", [
    (httpx.ReadTimeout("sensitive error"), 504),
    (httpx.ConnectError("sensitive error"), 502),
])
def test_network_failure_mapping(client, monkeypatch, exception, expected):
    http, _ = client

    def handler(request):
        raise exception

    monkeypatch.setattr(app.state.catalog._http, "_transport", httpx.MockTransport(handler))
    response = http.get("/api/games", params={"query": "test"})
    assert response.status_code == expected
    assert "sensitive error" not in response.text


@pytest.mark.parametrize("payload", [{"unexpected": True}, [{"id": 42}], [{"id": True, "name": "test"}]])
def test_malformed_catalog_is_not_reported_as_success(client, monkeypatch, payload):
    http, _ = client
    handler, _ = handler_for(games=payload)
    monkeypatch.setattr(app.state.catalog._http, "_transport", httpx.MockTransport(handler))
    assert http.get("/api/games", params={"query": "test"}).status_code == 502


def test_empty_results_are_a_valid_success(client, monkeypatch):
    http, _ = client
    handler, _ = handler_for(games=[])
    monkeypatch.setattr(app.state.catalog._http, "_transport", httpx.MockTransport(handler))
    response = http.get("/api/games", params={"query": "does not exist"})
    assert response.status_code == 200
    assert response.json()["games"] == []


def test_partial_metadata_does_not_invent_data():
    game = catalog.normalize_game({"id": 42, "name": "Test"})
    assert game.summary is game.release_date is game.source_url is None
    assert game.platforms == game.store_links == []


def test_only_provider_https_store_links_on_known_domains_are_exposed():
    accepted = [
        "https://store.steampowered.com/app/42/test/",
        "https://my-game.itch.io/game", "https://www.gog.com/en/game/test",
    ]
    rejected = [
        "javascript:alert(1)", "http://store.steampowered.com/app/42/",
        "https://store.steampowered.com.evil.example/game",
        "https://test:secret@store.steampowered.com/app/42/",
        "https://store.steampowered.com:8000/app/42/",
        "https://unknown-store.example/game", "https://[invalid", None,
    ]
    links = catalog.store_links([{"url": url} for url in accepted + rejected + accepted])
    assert [link.url for link in links] == accepted


def test_query_is_quoted_as_a_literal_and_not_inserted_as_commands(client):
    http, requests = client
    query = 'game"; fields *; search "other\\game'
    assert http.get("/api/games", params={"query": query, "limit": 3}).status_code == 200
    assert requests[-1].content.decode() == (
        f"search {json.dumps(query, ensure_ascii=False)}; fields {catalog.FIELDS}; limit 3;"
    )


def test_openapi_documents_catalog_errors(client):
    http, _ = client
    operation = http.get("/openapi.json").json()["paths"]["/api/games"]["get"]
    assert {"200", "422", "429", "502", "503", "504"} <= set(operation["responses"])


@pytest.mark.parametrize("payload", [
    {}, {"access_token": "", "expires_in": 100, "token_type": "bearer"},
    {"access_token": "test", "expires_in": True, "token_type": "bearer"},
    {"access_token": "test", "expires_in": 0, "token_type": "bearer"},
])
def test_invalid_token_payload_never_reaches_catalog(client, monkeypatch, payload):
    http, _ = client
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(app.state.catalog._http, "_transport", httpx.MockTransport(handler))
    assert http.get("/api/games", params={"query": "test"}).status_code == 502
    assert len(requests) == 1
    assert str(requests[0].url) == catalog.TOKEN_URL


def test_token_for_another_application_is_rejected(client, monkeypatch):
    http, _ = client
    handler, requests = handler_for()

    def wrong_client(request):
        if str(request.url) == catalog.VALIDATE_URL:
            return httpx.Response(200, json={"client_id": "someone-else", "expires_in": 3600})
        return handler(request)

    monkeypatch.setattr(app.state.catalog._http, "_transport", httpx.MockTransport(wrong_client))
    assert http.get("/api/games", params={"query": "test"}).status_code == 502
    assert app.state.catalog._token is None
    assert not any(str(request.url) == catalog.GAMES_URL for request in requests)


def test_concurrent_identical_queries_only_call_provider_once():
    handler, requests = handler_for()

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = catalog.IGDBClient(http)
            results = await asyncio.gather(*[
                client.search(CatalogQuery(query="test")) for _ in range(3)
            ])
            assert sum(not result.cached for result in results) == 1
            assert len(requests) == 3

    asyncio.run(scenario())


def test_total_deadline_cancels_slow_provider(client, monkeypatch):
    http, _ = client
    monkeypatch.setenv("IGDB_TIMEOUT_SECONDS", "1")
    cancelled = []

    async def slow(request):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.append(True)

    monkeypatch.setattr(app.state.catalog._http, "_transport", httpx.MockTransport(slow))
    assert http.get("/api/games", params={"query": "test"}).status_code == 504
    assert cancelled == [True]


def test_maintenance_invalidates_revoked_token_and_next_search_recovers(monkeypatch):
    handler, requests = handler_for()
    validation_fails = [False]

    def with_revocation(request):
        if str(request.url) == catalog.VALIDATE_URL and validation_fails[0]:
            return httpx.Response(401)
        return handler(request)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(with_revocation)) as http:
            client = catalog.IGDBClient(http)
            await client.search(CatalogQuery(query="test"))
            validation_fails[0] = True
            original_sleep = asyncio.sleep
            ticks = []

            async def one_tick(seconds):
                assert seconds == 3600
                ticks.append(True)
                if len(ticks) > 1:
                    raise asyncio.CancelledError()

            # Substituir apenas a referência de asyncio deste módulo.
            monkeypatch.setattr(catalog, "asyncio", SimpleNamespace(
                sleep=one_tick, timeout=asyncio.timeout,
            ))
            with pytest.raises(asyncio.CancelledError):
                await client.maintain_token()
            assert client._token is None
            monkeypatch.setattr(catalog, "asyncio", asyncio)
            assert asyncio.sleep is original_sleep
            validation_fails[0] = False
            await client.search(CatalogQuery(query="other"))
            assert sum(str(request.url) == catalog.TOKEN_URL for request in requests) == 2

    asyncio.run(scenario())
