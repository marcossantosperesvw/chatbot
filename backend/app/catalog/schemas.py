"""Contrato pequeno do catálogo, independente do formato bruto da IGDB."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class CatalogQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Annotated[str, StringConstraints(
        strip_whitespace=True, min_length=1, max_length=120,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    )]
    limit: int = Field(default=5, ge=1, le=10)


class StoreLink(BaseModel):
    store: str
    url: str


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
