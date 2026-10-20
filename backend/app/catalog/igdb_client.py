"""Cliente assíncrono com token, cache limitado e controle local de consultas."""

import asyncio
import json
import math
import time
from collections import OrderedDict
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx

from app.catalog.config import IGDBSettings, get_igdb_settings
from app.catalog.errors import (
    CatalogFilterError, CatalogProviderError, CatalogRateLimitError, CatalogTimeoutError,
)
from app.catalog.schemas import (
    CatalogDiscoveryQuery, CatalogGame, CatalogQuery, CatalogSearchResult, StoreLink,
)


TOKEN_URL = "https://id.twitch.tv/oauth2/token"
VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"
GAMES_URL = "https://api.igdb.com/v4/games"
FIELDS = (
    "id,name,summary,platforms.name,genres.name,game_modes.name,"
    "first_release_date,url,websites.url"
)
CACHE_TTL_SECONDS = 300
CACHE_MAX_ENTRIES = 128
REQUEST_INTERVAL_SECONDS = 0.26  # Abaixo de 4 requisições/s, por processo.
FILTER_FIELDS = {"platform": "platforms", "genre": "genres", "game_mode": "game_modes"}
# Conveniências de linguagem, não uma lista fechada de jogos ou IDs de terceiros.
FILTER_ALIASES = {
    "platform": {"pc": "PC (Microsoft Windows)", "ps5": "PlayStation 5", "ps4": "PlayStation 4"},
    "genre": {"rpg": "Role-playing (RPG)"},
    "game_mode": {"solo": "Single player", "cooperativo": "Co-operative"},
}
STORE_HOSTS = {
    "store.steampowered.com": "Steam",
    "gog.com": "GOG", "www.gog.com": "GOG",
    "store.epicgames.com": "Epic Games", "www.epicgames.com": "Epic Games",
    "itch.io": "itch.io", "apps.apple.com": "App Store",
    "play.google.com": "Google Play", "www.xbox.com": "Xbox",
    "store.playstation.com": "PlayStation", "www.nintendo.com": "Nintendo",
}


def safe_url(value: object) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 2000:
        return None
    if any(character.isspace() or ord(character) < 32 for character in value):
        return None
    try:
        parts = urlsplit(value)
        if (parts.scheme != "https" or not parts.hostname or parts.username
                or parts.password or parts.port not in (None, 443)):
            return None
        return value
    except ValueError:
        return None


def store_links(websites: list[dict] | None) -> list[StoreLink]:
    links = []
    seen = set()
    for website in websites or []:
        url = safe_url(website.get("url"))
        if url is None or url in seen:
            continue
        host = urlsplit(url).hostname
        store = STORE_HOSTS.get(host)
        if host.endswith(".itch.io"):
            store = "itch.io"
        if store:
            links.append(StoreLink(store=store, url=url))
            seen.add(url)
    return links


def names(items: list[dict] | None) -> list[str]:
    return list(dict.fromkeys(item["name"].strip() for item in items or []))


def normalize_game(item: dict) -> CatalogGame:
    release_date = None
    timestamp = item.get("first_release_date")
    if isinstance(timestamp, int) and not isinstance(timestamp, bool):
        try:
            release_date = datetime.fromtimestamp(timestamp, UTC).date()
        except (ValueError, OverflowError, OSError):
            pass
    source_url = safe_url(item.get("url"))
    if source_url and urlsplit(source_url).hostname not in ("igdb.com", "www.igdb.com"):
        source_url = None
    return CatalogGame(
        id=item["id"], name=item["name"], summary=item.get("summary"),
        platforms=names(item.get("platforms")), genres=names(item.get("genres")),
        game_modes=names(item.get("game_modes")), release_date=release_date,
        source_url=source_url, store_links=store_links(item.get("websites")),
    )


