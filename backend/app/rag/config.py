"""RAG desativado por padrão; caminhos relativos resolvidos a partir do backend."""

import os
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from app.rag.errors import RagError


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class RagSettings(BaseModel):
    enabled: bool = False
    index_path: Path = BACKEND_ROOT / ".data" / "rag-index.json"
    allow_synthetic: bool = False
    min_score: float = Field(default=0.35, ge=0, le=1)


def _boolean(name: str, default="false") -> bool:
    value = os.getenv(name, default).strip().casefold()
    if value not in {"true", "false"}:
        raise RagError("Configuração booleana de RAG inválida.")
    return value == "true"


def get_rag_settings() -> RagSettings:
    if not _boolean("RAG_ENABLED"):
        return RagSettings()
    try:
        path = Path(os.getenv("RAG_INDEX_PATH", ".data/rag-index.json"))
        if not path.is_absolute():
            path = BACKEND_ROOT / path
        return RagSettings(enabled=True, index_path=path,
                           allow_synthetic=_boolean("RAG_ALLOW_SYNTHETIC"),
                           min_score=os.getenv("RAG_MIN_SCORE", "0.35"))
    except (ValidationError, ValueError, OSError):
        raise RagError("Configuração de RAG inválida.") from None
