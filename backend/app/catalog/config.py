"""Credenciais Twitch lidas apenas quando uma consulta é solicitada."""

import os

from pydantic import BaseModel, Field, SecretStr, ValidationError, field_validator

from app.catalog.errors import CatalogConfigurationError


class IGDBSettings(BaseModel):
    client_id: SecretStr
    client_secret: SecretStr
    timeout_seconds: float = Field(default=5, ge=1, le=15)

    @field_validator("client_id", "client_secret", mode="before")
    @classmethod
    def require_nonblank(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Credencial obrigatória ausente.")
        return value.strip()


def get_igdb_settings() -> IGDBSettings:
    try:
        return IGDBSettings(
            client_id=os.getenv("IGDB_CLIENT_ID", ""),
            client_secret=os.getenv("IGDB_CLIENT_SECRET", ""),
            timeout_seconds=os.getenv("IGDB_TIMEOUT_SECONDS", "5"),
        )
    except ValidationError:
        raise CatalogConfigurationError() from None
