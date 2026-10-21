"""Regressão do corpus real e isolamento de escopos, sem rede ou geração paga."""

import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.rag import cli
from app.rag.index import KnowledgeIndex, build_index, load_index, save_index
from app.rag.retrieval import KnowledgeQuery, KnowledgeStore
from app.rag.schemas import DocumentMetadata
from app.tools.catalog import CatalogContext
from app.tools.knowledge import search_knowledge
from agents.tool_context import ToolContext


ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((Path(__file__).parent / "evaluation/knowledge-cases.json").read_text())


@pytest.fixture(scope="module")
def corpus():
    return build_index(ROOT / "knowledge")


@pytest.mark.parametrize("case", [c for c in CASES if c.get("evaluation") != "conversation"], ids=lambda c: c["id"])
def test_real_corpus_retrieves_supporting_evidence(corpus, case):
    params = {k: case[k] for k in ("query", "game", "product", "platform") if k in case}
    hits = asyncio.run(KnowledgeStore(corpus).search(KnowledgeQuery(**params)))
    if case["expected_document"] is None:
        assert hits == []
    else:
        assert hits and hits[0].chunk.metadata.document_id == case["expected_document"]
        for evidence in case["evidence"]:
            assert evidence in hits[0].chunk.text


def test_corpus_keeps_context_and_editorial_material_out(corpus):
    assert len(corpus.revisions) >= 7
    assert len(corpus.passages) == len(corpus.revisions)
    for passage in corpus.passages:
        meta = passage.chunk.metadata
        assert meta.scope == "general" and meta.game is None and not meta.synthetic
        assert meta.products and meta.source_url
        assert "Perguntas de avaliação" not in passage.chunk.text
        assert "revisão humana pendente" not in passage.chunk.text


def test_mixed_index_does_not_cross_game_and_general_scope(corpus):
    games = build_index(Path(__file__).parent / "fixtures/rag", allow_synthetic=True)
    index = KnowledgeIndex(max_chars=2000, revisions=corpus.revisions | games.revisions,
                           passages=corpus.passages + games.passages)
    store = KnowledgeStore(index)
    assert asyncio.run(store.search(KnowledgeQuery(query="bairros ruas"))) == []
    hits = asyncio.run(store.search(KnowledgeQuery(query="bairros ruas", game="Cidade Aurora — jogo fictício")))
    assert hits and all(h.chunk.metadata.scope == "game" for h in hits)
    assert asyncio.run(store.search(KnowledgeQuery(query="Steam Cloud", game="Cidade Aurora — jogo fictício"))) == []


def test_scope_validation_and_backwards_compatibility(corpus):
    data = corpus.passages[0].chunk.metadata.model_dump()
    for invalid in ({"game":"Um jogo"}, {"game_version":"1"}, {"scope":"game"}):
        with pytest.raises(ValidationError):
            DocumentMetadata(**(data | invalid))
    with pytest.raises(ValidationError):
        KnowledgeQuery(query="cloud", game_version="1")
    legacy = json.loads((Path(__file__).parent / "fixtures/rag/cidade-aurora.json").read_text())
    assert DocumentMetadata(**legacy).scope == "game"


def test_cli_general_search_and_persisted_metadata(corpus, tmp_path, capsys):
    path = tmp_path / "index.json"
    save_index(corpus, path)
    assert load_index(path) == corpus
    assert cli.main(["search", "--index", str(path), "--query", "gatilhos adaptáveis Android",
                     "--product", "DualSense", "--platform", "Android"]) == 0
    assert "dualsense-dispositivos" in capsys.readouterr().out


def test_general_tool_contract_and_citations(corpus):
    state = CatalogContext(None, knowledge=KnowledgeStore(corpus))
    args = dict(query="gatilhos adaptáveis Android", game=None, platform="Android",
                game_version=None, product="DualSense")
    raw = json.dumps(args)
    context = ToolContext(context=state, tool_name="search_knowledge", tool_call_id="test", tool_arguments=raw)
    result = json.loads(asyncio.run(search_knowledge.on_invoke_tool(context, raw)))
    assert result["status"] == "ok"
    passage = result["passages"][0]
    assert passage["scope"] == "general" and passage["game"] is None
    assert passage["products"] == ["DualSense", "PlayStation"]
    assert passage["citation"] in state.allowed_citations
    assert passage["source_url"] in state.allowed_urls
    schema = search_knowledge.params_json_schema
    assert set(schema["required"]) == set(schema["properties"])
    assert {t["type"] for t in schema["properties"]["game"]["anyOf"]} == {"string", "null"}
