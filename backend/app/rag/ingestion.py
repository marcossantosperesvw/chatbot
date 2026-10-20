"""Ingestão de um par Markdown/JSON. Sem rede, persistência de índice ou IA."""

import re
from pathlib import Path

from pydantic import ValidationError

from app.rag.schemas import DocumentMetadata, KnowledgeChunk, KnowledgeDocument


DEFAULT_MAX_CHARS = 1200
HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+[ \t]*)?$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")


class RagIngestionError(ValueError):
    """Falha local com mensagem legível, sem reproduzir o conteúdo do documento."""


def load_document(markdown_path: str | Path) -> KnowledgeDocument:
    """Ler UTF-8; guia.md exige guia.json no mesmo diretório."""
    path = Path(markdown_path)
    if path.suffix != ".md":
        raise RagIngestionError("O documento deve ter extensão .md.")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise RagIngestionError("Não foi possível ler o Markdown em UTF-8.") from None
    try:
        raw_metadata = path.with_suffix(".json").read_text(encoding="utf-8")
        metadata = DocumentMetadata.model_validate_json(raw_metadata)
    except (OSError, UnicodeError, ValidationError):
        raise RagIngestionError("Metadados JSON ausentes, ilegíveis ou inválidos.") from None
    try:
        return KnowledgeDocument(metadata=metadata, text=text)
    except ValidationError:
        raise RagIngestionError("O Markdown não pode estar vazio.") from None


def _sections(text: str):
    """Produzir spans com hierarquia ATX; cercas de código não criam seções."""
    headings: list[tuple[int, str]] = []
    fence: str | None = None
    start = offset = 0
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        marker = FENCE.match(content)
        if marker:
            if fence is None:
                fence = marker[1]
            elif (marker[1][0] == fence[0] and len(marker[1]) >= len(fence)
                  and not marker[2].strip()):
                fence = None
        elif fence is None and (heading := HEADING.match(content)):
            if offset > start:
                yield tuple(title for _, title in headings), start, offset
            level, title = len(heading[1]), heading[2].strip()
            while headings and headings[-1][0] >= level:
                headings.pop()
            headings.append((level, title))
            start = offset
        offset += len(line)
    if offset > start:
        yield tuple(title for _, title in headings), start, offset


def _choose_cut(text: str, start: int, end: int, max_chars: int) -> int:
    if end - start <= max_chars:
        return end
    limit = start + max_chars
    # Priorizar parágrafos, depois linhas/palavras; palavra maior que o limite
    # precisa ser dividida. Não descartar seu restante nem truncar o documento.
    breaks = list(PARAGRAPH_BREAK.finditer(text, start, limit))
    if breaks:
        return breaks[-1].end()
    for separator in ("\n", " "):
        boundary = text.rfind(separator, start, limit)
        if boundary > start:
            return boundary + 1
    return limit


def chunk_document(
    document: KnowledgeDocument, *, max_chars: int = DEFAULT_MAX_CHARS,
) -> list[KnowledgeChunk]:
    """Dividir sem misturar seções; offsets referem-se a document.text, não a bytes."""
    if type(max_chars) is not int or max_chars <= 0:
        raise ValueError("max_chars deve ser um inteiro positivo.")
    chunks = []
    for section_path, start, end in _sections(document.text):
        while start < end:
            cut = _choose_cut(document.text, start, end, max_chars)
            raw = document.text[start:cut]
            trimmed = raw.strip()
            if trimmed:
                left = start + len(raw) - len(raw.lstrip())
                chunks.append(KnowledgeChunk(
                    chunk_id=f"{document.metadata.document_id}:{len(chunks) + 1}",
                    metadata=document.metadata, section_path=section_path,
                    text=trimmed, start_char=left, end_char=left + len(trimmed),
                ))
            start = cut
    return chunks


def ingest_document(
    markdown_path: str | Path, *, max_chars: int = DEFAULT_MAX_CHARS,
) -> list[KnowledgeChunk]:
    """Atalho para carregar e dividir um documento; não escreve ou envia dados."""
    return chunk_document(load_document(markdown_path), max_chars=max_chars)
