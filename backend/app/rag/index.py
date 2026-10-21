"""Índice JSON versionado; construção explícita e gravação atômica local."""

import hashlib
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.rag.embeddings import validate_vector
from app.rag.errors import RagError
from app.rag.ingestion import RagIngestionError, chunk_document, load_document
from app.rag.schemas import KnowledgeChunk


MAX_CHUNKS = 5000
MAX_INDEX_BYTES = 50_000_000


class IndexedPassage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    chunk: KnowledgeChunk
    vector: tuple[float, ...] | None = None

    @field_validator("vector", mode="before")
    @classmethod
    def check_vector(cls, value):
        return None if value is None else validate_vector(value)


class KnowledgeIndex(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    mode: Literal["lexical", "semantic"] = "lexical"
    embedding_model: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    max_chars: int = Field(default=1200, strict=True, ge=1, le=2000)
    revisions: dict[str, str]
    passages: tuple[IndexedPassage, ...] = Field(max_length=MAX_CHUNKS)

    @model_validator(mode="after")
    def check_consistency(self):
        ids = [passage.chunk.chunk_id for passage in self.passages]
        if len(set(ids)) != len(ids):
            raise ValueError("IDs de trechos duplicados.")
        metadata_by_document = {}
        if any(not re.fullmatch(r"[0-9a-f]{64}", revision) for revision in self.revisions.values()):
            raise ValueError("Revisão documental inválida.")
        for passage in self.passages:
            chunk = passage.chunk
            if chunk.metadata.document_id not in self.revisions or len(chunk.text) > self.max_chars:
                raise ValueError("Trecho incompatível com o manifesto.")
            identifier = chunk.metadata.document_id
            if not re.fullmatch(re.escape(identifier) + r":[1-9][0-9]*", chunk.chunk_id):
                raise ValueError("ID do trecho incompatível com o documento.")
            previous = metadata_by_document.setdefault(identifier, chunk.metadata)
            if previous != chunk.metadata:
                raise ValueError("Metadados divergentes no mesmo documento.")
        if self.mode == "semantic":
            if not self.embedding_model or not self.embedding_model.strip():
                raise ValueError("Índice sem modelo de embedding.")
            if any(passage.vector is None for passage in self.passages):
                raise ValueError("Índice sem vetores completos.")
            if len({len(passage.vector) for passage in self.passages}) > 1:
                raise ValueError("Dimensões inconsistentes.")
        elif self.embedding_model is not None or any(p.vector is not None for p in self.passages):
            raise ValueError("Índice lexical não deve conter embeddings.")
        return self


def build_index(directory: Path, *, max_chars=1200, allow_synthetic=False) -> KnowledgeIndex:
    if type(max_chars) is not int or not 1 <= max_chars <= 2000:
        raise RagError("max_chars deve estar entre 1 e 2000.")
    try:
        directory = directory.resolve(strict=True)
        if not directory.is_dir():
            raise RagError("A base deve ser um diretório.")
        files = sorted(directory.rglob("*.md"))
        passages, revisions = [], {}
        for path in files:
            if path.name == "README.md":
                continue  # Documentação operacional não faz parte do corpus.
            sidecar = path.with_suffix(".json")
            if (path.is_symlink() or sidecar.is_symlink()
                    or not path.resolve().is_relative_to(directory)
                    or not sidecar.resolve().is_relative_to(directory)):
                raise RagError("A base não aceita documentos fora do diretório ou links simbólicos.")
            if path.stat().st_size > 1_000_000 or sidecar.stat().st_size > 100_000:
                raise RagError("Documento ou metadados excedem o limite local.")
            document = load_document(path)
            if document.metadata.synthetic and not allow_synthetic:
                raise RagError("Documento sintético bloqueado; use somente em demonstração explícita.")
            identifier = document.metadata.document_id
            if identifier in revisions:
                raise RagError("document_id duplicado na base.")
            revisions[identifier] = hashlib.sha256(
                (document.metadata.model_dump_json() + "\n" + document.text).encode("utf-8")
            ).hexdigest()
            passages.extend(IndexedPassage(chunk=chunk) for chunk in chunk_document(document, max_chars=max_chars))
            if len(passages) > MAX_CHUNKS:
                raise RagError("Base excede o limite de trechos do MVP.")
        if not passages:
            raise RagError("Nenhum documento encontrado; adicione pares Markdown/JSON à base.")
        return KnowledgeIndex(max_chars=max_chars, revisions=revisions, passages=tuple(passages))
    except (OSError, RagIngestionError, ValidationError):
        raise RagError("Não foi possível construir o índice; confira os documentos e metadados.") from None


def save_index(index: KnowledgeIndex, path: Path, *, force=False) -> None:
    # Reconferir antes de persistir: model_copy do Pydantic não revalida alterações.
    try:
        payload = KnowledgeIndex.model_validate_json(index.model_dump_json()).model_dump_json()
    except ValidationError:
        raise RagError("Índice inválido; não foi salvo.") from None
    if len(payload.encode("utf-8")) > MAX_INDEX_BYTES:
        raise RagError("Índice excede o limite de armazenamento do MVP.")
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        if force:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)  # Não sobrescrever um índice existente, nem em corrida.
    except FileExistsError:
        raise RagError("Índice já existe; use --force para substituir explicitamente.") from None
    except OSError:
        raise RagError("Não foi possível salvar o índice.") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_index(path: Path, *, allow_synthetic=False) -> KnowledgeIndex:
    try:
        if path.stat().st_size > MAX_INDEX_BYTES:
            raise RagError("Índice excede o limite local.")
        index = KnowledgeIndex.model_validate_json(path.read_text(encoding="utf-8"))
        if any(p.chunk.metadata.synthetic for p in index.passages) and not allow_synthetic:
            raise RagError("Índice sintético bloqueado fora da demonstração.")
        if not index.passages:
            raise RagError("Índice vazio.")
        return index
    except (OSError, UnicodeError, ValidationError):
        raise RagError("Índice ausente ou inválido; execute a indexação local.") from None
