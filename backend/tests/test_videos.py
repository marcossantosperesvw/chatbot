"""YouTube e fluxo do agente com HTTP simulado; sem consumir cotas reais."""

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from agents.tool_context import ToolContext
from fastapi.testclient import TestClient
from openai import AsyncOpenAI

from app.core.errors import AIProviderError
from app.main import app
from app.services import chat_service
from app.tools.catalog import CatalogContext
from app.tools.videos import extract_video, search_videos
from app.videos.schemas import TutorialVideo
from app.videos.youtube import VideoSettings, VideoUnavailable, YouTubeClient, get_video_settings


ID = "abcdefghijk"
OTHER = "lmnopqrstuv"


def video():
    return TutorialVideo(video_id=ID, title="Instalar Epic Games no Windows", channel="Canal teste",
                         retrieved_at=datetime.now(UTC))


def item(identifier=ID, **overrides):
    return {"id": identifier, "snippet": {"title":"Instalar &amp; configurar", "channelTitle":"Canal teste",
            "channelId":"canal-1", "liveBroadcastContent":"none"},
            "status":{"privacyStatus":"public", "embeddable":True, "uploadStatus":"processed"},
            "contentDetails":{}, **overrides}


def youtube(handler, **settings):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return YouTubeClient(http, VideoSettings(api_key="test-youtube-secret", **settings))


def handler_for(calls, items=None):
    def handle(request):
        calls.append(request)
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"items":[{"id":{"videoId":ID}}, {"id":{"videoId":OTHER}},
                                                    {"id":{"videoId":"../unsafe"}}]})
        return httpx.Response(200, json={"items":items if items is not None else [item()]})
    return handle


def test_search_filters_confirms_metadata_and_coalesces_cache():
    calls = []

    async def run():
        client = youtube(handler_for(calls))
        async with client.http:
            first, second = await asyncio.gather(client.search("  instalar   Epic Windows "), client.search("instalar Epic Windows"))
            assert first == second and len(first) == 1
            assert first[0].title == "Instalar & configurar"
            assert await client.search("INSTALAR EPIC WINDOWS") == first
    asyncio.run(run())
    assert len(calls) == 2
    query = calls[0].url.params
    for key in ("videoEmbeddable", "videoSyndicated"):
        assert query[key] == "true"
    assert query["safeSearch"] == "strict" and query["relevanceLanguage"] == "pt"
    assert calls[0].headers["x-goog-api-key"] == "test-youtube-secret"
    assert "test-youtube-secret" not in str(calls[0].url)
    assert calls[1].url.params["id"] == f"{ID},{OTHER}"


@pytest.mark.parametrize("change", [
    {"status":{"privacyStatus":"private", "embeddable":True, "uploadStatus":"processed"}},
    {"status":{"privacyStatus":"public", "embeddable":False, "uploadStatus":"processed"}},
    {"contentDetails":{"contentRating":{"ytRating":"ytAgeRestricted"}}},
    {"contentDetails":{"regionRestriction":{"blocked":["BR"]}}},
    {"contentDetails":{"regionRestriction":{"allowed":["US"]}}},
    {"snippet":{"title":"Live", "channelTitle":"Canal", "liveBroadcastContent":"live"}},
    {"snippet":{"title":"", "channelTitle":"Canal"}},
])
def test_unplayable_or_invalid_candidates_are_not_returned(change):
    async def run():
        client = youtube(handler_for([], [item(**change)]))
        async with client.http:
            assert await client.search("instalar Epic Games") == ()
    asyncio.run(run())


@pytest.mark.parametrize("status", [400, 403, 429, 500])
def test_provider_failure_is_safe_without_retry(status):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(status, json={"error":{"message":"secret-provider-data"}})

    async def run():
        client = youtube(handle)
        async with client.http:
            with pytest.raises(VideoUnavailable) as error:
                await client.search("instalar Epic Games")
            assert "secret" not in str(error.value)
    asyncio.run(run())
    assert len(calls) == 1


def test_timeout_and_malformed_response_are_safe():
    for response in ("timeout", [], {"items":None}):
        def handle(request):
            if response == "timeout":
                raise httpx.ReadTimeout("secret", request=request)
            return httpx.Response(200, json=response)

        async def run():
            client = youtube(handle)
            async with client.http:
                with pytest.raises(VideoUnavailable):
                    await client.search("instalar Epic Games")
        asyncio.run(run())


def test_budget_blocks_new_queries_but_allows_cache_and_expiration_requeries():
    calls = []

    async def run():
        client = youtube(handler_for(calls), max_searches_per_day=1)
        async with client.http:
            await client.search("instalar Epic Games")
            assert await client.search("instalar Epic Games")
            with pytest.raises(VideoUnavailable):
                await client.search("outro tutorial")
            client._cache.clear()
            with pytest.raises(VideoUnavailable):
                await client.search("instalar Epic Games")
    asyncio.run(run())
    assert len(calls) == 2


