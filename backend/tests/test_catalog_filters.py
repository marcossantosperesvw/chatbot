"""Resolução de filtros em dados IGDB simulados, sem IDs fornecidos pelo modelo."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from app.catalog import igdb_client as module
from app.catalog.config import IGDBSettings
from app.catalog.errors import CatalogFilterError, CatalogProviderError
from app.catalog.schemas import CatalogDiscoveryQuery


TAXONOMIES = {
    "platforms": {"id": 6, "name": "PC (Microsoft Windows)"},
    "genres": {"id": 13, "name": "Simulator"},
    "game_modes": {"id": 1, "name": "Single player"},
}


def setup(monkeypatch, *, taxonomy=None, status=200):
    monkeypatch.setattr(module, "REQUEST_INTERVAL_SECONDS", 0)
    requests = []

    def handler(request):
        requests.append(request)
        if str(request.url) == module.TOKEN_URL:
            return httpx.Response(200, json={"access_token": "fake-token", "expires_in": 3600, "token_type": "bearer"})
        if str(request.url) == module.VALIDATE_URL:
            return httpx.Response(200, json={"client_id": "fake-client", "expires_in": 3600})
        endpoint = request.url.path.split("/")[-1]
        if endpoint == "games":
            return httpx.Response(200, json=[])
        return httpx.Response(status, json=[TAXONOMIES[endpoint]] if taxonomy is None else taxonomy)

    return httpx.MockTransport(handler), requests


def client(http):
    return module.IGDBClient(http, IGDBSettings(client_id="fake-client", client_secret="fake-secret"))


def test_combines_resolved_filters_with_and_without_title_search(monkeypatch):
    transport, requests = setup(monkeypatch)

    async def run():
        async with httpx.AsyncClient(transport=transport) as http:
            await client(http).search(CatalogDiscoveryQuery(platform="PC", genre="Simulator", game_mode="Single player"))

    asyncio.run(run())
    body = requests[-1].content.decode()
    assert "platforms = (6) & genres = (13) & game_modes = (1)" in body
    assert "search " not in body
    assert "sort total_rating_count desc;" in body
    assert len(requests) == 6


def test_filter_and_result_caches_are_bounded_separate_and_include_preferences(monkeypatch):
    transport, requests = setup(monkeypatch)
    monkeypatch.setattr(module, "CACHE_MAX_ENTRIES", 1)

    async def run():
        async with httpx.AsyncClient(transport=transport) as http:
            catalog = client(http)
            first = await catalog.search(CatalogDiscoveryQuery(platform="PC"))
            cached = await catalog.search(CatalogDiscoveryQuery(platform="pc"))
            other = await catalog.search(CatalogDiscoveryQuery(platform="PC", genre="Simulator"))
            assert not first.cached and cached.cached and not other.cached
            assert len(catalog._cache) == 1
            assert len(catalog._filter_cache) == 1

    asyncio.run(run())
    assert sum(request.url.path.endswith("/platforms") for request in requests) == 1
    assert sum(request.url.path.endswith("/games") for request in requests) == 2


def test_expired_filter_is_resolved_again(monkeypatch):
    transport, requests = setup(monkeypatch)
    clock = [0]
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: clock[0]))

    async def run():
        async with httpx.AsyncClient(transport=transport) as http:
            catalog = client(http)
            await catalog.search(CatalogDiscoveryQuery(platform="PC"))
            clock[0] = module.CACHE_TTL_SECONDS + 1
            await catalog.search(CatalogDiscoveryQuery(platform="PC"))

    asyncio.run(run())
    assert sum(request.url.path.endswith("/platforms") for request in requests) == 2


@pytest.mark.parametrize("payload", [[], [{"id": 1, "name": "Other"}],
                                     [{"id": 1, "name": "Simulator"}] * 2])
def test_unknown_or_ambiguous_filter_never_runs_unfiltered_search(monkeypatch, payload):
    transport, requests = setup(monkeypatch, taxonomy=payload)

    async def run():
        async with httpx.AsyncClient(transport=transport) as http:
            with pytest.raises(CatalogFilterError):
                await client(http).search(CatalogDiscoveryQuery(genre="Simulator"))

    asyncio.run(run())
    assert not any(request.url.path.endswith("/games") for request in requests)


def test_filter_is_quoted_not_raw_apicalypse(monkeypatch):
    malicious = 'Simulator"; fields *; where name="other'
    transport, requests = setup(monkeypatch, taxonomy=[])

    async def run():
        async with httpx.AsyncClient(transport=transport) as http:
            with pytest.raises(CatalogFilterError):
                await client(http).search(CatalogDiscoveryQuery(genre=malicious))

    asyncio.run(run())
    assert requests[-1].content.decode() == f"fields id,name; where name ~ {json.dumps(malicious)}; limit 2;"


@pytest.mark.parametrize("identifier", [True, "13", -1])
def test_provider_must_supply_valid_numeric_filter_id(monkeypatch, identifier):
    transport, _ = setup(monkeypatch, taxonomy=[{"id": identifier, "name": "Simulator"}])

    async def run():
        async with httpx.AsyncClient(transport=transport) as http:
            with pytest.raises(CatalogProviderError):
                await client(http).search(CatalogDiscoveryQuery(genre="Simulator"))

    asyncio.run(run())


@pytest.mark.parametrize("params", [{}, {"query": ""}, {"platform": "a\nb"}, {"genre": "x", "limit": 6}])
def test_discovery_requires_bounded_valid_input(params):
    with pytest.raises(ValidationError):
        CatalogDiscoveryQuery(**params)
