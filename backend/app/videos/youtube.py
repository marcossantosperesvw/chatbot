"""Cliente opcional, limitado e compartilhado por processo, usando HTTPX existente."""

import asyncio
import html
import os
import re
import time
from collections import OrderedDict
from datetime import UTC, datetime

import httpx
from pydantic import BaseModel, Field, SecretStr, ValidationError

from app.videos.schemas import TutorialVideo


class VideoUnavailable(Exception):
    """Falha sem detalhes do provedor ou credenciais."""


class VideoSettings(BaseModel):
    api_key: SecretStr
    timeout_seconds: float = Field(default=5, ge=1, le=5)
    max_searches_per_day: int = Field(default=30, ge=1, le=1000)
    preferred_channel_ids: tuple[str, ...] = ()


def get_video_settings() -> VideoSettings | None:
    key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not key:
        return None
    try:
        return VideoSettings(api_key=key,
            timeout_seconds=os.getenv("YOUTUBE_TIMEOUT_SECONDS", "5"),
            max_searches_per_day=os.getenv("YOUTUBE_MAX_SEARCHES_PER_DAY", "30"),
            preferred_channel_ids=tuple(x.strip() for x in os.getenv("YOUTUBE_PREFERRED_CHANNEL_IDS", "").split(",") if x.strip()))
    except ValidationError:
        raise VideoUnavailable() from None


class YouTubeClient:
    def __init__(self, http: httpx.AsyncClient, settings: VideoSettings):
        self.http, self.settings = http, settings
        self._lock = asyncio.Lock()
        self._cache: OrderedDict[str, tuple[float, tuple[TutorialVideo, ...]]] = OrderedDict()
        self._day = datetime.now(UTC).date()
        self._searches = 0
        self._blocked_until = 0.0

    def purge_cache(self) -> None:
        now = time.monotonic()
        for key, (expires, _) in list(self._cache.items()):
            if expires <= now:
                del self._cache[key]

    async def maintain_cache(self) -> None:
        while True:
            await asyncio.sleep(60)
            self.purge_cache()

    async def _get(self, resource: str, **params) -> dict:
        response = await self.http.get(f"https://www.googleapis.com/youtube/v3/{resource}",
            params=params, headers={"X-Goog-Api-Key": self.settings.api_key.get_secret_value()},
            timeout=self.settings.timeout_seconds, follow_redirects=False)
        if response.status_code in {403, 429}:
            self._blocked_until = time.monotonic() + 60
        if response.status_code != 200 or len(response.content) > 1_000_000:
            raise VideoUnavailable()
        data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise VideoUnavailable()
        return data

    async def search(self, query: str) -> tuple[TutorialVideo, ...]:
        query = " ".join(query.split())
        if not 3 <= len(query) <= 250:
            raise VideoUnavailable()
        try:
            async with asyncio.timeout(self.settings.timeout_seconds):
                async with self._lock:
                    return await self._search(query)
        except (TimeoutError, httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
            raise VideoUnavailable() from None

    async def _search(self, query: str) -> tuple[TutorialVideo, ...]:
        now = time.monotonic()
        self.purge_cache()
        cached = self._cache.get(query.casefold())
        if cached and cached[0] > now:
            self._cache.move_to_end(query.casefold())
            return cached[1]
        today = datetime.now(UTC).date()
        if today != self._day:
            self._day, self._searches = today, 0
        if now < self._blocked_until or self._searches >= self.settings.max_searches_per_day:
            raise VideoUnavailable()
        self._searches += 1  # Tentativas falhas também consomem orçamento local.
        found = await self._get("search", part="snippet", q=query, type="video", maxResults=5,
            videoEmbeddable="true", videoSyndicated="true", relevanceLanguage="pt",
            regionCode="BR", safeSearch="strict", order="relevance")
        ids = []
        for item in found["items"]:
            identifier = item.get("id", {}).get("videoId", "")
            if isinstance(identifier, str) and re.fullmatch(r"[A-Za-z0-9_-]{11}", identifier) and identifier not in ids:
                ids.append(identifier)
        videos = []
        if ids:
            details = await self._get("videos", part="snippet,status,contentDetails", id=",".join(ids))
            # Preservar a ordem de relevância da pesquisa, não a ordem do lote de detalhes.
            by_id = {item.get("id"): item for item in details["items"] if isinstance(item, dict)}
            preferred = set(self.settings.preferred_channel_ids)
            ids.sort(key=lambda identifier: by_id.get(identifier, {}).get("snippet", {}).get("channelId") not in preferred)
            for identifier in ids:
                item = by_id.get(identifier, {})
                status, snippet = item.get("status", {}), item.get("snippet", {})
                content = item.get("contentDetails", {})
                regions = content.get("regionRestriction", {})
                if (status.get("embeddable") is not True or status.get("privacyStatus") != "public"
                        or status.get("uploadStatus") != "processed"
                        or snippet.get("liveBroadcastContent") not in {None, "none"}
                        or content.get("contentRating", {}).get("ytRating") == "ytAgeRestricted"
                        or "BR" in regions.get("blocked", [])
                        or ("allowed" in regions and "BR" not in regions["allowed"])):
                    continue
                title, channel = snippet.get("title"), snippet.get("channelTitle")
                if not isinstance(title, str) or not isinstance(channel, str) or not title.strip() or not channel.strip():
                    continue
                videos.append(TutorialVideo(video_id=identifier, title=html.unescape(title)[:200],
                    channel=html.unescape(channel)[:200], retrieved_at=datetime.now(UTC)))
                if len(videos) == 3:
                    break
        result = tuple(videos)
        self._cache[query.casefold()] = (now + 3600, result)
        self._cache.move_to_end(query.casefold())
        while len(self._cache) > 128:
            self._cache.popitem(last=False)
        return result
