"""Índice e recuperação lexical/semântica com vetores fictícios, sem rede."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import httpx
from openai import AsyncOpenAI
from pydantic import ValidationError

from app.rag import cli
from app.rag.embeddings import cosine, embed_texts, validate_vector
from app.rag.errors import RagError
from app.rag.index import IndexedPassage, KnowledgeIndex, build_index, load_index, save_index
from app.rag.ingestion import chunk_document
from app.rag.retrieval import KnowledgeQuery, KnowledgeStore
from app.rag.schemas import DocumentMetadata, KnowledgeDocument


FIXTURES = Path(__file__).parent / "fixtures" / "rag"


@pytest.mark.parametrize("case", json.loads((FIXTURES / "retrieval-cases.json").read_text(encoding="utf-8")),
                         ids=lambda case: case["name"])
def test_editable_retrieval_cases(case):
    store = KnowledgeStore(build_index(FIXTURES, allow_synthetic=True))
    hits = asyncio.run(store.search(KnowledgeQuery(query=case["query"], game=case["game"])))
    if case["expected_chunk"] is None:
        assert hits == []
    else:
        assert hits and hits[0].chunk.chunk_id == case["expected_chunk"]


def index_with(*, mode="lexical", synthetic=False):
    passages = []
    for identifier, game, platform, version, text, vector in [
        ("ponte", "Aurora", "PC", "1", "Para construir uma ponte, conecte as duas margens do rio.", (1, 0)),
        ("torre", "Aurora", "PS5", "2", "Para construir uma torre, organize os blocos na vertical.", (0, 1)),
        ("outro", "Outro jogo", "PC", "1", "Uma ponte tem pilares e o rio tem duas margens.", (1, 0)),
    ]:
        metadata = DocumentMetadata(document_id=identifier, title=identifier, game=game,
                                    platforms=(platform,), game_version=version,
                                    source="Teste fictício", reviewed_at="2026-10-19", synthetic=synthetic,
                                    source_url="https://example.com/guia")
        chunk = chunk_document(KnowledgeDocument(metadata=metadata, text=text))[0]
        passages.append(IndexedPassage(chunk=chunk, vector=vector if mode == "semantic" else None))
    return KnowledgeIndex(mode=mode, embedding_model="fake-embedding-model" if mode == "semantic" else None,
                          revisions={p.chunk.metadata.document_id: "a" * 64 for p in passages},
                          passages=tuple(passages))


def fake_embedding_client(vectors=None, *, incomplete=False):
    calls = []

    async def create(**kwargs):
        calls.append(kwargs)
        values = vectors or [(1.0, 0.0)] * len(kwargs["input"])
        return SimpleNamespace(data=[SimpleNamespace(index=n, embedding=v) for n, v in enumerate(values)] if not incomplete else [])

    return SimpleNamespace(embeddings=SimpleNamespace(create=create)), calls


def test_build_blocks_synthetic_data_by_default():
    with pytest.raises(RagError, match="sintético"):
        build_index(FIXTURES)
    index = build_index(FIXTURES, allow_synthetic=True)
    assert len(index.passages) == 4
    assert all(len(digest) == 64 for digest in index.revisions.values())


def test_round_trip_and_explicit_overwrite(tmp_path):
    index = index_with()
    path = tmp_path / "index.json"
    save_index(index, path)
    assert load_index(path) == index
    before = path.read_bytes()
    with pytest.raises(RagError, match="existe"):
        save_index(index, path)
    assert path.read_bytes() == before
    save_index(index, path, force=True)
    assert load_index(path) == index
    assert list(tmp_path.iterdir()) == [path]


def test_loading_synthetic_index_requires_permission(tmp_path):
    path = tmp_path / "index.json"
    save_index(index_with(synthetic=True), path)
    with pytest.raises(RagError, match="sintético"):
        load_index(path)
    assert load_index(path, allow_synthetic=True).passages[0].chunk.metadata.synthetic


@pytest.mark.parametrize("payload", ["", "{}", "not json", '{"schema_version":42}'])
def test_invalid_index_is_safe(tmp_path, payload):
    path = tmp_path / "index.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(RagError):
        load_index(path)


def test_duplicate_document_ids_fail_without_an_index(tmp_path):
    for number in range(2):
        (tmp_path / f"a{number}.md").write_text("# Guia\nTexto de teste.", encoding="utf-8")
        (tmp_path / f"a{number}.json").write_text(index_with().passages[0].chunk.metadata.model_dump_json(), encoding="utf-8")
    with pytest.raises(RagError, match="duplicado"):
        build_index(tmp_path)


def test_revision_changes_when_content_changes(tmp_path):
    md = tmp_path / "guia.md"
    md.write_text("# Ponte\nConectar margens.", encoding="utf-8")
    md.with_suffix(".json").write_text(index_with().passages[0].chunk.metadata.model_dump_json(), encoding="utf-8")
    first = build_index(tmp_path)
    md.write_text("# Ponte\nConectar margens com pilares.", encoding="utf-8")
    second = build_index(tmp_path)
    assert first.revisions != second.revisions


def test_symlink_is_not_followed_into_another_base(tmp_path):
    directory = tmp_path / "base"
    directory.mkdir()
    (directory / "guia.md").symlink_to(FIXTURES / "cidade-aurora.md")
    (directory / "guia.json").symlink_to(FIXTURES / "cidade-aurora.json")
    with pytest.raises(RagError, match="simbólicos"):
        build_index(directory, allow_synthetic=True)


def test_empty_directory_is_not_a_valid_index(tmp_path):
    (tmp_path / "README.md").write_text("Documentação, não corpus.", encoding="utf-8")
    with pytest.raises(RagError, match="Nenhum documento"):
        build_index(tmp_path)


def test_lexical_search_ranks_evidence_not_only_game_name():
    store = KnowledgeStore(index_with(), min_score=0)
    hits = asyncio.run(store.search(KnowledgeQuery(query="Como conectar as margens com uma ponte?", game="Aurora")))
    assert hits[0].chunk.metadata.document_id == "ponte"
    assert all(hit.chunk.metadata.game == "Aurora" for hit in hits)
    assert asyncio.run(store.search(KnowledgeQuery(query="Aurora", game="Aurora"))) == []
    assert asyncio.run(store.search(KnowledgeQuery(query="astronave espacial", game="Aurora"))) == []


@pytest.mark.parametrize("filters,expected", [
    ({"platform": "pc", "game_version": "1"}, ["ponte"]),
    ({"platform": "PC", "game_version": "2"}, []),
    ({"platform": "Xbox"}, []),
    ({"game_version": "99"}, []),
])
def test_filters_are_exact_and_never_relaxed(filters, expected):
    hits = asyncio.run(KnowledgeStore(index_with(), min_score=0).search(
        KnowledgeQuery(query="construir", game="ÁURORA", **filters)))
    assert [hit.chunk.metadata.document_id for hit in hits] == expected


def test_unknown_metadata_does_not_confirm_platform():
    original = index_with()
    passage = original.passages[0]
    metadata = passage.chunk.metadata.model_copy(update={"platforms": (), "game_version": None})
    chunk = passage.chunk.model_copy(update={"metadata": metadata})
    index = original.model_copy(update={"passages": (IndexedPassage(chunk=chunk),)})
    store = KnowledgeStore(index, min_score=0)
    assert asyncio.run(store.search(KnowledgeQuery(query="ponte", game="Aurora", platform="PC"))) == []


def test_semantic_search_uses_recorded_model_and_same_dimensions():
    client, calls = fake_embedding_client()
    hits = asyncio.run(KnowledgeStore(index_with(mode="semantic"), min_score=0.5).search(
        KnowledgeQuery(query="ligar lados do curso de água", game="Aurora"), client=client))
    assert [hit.chunk.metadata.document_id for hit in hits] == ["ponte"]
    assert calls[0]["model"] == "fake-embedding-model"
    assert calls[0]["input"] == ["ligar lados do curso de água"]
    assert hits[0].score == pytest.approx(1)


def test_semantic_search_does_not_call_provider_for_missing_game():
    client, calls = fake_embedding_client()
    hits = asyncio.run(KnowledgeStore(index_with(mode="semantic")).search(
        KnowledgeQuery(query="ponte", game="Inexistente"), client=client))
    assert hits == [] and calls == []


def test_semantic_query_dimension_mismatch_is_not_silently_accepted():
    client, _ = fake_embedding_client(vectors=[(1, 0, 0)])
    with pytest.raises(RagError, match="Dimensão"):
        asyncio.run(KnowledgeStore(index_with(mode="semantic")).search(
            KnowledgeQuery(query="ponte", game="Aurora"), client=client))


@pytest.mark.parametrize("vector", [[], [0, 0], [True, 1], [float("nan"), 1], [float("inf"), 1], ["1", "2"]])
def test_invalid_vectors_are_rejected(vector):
    with pytest.raises(RagError):
        validate_vector(vector)


def test_embedding_batches_are_bounded_and_complete():
    client, calls = fake_embedding_client()
    assert len(asyncio.run(embed_texts(client, "fake-model", ["test"] * 33))) == 33
    assert [len(call["input"]) for call in calls] == [32, 1]
    client, _ = fake_embedding_client(incomplete=True)
    with pytest.raises(RagError, match="incompleta"):
        asyncio.run(embed_texts(client, "fake-model", ["test"]))


def test_model_cannot_mix_vector_modes_or_duplicate_ids():
    data = index_with().model_dump()
    with pytest.raises(ValidationError):
        KnowledgeIndex(**(data | {"mode": "semantic"}))
    with pytest.raises(ValidationError):
        KnowledgeIndex(**(data | {"passages": [data["passages"][0]] * 2}))


def test_atomic_replacement_failure_preserves_previous_index(tmp_path, monkeypatch):
    path = tmp_path / "index.json"
    save_index(index_with(), path)
    original = path.read_bytes()

    def fail(*args):
        raise OSError("internal")

    monkeypatch.setattr("app.rag.index.os.replace", fail)
    with pytest.raises(RagError):
        save_index(index_with(), path, force=True)
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]


def test_index_cannot_transfer_citation_to_another_document():
    data = index_with().model_dump()
    data["passages"][0]["chunk"]["chunk_id"] = "outro:1"
    with pytest.raises(ValidationError):
        KnowledgeIndex(**data)


def test_cosine_is_stable_for_large_finite_components():
    assert cosine((1e300, 1e300), (1e300, 1e300)) == pytest.approx(1)


@pytest.mark.parametrize("status", [401, 429, 500])
def test_embedding_provider_failure_is_safe_and_not_retried(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"message": "secret", "type": "api_error"}})

    async def run():
        async with AsyncOpenAI(api_key="fake-key", max_retries=0,
                               http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))) as client:
            with pytest.raises(RagError) as error:
                await embed_texts(client, "fake-model", ["test"])
            assert "secret" not in str(error.value)

    asyncio.run(run())
    assert len(calls) == 1


def test_cli_round_trip_and_no_implicit_payment(tmp_path, capsys, monkeypatch):
    output = tmp_path / "index.json"
    assert cli.main(["build", "--input", str(FIXTURES), "--output", str(output), "--allow-synthetic"]) == 0
    assert "lexical" in capsys.readouterr().out
    assert cli.main(["search", "--index", str(output), "--game", "Cidade Aurora — jogo fictício",
                     "--query", "bairros ruas", "--min-score", "0", "--allow-synthetic"]) == 0
    assert "cidade-aurora-teste" in capsys.readouterr().out
    assert cli.main(["build", "--input", str(FIXTURES), "--output", str(output), "--allow-synthetic"]) == 1
    output = tmp_path / "semantic.json"

    def forbidden_client():
        pytest.fail("A API nunca deve ser chamada sem --allow-paid")

    monkeypatch.setattr(cli, "_client", forbidden_client)
    assert cli.main(["build", "--input", str(FIXTURES), "--output", str(output), "--mode", "semantic",
                     "--embedding-model", "fake-model", "--allow-synthetic"]) == 1
    assert not output.exists()
