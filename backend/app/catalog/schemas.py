"""Contrato pequeno do catálogo, independente do formato bruto da IGDB."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


SearchText = Annotated[str, StringConstraints(
    strip_whitespace=True, min_length=1, max_length=120,
    pattern=r"^[^\x00-\x1f\x7f]+$",
)]


class CatalogQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: SearchText
    limit: int = Field(default=5, ge=1, le=10)


class StoreLink(BaseModel):
    store: str
    url: str


class CatalogDiscoveryQuery(BaseModel):
    """Entrada interna da ferramenta; não altera o contrato GET /api/games."""

    model_config = ConfigDict(extra="forbid")
    query: SearchText | None = None
    platform: SearchText | None = None
    genre: SearchText | None = None
    game_mode: SearchText | None = None
    limit: int = Field(default=5, ge=1, le=5)

    @model_validator(mode="after")
    def require_criterion(self):
        if not any((self.query, self.platform, self.genre, self.game_mode)):
            raise ValueError("Informe um nome ou uma preferência.")
        return self


class CatalogGame(BaseModel):
    id: int = Field(strict=True, gt=0)
    name: Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]
    summary: str | None = None
    platforms: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    game_modes: list[str] = Field(default_factory=list)
    release_date: date | None = None
    source_url: str | None = None
    store_links: list[StoreLink] = Field(default_factory=list)


class CatalogSearchResult(BaseModel):
    source: Literal["IGDB"] = "IGDB"
    query: str
    games: list[CatalogGame]
    retrieved_at: datetime
    cached: bool = False
