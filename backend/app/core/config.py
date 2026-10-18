"""Configuração validada somente quando o chat precisa acessar a IA."""

import os

from pydantic import BaseModel, Field, SecretStr, ValidationError, field_validator

from app.core.errors import AIConfigurationError


class AISettings(BaseModel):
    api_key: SecretStr
    model: str = Field(min_length=1)
    timeout_seconds: float = Field(default=25, ge=1, le=25)
    max_output_tokens: int = Field(default=800, ge=16, le=2048)

    @field_validator("api_key", "model", mode="before")
    @classmethod
    def require_nonblank(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Configuração obrigatória ausente.")
        return value.strip()


def get_ai_settings() -> AISettings:
    try:
        return AISettings(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_MODEL", ""),
            timeout_seconds=os.getenv("OPENAI_TIMEOUT_SECONDS", "25"),
            max_output_tokens=os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "800"),
        )
    except ValidationError:
        # ValidationError pode conter o valor da credencial: não propagá-la.
        raise AIConfigurationError() from None
