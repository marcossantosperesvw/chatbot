"""Contratos da ingestão local, independentes de embeddings e do agente."""

from datetime import date
from typing import Annotated, Literal

from pydantic import (
    BaseModel, ConfigDict, Field, HttpUrl, StrictBool, StringConstraints,
    field_validator, model_validator,
)


Text = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]
DocumentId = Annotated[str, StringConstraints(
    strict=True, pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$",
)]


class DocumentMetadata(BaseModel):
    """Metadados do JSON de mesmo nome do Markdown; campos extras são rejeitados."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: DocumentId
    title: Text
    scope: Literal["game", "general"] = "game"
    game: Text | None = None
    products: tuple[Text, ...] = ()
    platforms: tuple[Text, ...] = ()
    game_version: Text | None = None
    source: Text
    source_url: HttpUrl | None = None
    reviewed_at: date
    synthetic: StrictBool  # Obrigatório: exemplos fictícios precisam ser explícitos.

    @model_validator(mode="after")
    def validate_scope(self):
        if self.scope == "game" and self.game is None:
            raise ValueError("Documento de jogo exige game.")
        if self.scope == "general" and (self.game is not None or self.game_version is not None):
            raise ValueError("Documento geral não pode definir jogo ou versão de jogo.")
        return self

    @field_validator("source_url")
    @classmethod
    def require_safe_source_url(cls, value):
        if value and (value.scheme != "https" or value.username or value.password):
            raise ValueError("A fonte deve usar HTTPS sem credenciais.")
        return value


class KnowledgeDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metadata: DocumentMetadata
    # Preservar espaços e posições; a validação não altera o texto original.
    text: str = Field(strict=True, min_length=1)

    @field_validator("text")
    @classmethod
    def require_content(cls, value):
        if not value.strip():
            raise ValueError("O documento precisa ter conteúdo.")
        return value


class KnowledgeChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: Text
    metadata: DocumentMetadata
    section_path: tuple[Text, ...] = ()
    text: str = Field(strict=True, min_length=1)
    start_char: int = Field(strict=True, ge=0)
    end_char: int = Field(strict=True, gt=0)

    @model_validator(mode="after")
    def validate_span(self):
        if not self.text.strip() or self.end_char - self.start_char != len(self.text):
            raise ValueError("O trecho precisa ter conteúdo e posições coerentes.")
        return self
