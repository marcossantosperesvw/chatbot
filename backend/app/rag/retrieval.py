"""Busca local exata por metadados e ranking lexical ou por cosseno."""

import math
import re
import unicodedata
from collections import Counter

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field

from app.rag.embeddings import cosine, embed_texts
from app.rag.errors import RagError
from app.rag.index import KnowledgeIndex
from app.rag.schemas import KnowledgeChunk, Text


STOPWORDS = set("a ao aos as com como da das de do dos e em entre eu meu minha no nos na nas o os ou para por qual que se sem sua um uma voce jogo game".split())


def normalize(text: str) -> str:
    return " ".join("".join(char for char in unicodedata.normalize("NFKD", text.casefold())
                            if not unicodedata.combining(char)).split())


def tokens(text: str) -> list[str]:
    return [word for word in re.findall(r"\w+", normalize(text)) if word not in STOPWORDS]


class KnowledgeQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: Text = Field(max_length=500)
    game: Text = Field(max_length=200)
    platform: Text | None = Field(default=None, max_length=120)
    game_version: Text | None = Field(default=None, max_length=120)


class SearchHit(BaseModel):
    chunk: KnowledgeChunk
    score: float


class KnowledgeStore:
    """Snapshot imutável por processo; sem histórico, auto-indexação ou escrita."""

    def __init__(self, index: KnowledgeIndex, *, min_score=0.35):
        if not math.isfinite(min_score) or not 0 <= min_score <= 1:
            raise RagError("Limiar de recuperação inválido.")
        self.index = index
        self.min_score = min_score
        # Não adicionar jogo/título a todos os tokens: isso pode produzir matches
        # só pelo nome mesmo quando o trecho não contém a informação procurada.
        self._terms = [Counter(tokens(p.chunk.text)) for p in index.passages]
        self._lengths = [sum(counter.values()) for counter in self._terms]
        self._average = sum(self._lengths) / max(1, len(self._lengths)) or 1
        self._df = Counter(word for counter in self._terms for word in counter)

    async def search(self, params: KnowledgeQuery, *, client: AsyncOpenAI | None = None) -> list[SearchHit]:
        indices = []
        for position, passage in enumerate(self.index.passages):
            meta = passage.chunk.metadata
            if normalize(meta.game) != normalize(params.game):
                continue
            if params.platform and normalize(params.platform) not in {normalize(p) for p in meta.platforms}:
                continue
            if params.game_version and normalize(params.game_version) != normalize(meta.game_version or ""):
                continue
            indices.append(position)
        if not indices:
            return []  # Não chamar embeddings quando os filtros já não encontram documentos.
        scores = []
        if self.index.mode == "semantic":
            if client is None:
                raise RagError("Busca semântica requer cliente de embeddings.")
            vector = (await embed_texts(client, self.index.embedding_model, [params.query]))[0]
            scores = [(position, cosine(vector, self.index.passages[position].vector)) for position in indices]
        else:
            query_terms = set(tokens(params.query)) - set(tokens(params.game))
            for position in indices:
                score = 0.0
                for term in query_terms:
                    frequency = self._terms[position][term]
                    if not frequency:
                        continue
                    idf = math.log(1 + (len(self._terms) - self._df[term] + 0.5) / (self._df[term] + 0.5))
                    denominator = frequency + 1.5 * (0.25 + 0.75 * self._lengths[position] / self._average)
                    score += idf * frequency * 2.5 / denominator
                # Mapeamento monotônico para [0,1); não é probabilidade de verdade.
                scores.append((position, score / (1 + score)))
        ranked = sorted(scores, key=lambda pair: (-pair[1], self.index.passages[pair[0]].chunk.chunk_id))
        return [SearchHit(chunk=self.index.passages[position].chunk, score=score)
                for position, score in ranked[:3] if score > 0 and score >= self.min_score]
