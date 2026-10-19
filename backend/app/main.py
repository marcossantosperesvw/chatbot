import asyncio
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.catalog import router as catalog_router
from app.catalog.igdb_client import IGDBClient
from app.core.logging import configure_agent_logging

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
configure_agent_logging()

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(follow_redirects=False) as http:
        app.state.catalog = IGDBClient(http)
        maintenance = asyncio.create_task(app.state.catalog.maintain_token())
        try:
            yield
        finally:
            maintenance.cancel()
            with suppress(asyncio.CancelledError):
                await maintenance


app = FastAPI(title="Chatbot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(catalog_router)


@app.get("/api/health")
def health_check():
    return {"status": "online", "message": "Chatbot backend running successfully!"}
