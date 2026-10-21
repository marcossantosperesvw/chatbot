"""Mesma matriz de segurança no Python e no navegador, sem acessar lojas reais."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from agents.tool_context import ToolContext
from pydantic import ValidationError

from app.catalog.igdb_client import normalize_game, store_links
from app.catalog.schemas import CatalogGame, CatalogSearchResult, StoreLink
from app.catalog.trusted_stores import trusted_store
from app.tools.catalog import CatalogContext, search_games, selected_store_links


ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "shared/trusted-store-cases.json").read_text())
URL = "https://store.steampowered.com/app/42/test/"


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["url"])
def test_shared_destination_policy(case):
    assert trusted_store(case["url"]) == case["store"]


def test_catalog_discards_unapproved_urls_and_labels_are_not_spoofable():
    websites = [{"url":case["url"]} for case in CASES]
    links = store_links(websites)
    assert len(links) == sum(case["store"] is not None for case in CASES)
    assert all(trusted_store(link.url) == link.store for link in links)
    for url, store in [(URL, "Outra loja"), ("https://evil.example/test", "Steam")]:
        with pytest.raises(ValidationError):
            StoreLink(store=store, url=url)


def test_tool_revalidates_and_only_authorizes_current_mentioned_links():
    safe = StoreLink(store="Steam", url=URL)
    # Simular um objeto adulterado depois da validação Pydantic.
    altered = safe.model_copy(update={"url":"https://evil.example/game"})
    game = CatalogGame(id=42, name="Teste", store_links=[safe]).model_copy(update={"store_links":[altered, safe]})

    async def search(params):
        return CatalogSearchResult(query="Teste", retrieved_at=datetime.now(UTC), games=[game])

    state = CatalogContext(SimpleNamespace(search=search))
    args = json.dumps({"query":"Teste", "platform":None, "genre":None, "game_mode":None})
    context = ToolContext(context=state, tool_name="search_games", tool_call_id="test", tool_arguments=args)
    result = json.loads(asyncio.run(search_games.on_invoke_tool(context, args)))
    assert result["games"][0]["store_links"] == [{"store":"Steam", "url":URL}]
    assert "https://evil.example/game" not in state.allowed_urls
    assert selected_store_links("Sem loja nesta resposta.", state) == []
    assert selected_store_links(f"Confira {URL}. Repetindo: {URL}", state) == [safe]
    assert selected_store_links(URL, CatalogContext(None)) == []
    assert normalize_game({"id":42, "name":"Teste", "websites":[{"url":"https://evil.example/game"}]}).store_links == []
