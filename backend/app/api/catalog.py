"""Pesquisa independente de IA para validar a integração com o catálogo."""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.schemas import ErrorResponse
from app.catalog.errors import (
    CatalogConfigurationError, CatalogProviderError,
    CatalogRateLimitError, CatalogTimeoutError,
)
from app.catalog.schemas import CatalogQuery, CatalogSearchResult


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["catalog"])


@router.get(
    "/games", response_model=CatalogSearchResult,
    summary="Pesquisar jogos por nome na IGDB",
    responses={
        code: {"model": ErrorResponse, "description": description}
        for code, description in {
            429: "Limite de consultas excedido.",
            502: "Falha de comunicação ou resposta inválida do catálogo.",
            503: "Catálogo não configurado.",
            504: "Tempo limite da consulta excedido.",
        }.items()
    },
)
async def search_games(request: Request, params: Annotated[CatalogQuery, Query()]):
    try:
        return await request.app.state.catalog.search(params)
    except CatalogRateLimitError as error:
        raise HTTPException(
            status_code=429, detail="Limite de consultas ao catálogo excedido. Aguarde e tente novamente.",
            headers={"Retry-After": str(error.retry_after)},
        ) from None
    except (CatalogConfigurationError, CatalogProviderError, CatalogTimeoutError) as error:
        code, detail = {
            CatalogConfigurationError: (503, "Configure as credenciais da IGDB no backend."),
            CatalogProviderError: (502, "Não foi possível consultar o catálogo de jogos."),
            CatalogTimeoutError: (504, "O catálogo demorou para responder. Tente novamente."),
        }[type(error)]
        logger.warning("Falha do catálogo: %s", type(error).__name__)
        raise HTTPException(status_code=code, detail=detail) from None