class IGDBClient:
    """Uma instância por processo, encerrada junto com o cliente HTTP da aplicação."""

    def __init__(self, http: httpx.AsyncClient, settings: IGDBSettings | None = None):
        self._http = http
        self._settings = settings
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._next_request_at = 0.0
        self._cooldown_until = 0.0
        self._lock = asyncio.Lock()
        self._cache: OrderedDict[tuple, tuple[float, CatalogSearchResult]] = OrderedDict()
        self._filter_cache: OrderedDict[tuple[str, str], tuple[float, int]] = OrderedDict()

    def _check_response(self, response: httpx.Response) -> None:
        if response.status_code == 429:
            try:
                delay = float(response.headers.get("Retry-After", "1"))
                if not math.isfinite(delay):
                    raise ValueError()
                retry_after = max(1, math.ceil(delay))
            except ValueError:
                retry_after = 1
            self._cooldown_until = time.monotonic() + retry_after
            raise CatalogRateLimitError(retry_after)
        if not response.is_success:
            raise CatalogProviderError()

    async def _get_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        response = await self._http.post(TOKEN_URL, data={
            "client_id": self._settings.client_id.get_secret_value(),
            "client_secret": self._settings.client_secret.get_secret_value(),
            "grant_type": "client_credentials",
        }, timeout=self._settings.timeout_seconds)
        self._check_response(response)
        payload = response.json()
        token = payload["access_token"]
        expires_in = payload["expires_in"]
        if (not isinstance(token, str) or not token.strip()
                or isinstance(expires_in, bool) or not isinstance(expires_in, int)
                or expires_in <= 0 or payload.get("token_type") != "bearer"):
            raise CatalogProviderError()
        self._token = token
        # Antecipar renovação sem invalidar tokens de duração curta imediatamente.
        self._token_expires_at = time.monotonic() + expires_in - min(60, expires_in / 10)
        await self._validate_token()
        return token

    async def _validate_token(self) -> None:
        token = self._token
        self._token = None  # Falhas de validação invalidam o token em memória.
        response = await self._http.get(
            VALIDATE_URL, headers={"Authorization": f"OAuth {token}"},
            timeout=self._settings.timeout_seconds,
        )
        self._check_response(response)
        payload = response.json()
        expires_in = payload["expires_in"]
        if (payload["client_id"] != self._settings.client_id.get_secret_value()
                or isinstance(expires_in, bool) or not isinstance(expires_in, int)
                or expires_in <= 0):
            raise CatalogProviderError()
        self._token_expires_at = time.monotonic() + expires_in - min(60, expires_in / 10)
        self._token = token

    async def maintain_token(self) -> None:
        """A Twitch exige validação periódica enquanto mantemos um token OAuth."""
        while True:
            await asyncio.sleep(3600)
            async with self._lock:
                if self._token is not None:
                    try:
                        async with asyncio.timeout(self._settings.timeout_seconds):
                            await self._validate_token()
                    except (TimeoutError, httpx.HTTPError, ValueError, KeyError,
                            TypeError, CatalogProviderError, CatalogRateLimitError):
                        self._token = None

    async def _post(self, url: str, query: str, token: str) -> httpx.Response:
        await asyncio.sleep(max(0, self._next_request_at - time.monotonic()))
        self._next_request_at = time.monotonic() + REQUEST_INTERVAL_SECONDS
        return await self._http.post(
            url, content=query.encode("utf-8"), timeout=self._settings.timeout_seconds,
            headers={
                "Client-ID": self._settings.client_id.get_secret_value(),
                "Authorization": f"Bearer {token}",
                "Accept": "application/json", "Content-Type": "text/plain",
            },
        )

    async def _fetch(self, url: str, query: str) -> list:
        token = await self._get_token()
        response = await self._post(url, query, token)
        if response.status_code == 401:
            self._token = None
            token = await self._get_token()
            response = await self._post(url, query, token)
            if response.status_code == 401:
                self._token = None
        self._check_response(response)
        payload = response.json()
        if not isinstance(payload, list):
            raise CatalogProviderError()
        return payload

    async def _resolve_filter(self, field: str, value: str) -> int:
        value = FILTER_ALIASES.get(field, {}).get(value.casefold(), value)
        key = (field, value.casefold())
        cached = self._filter_cache.get(key)
        if cached and time.monotonic() < cached[0]:
            self._filter_cache.move_to_end(key)
            return cached[1]
        endpoint = FILTER_FIELDS[field]
        literal = json.dumps(value, ensure_ascii=False)
        payload = await self._fetch(
            f"https://api.igdb.com/v4/{endpoint}",
            f"fields id,name; where name ~ {literal}; limit 2;",
        )
        # Checar também localmente: não aceitar correspondências aproximadas.
        if (len(payload) != 1 or payload[0]["name"].casefold() != value.casefold()):
            raise CatalogFilterError(field)
        identifier = payload[0]["id"]
        if type(identifier) is not int or identifier <= 0:
            raise CatalogProviderError()
        self._filter_cache[key] = (time.monotonic() + CACHE_TTL_SECONDS, identifier)
        self._filter_cache.move_to_end(key)
        while len(self._filter_cache) > CACHE_MAX_ENTRIES:
            self._filter_cache.popitem(last=False)
        return identifier

    async def search(self, params: CatalogQuery | CatalogDiscoveryQuery) -> CatalogSearchResult:
        if self._settings is None:
            self._settings = get_igdb_settings()
        key = tuple((name, value.casefold() if isinstance(value, str) else value)
                    for name, value in params.model_dump().items())
        try:
            async with asyncio.timeout(self._settings.timeout_seconds):
                # Serialização simples evita renovar o token várias vezes e limita
                # as consultas no MVP de um processo. O timeout inclui essa espera.
                async with self._lock:
                    cached = self._cache.get(key)
                    if cached and time.monotonic() < cached[0]:
                        self._cache.move_to_end(key)
                        return cached[1].model_copy(deep=True, update={
                            "cached": True, "query": params.query or "",
                        })
                    if time.monotonic() < self._cooldown_until:
                        raise CatalogRateLimitError(max(1, math.ceil(self._cooldown_until - time.monotonic())))
                    # O nome é um literal entre aspas, nunca uma consulta livre.
                    query = (f"search {json.dumps(params.query, ensure_ascii=False)}; "
                             if params.query else "")
                    query += f"fields {FIELDS}; limit {params.limit};"
                    filters = []
                    if isinstance(params, CatalogDiscoveryQuery):
                        for field, endpoint in FILTER_FIELDS.items():
                            value = getattr(params, field)
                            if value:
                                identifier = await self._resolve_filter(field, value)
                                filters.append(f"{endpoint} = ({identifier})")
                    if filters:
                        query += " where " + " & ".join(filters) + ";"
                    if not params.query:
                        # Volume de avaliações prioriza candidatos conhecidos;
                        # não equivale a relevância pessoal nem a uma nota de qualidade.
                        query += " sort total_rating_count desc;"
                    payload = await self._fetch(GAMES_URL, query)
                    result = CatalogSearchResult(
                        query=params.query or "",
                        games=[normalize_game(item) for item in payload[:params.limit]],
                        retrieved_at=datetime.now(UTC),
                    )
                    self._cache[key] = (time.monotonic() + CACHE_TTL_SECONDS, result.model_copy(deep=True))
                    self._cache.move_to_end(key)
                    while len(self._cache) > CACHE_MAX_ENTRIES:
                        self._cache.popitem(last=False)
                    return result
        except (TimeoutError, httpx.TimeoutException):
            raise CatalogTimeoutError() from None
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
            raise CatalogProviderError() from None
