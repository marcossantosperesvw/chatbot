"""Contrato HTTP do chat, independente do provedor de inteligência artificial."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


MessageContent = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=4000,
    ),
]


class HistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: MessageContent


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: UUID
    message: MessageContent
    history: list[HistoryMessage] = Field(default_factory=list, max_length=50)


class AssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: MessageContent


class ChatResponse(BaseModel):
    conversation_id: UUID
    message: AssistantMessage


class ErrorResponse(BaseModel):
    detail: str
