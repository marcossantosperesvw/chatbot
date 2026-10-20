"""Ingestão de dados sintéticos; sem serviços externos ou alterações na base real."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.rag.ingestion import (
    RagIngestionError, chunk_document, ingest_document, load_document,
)
from app.rag.schemas import DocumentMetadata, KnowledgeChunk, KnowledgeDocument


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "rag" / "cidade-aurora.md"


def metadata(**updates):
    return DocumentMetadata.model_validate({
        "document_id": "teste", "title": "Documento de teste", "game": "Jogo fictício",
        "source": "Exemplo sintético de teste", "reviewed_at": "2026-10-19",
        "synthetic": True,
    } | updates)


def document(text):
    return KnowledgeDocument(metadata=metadata(), text=text)


def assert_traceability(doc, chunks, limit):
    previous_end = 0
    assert chunks
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)
    for chunk in chunks:
        assert chunk.metadata == doc.metadata
        assert chunk.text.strip()
        assert len(chunk.text) <= limit
        assert chunk.text == doc.text[chunk.start_char:chunk.end_char]
        # Nenhum conteúdo não branco pode desaparecer entre os spans.
        assert not doc.text[previous_end:chunk.start_char].strip()
        previous_end = chunk.end_char
    assert not doc.text[previous_end:].strip()


def test_loads_utf8_metadata_and_explicitly_synthetic_fixture():
    doc = load_document(FIXTURE)
    assert doc.metadata.document_id == "cidade-aurora-teste"
    assert doc.metadata.synthetic is True
    assert doc.metadata.source_url is None
    assert "Construção" in doc.text
    assert doc.metadata.platforms == ("Plataforma fictícia",)
    assert doc.metadata.reviewed_at.isoformat() == "2026-10-19"


def test_chunks_preserve_hierarchy_and_deterministic_ids():
    doc = load_document(FIXTURE)
    chunks = chunk_document(doc, max_chars=1000)
    assert_traceability(doc, chunks, 1000)
    assert chunks == chunk_document(doc, max_chars=1000)
    assert chunks[0].chunk_id == "cidade-aurora-teste:1"
    assert chunks[2].section_path == (
        "Documento fictício: Cidade Aurora", "Construção livre", "Modo individual",
    )
    assert chunks[3].section_path == (
        "Documento fictício: Cidade Aurora", "Limitações do exemplo",
    )


def test_ingest_is_load_plus_chunk_without_writing_files(tmp_path):
    path = tmp_path / "document.md"
    path.write_text("# Teste\n\nTexto fictício.", encoding="utf-8")
    path.with_suffix(".json").write_text(metadata().model_dump_json(), encoding="utf-8")
    before = {file.name for file in tmp_path.iterdir()}
    assert ingest_document(path) == chunk_document(load_document(path))
    assert {file.name for file in tmp_path.iterdir()} == before


@pytest.mark.parametrize("text", [
    "Texto sem títulos.\n\nOutro parágrafo.",
    "Introdução sem título.\n# Primeiro\nTexto\n## Filho\nDetalhe\n# Segundo\nFim.",
    "# Título\n\n" + ("Parágrafo repetido com acentuação e emoji 🎮.\n\n" * 20),
    "# Título\n" + "Uma linha sem fim " * 60,
    "# Título\n" + "á🎮" * 100,
    "\n\nConteúdo\n" + " " * 200 + "\nOutro conteúdo.\n\n",
    "# Primeiro\n## Segundo\n### Terceiro\n",
    "   # Título com indentação ###\n\nTexto sem newline final",
])
@pytest.mark.parametrize("limit", [1, 20, 90])
def test_bounded_chunks_never_lose_nonblank_content(text, limit):
    doc = document(text)
    assert_traceability(doc, chunk_document(doc, max_chars=limit), limit)


def test_prefers_paragraph_boundaries():
    chunks = chunk_document(document("Primeiro parágrafo.\n\nSegundo parágrafo."), max_chars=30)
    assert [chunk.text for chunk in chunks] == ["Primeiro parágrafo.", "Segundo parágrafo."]


@pytest.mark.parametrize("fence", ["```", "~~~~"])
def test_hashes_inside_fenced_code_do_not_create_sections(fence):
    text = f"# Guia\n{fence}text\n# Isto é código\n{fence}\n## Seção real\nConteúdo."
    chunks = chunk_document(document(text))
    assert len(chunks) == 2
    assert chunks[0].section_path == ("Guia",)
    assert "# Isto é código" in chunks[0].text
    assert chunks[1].section_path == ("Guia", "Seção real")


def test_intro_and_heading_level_changes_have_correct_paths():
    chunks = chunk_document(document("Introdução.\n# A\nTexto\n### B\nTexto\n## C\nTexto\n# D\nFim"))
    assert [chunk.section_path for chunk in chunks] == [(), ("A",), ("A", "B"), ("A", "C"), ("D",)]


@pytest.mark.parametrize("value", [0, -1, True, 2.5, "100"])
def test_rejects_invalid_character_limit(value):
    with pytest.raises(ValueError, match="inteiro positivo"):
        chunk_document(document("Conteúdo"), max_chars=value)


def test_rejects_non_markdown_and_missing_document(tmp_path):
    with pytest.raises(RagIngestionError, match="extensão"):
        load_document(tmp_path / "document.txt")
    with pytest.raises(RagIngestionError, match="Markdown"):
        load_document(tmp_path / "missing.md")


@pytest.mark.parametrize("raw", [None, "{", "[]", "{}", '{"synthetic":true}'])
def test_rejects_missing_malformed_or_incomplete_metadata(tmp_path, raw):
    path = tmp_path / "document.md"
    path.write_text("Conteúdo", encoding="utf-8")
    if raw is not None:
        path.with_suffix(".json").write_text(raw, encoding="utf-8")
    with pytest.raises(RagIngestionError, match="Metadados"):
        load_document(path)


@pytest.mark.parametrize("field,value", [
    ("document_id", "../unsafe"), ("document_id", ""), ("title", "  "),
    ("game", ""), ("source", ""), ("reviewed_at", "invalid-date"),
    ("synthetic", "true"), ("synthetic", 1), ("platforms", [""]),
    ("game_version", ""), ("source_url", "not a URL"),
    ("source_url", "http://example.com"),
    ("source_url", "https://user:password@example.com"),
    ("unexpected", "extra"),
])
def test_rejects_invalid_metadata_fields(field, value):
    with pytest.raises(ValidationError):
        metadata(**{field: value})


def test_requires_explicit_synthetic_flag(tmp_path):
    path = tmp_path / "document.md"
    path.write_text("Conteúdo", encoding="utf-8")
    data = metadata().model_dump(mode="json")
    del data["synthetic"]
    path.with_suffix(".json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RagIngestionError, match="Metadados"):
        load_document(path)


@pytest.mark.parametrize("text", ["", "  \n\t"])
def test_rejects_empty_markdown(tmp_path, text):
    path = tmp_path / "document.md"
    path.write_text(text, encoding="utf-8")
    path.with_suffix(".json").write_text(metadata().model_dump_json(), encoding="utf-8")
    with pytest.raises(RagIngestionError, match="vazio"):
        load_document(path)


@pytest.mark.parametrize("suffix", [".md", ".json"])
def test_rejects_invalid_utf8(tmp_path, suffix):
    path = tmp_path / "document.md"
    path.write_text("Texto", encoding="utf-8")
    path.with_suffix(".json").write_text(metadata().model_dump_json(), encoding="utf-8")
    path.with_suffix(suffix).write_bytes(b"\xff\xfe")
    with pytest.raises(RagIngestionError):
        load_document(path)


def test_file_read_errors_are_classified_without_raw_details(monkeypatch):
    def fail(self, **kwargs):
        raise PermissionError("detalhe interno")

    monkeypatch.setattr(Path, "read_text", fail)
    with pytest.raises(RagIngestionError) as error:
        load_document("document.md")
    assert "detalhe interno" not in str(error.value)


def test_newlines_are_normalized_before_offsets_are_computed(tmp_path):
    path = tmp_path / "document.md"
    path.write_bytes("# Título\r\n\r\nTexto com acentuação.\r\n".encode("utf-8"))
    path.with_suffix(".json").write_text(metadata().model_dump_json(), encoding="utf-8")
    doc = load_document(path)
    assert "\r" not in doc.text
    assert_traceability(doc, chunk_document(doc, max_chars=20), 20)


def test_chunk_rejects_empty_text_and_incoherent_offsets():
    for text, end in ((" ", 1), ("abc", 2)):
        with pytest.raises(ValidationError):
            KnowledgeChunk(chunk_id="teste:1", metadata=metadata(), text=text,
                           start_char=0, end_char=end)