def test_expired_cache_is_removed_and_refetched(monkeypatch):
    calls, clock = [], [100.0]
    monkeypatch.setattr("app.videos.youtube.time.monotonic", lambda: clock[0])

    async def run():
        client = youtube(handler_for(calls))
        async with client.http:
            await client.search("instalar Epic Games")
            clock[0] += 3601
            client.purge_cache()
            assert not client._cache
            assert await client.search("instalar Epic Games")
    asyncio.run(run())
    assert len(calls) == 4


def test_missing_config_is_optional_and_secret_is_masked(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    assert get_video_settings() is None
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-youtube-secret")
    assert "test-youtube-secret" not in repr(get_video_settings())
    monkeypatch.setenv("YOUTUBE_TIMEOUT_SECONDS", "nan")
    with pytest.raises(VideoUnavailable):
        get_video_settings()


async def invoke(state, query="instalar Epic Games Windows"):
    raw = json.dumps({"query":query})
    context = ToolContext(context=state, tool_name="search_videos", tool_call_id="test", tool_arguments=raw)
    return json.loads(await search_videos.on_invoke_tool(context, raw))


def test_authorization_quota_current_permissions_and_selection():
    calls = []

    async def search(query):
        calls.append(query)
        return (video(),)

    state = CatalogContext(None, videos=SimpleNamespace(search=search))
    assert asyncio.run(invoke(state))["status"] == "not_authorized" and not calls
    state.video_consent = True
    assert asyncio.run(invoke(state))["status"] == "ok"
    assert asyncio.run(invoke(state))["status"] == "limit_reached"
    content, videos = extract_video(f"Siga o tutorial.\n[VIDEO:{ID}]", state)
    assert content == "Siga o tutorial." and videos[0].video_id == ID
    assert videos[0].watch_url in state.allowed_urls
    assert not CatalogContext(None).video_candidates
    assert extract_video("Texto sem vídeo.", state) == ("Texto sem vídeo.", [])
    for text in (f"[VIDEO:{ID}]", f"Texto [VIDEO:{ID}] [VIDEO:{ID}]"):
        with pytest.raises(AIProviderError):
            extract_video(text, state)


@pytest.mark.parametrize("text", [f"Tutorial [VIDEO:{ID}]", "Tutorial [VIDEO:inventado]", "Tutorial [VIDEO:../segredo]", "Tutorial [VIDEO:incompleto"])
def test_unqueried_and_malformed_video_markers_are_rejected(text):
    with pytest.raises(AIProviderError):
        extract_video(text, CatalogContext(None))


def test_api_real_sdk_attaches_only_consulted_video_and_survives_youtube_failure(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")
    monkeypatch.setenv("OPENAI_MODEL", "fake-model")
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.setenv("RAG_ENABLED", "false")
    for unavailable in (False, True):
        sent = []

        async def search(query):
            assert "Windows" in query
            if unavailable:
                raise VideoUnavailable()
            return (video(),)

        def handle(request):
            body = json.loads(request.content)
            sent.append(body)
            if len(sent) == 1:
                output = [{"type":"function_call", "id":"fc_video", "call_id":"video", "name":"search_videos",
                           "arguments":json.dumps({"query":"instalar Epic Games Windows"}), "status":"completed"}]
            else:
                text = "Use o instalador oficial adequado ao seu sistema."
                if not unavailable:
                    text += f"\n[VIDEO:{ID}]"
                output = [{"id":"msg_video", "type":"message", "role":"assistant", "status":"completed",
                           "content":[{"type":"output_text", "text":text, "annotations":[]}]}]
            return httpx.Response(200, json={"id":f"resp_{len(sent)}", "object":"response", "created_at":1,
                "model":"fake-model", "status":"completed", "output":output, "error":None,
                "incomplete_details":None, "instructions":None, "parallel_tool_calls":False,
                "tools":[], "tool_choice":"auto"})

        def make_client(**kwargs):
            return AsyncOpenAI(**kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)))

        monkeypatch.setattr(chat_service, "AsyncOpenAI", make_client)
        with TestClient(app) as client:
            app.state.videos = SimpleNamespace(search=search)
            result = client.post("/api/chat", json={"conversation_id":str(uuid4()),
                "message":"Como instalar Epic Games no Windows?", "include_videos":True})
        assert result.status_code == 200
        message = result.json()["message"]
        assert "[VIDEO:" not in message["content"]
        assert len(message["videos"]) == (0 if unavailable else 1)
        assert len(sent) == 2
        assert {t["name"] for t in sent[0]["tools"]} == {"search_games", "search_knowledge", "search_videos"}
        assert "test-youtube-secret" not in json.dumps(sent)
