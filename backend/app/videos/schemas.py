"""Anexo de vídeo: somente metadados e ID, nunca HTML fornecido pelo modelo."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


VideoId = Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9_-]{11}$")]
VideoText = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=200)]


class TutorialVideo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    video_id: VideoId
    title: VideoText
    channel: VideoText
    retrieved_at: datetime

    @property
    def watch_url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"
