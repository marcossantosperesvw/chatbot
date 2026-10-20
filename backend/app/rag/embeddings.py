"""Embeddings opcionais: chamadas limitadas, sem modelo escolhido implicitamente."""

import math

from openai import AsyncOpenAI, OpenAIError

from app.rag.errors import RagError


def validate_vector(values) -> tuple[float, ...]:
    if (not isinstance(values, (list, tuple)) or not values
            or any(type(value) not in (int, float) or not math.isfinite(value) for value in values)):
        raise RagError("Embedding inválido.")
    vector = tuple(float(value) for value in values)
    if not math.isfinite(math.hypot(*vector)) or math.hypot(*vector) == 0:
        raise RagError("Embedding sem norma válida.")
    return vector


async def embed_texts(client: AsyncOpenAI, model: str, texts: list[str]) -> list[tuple[float, ...]]:
    """Lotes pequenos; cliente com retries desativados fornecido pelo chamador."""
    vectors = []
    try:
        for start in range(0, len(texts), 32):
            batch = texts[start:start + 32]
            response = await client.embeddings.create(model=model, input=batch, encoding_format="float")
            ordered = sorted(response.data, key=lambda item: item.index)
            if [item.index for item in ordered] != list(range(len(batch))):
                raise RagError("Resposta de embeddings incompleta.")
            vectors.extend(validate_vector(item.embedding) for item in ordered)
    except (OpenAIError, AttributeError, TypeError):
        raise RagError("Não foi possível gerar embeddings.") from None
    if vectors and len({len(vector) for vector in vectors}) != 1:
        raise RagError("Embeddings com dimensões inconsistentes.")
    return vectors


def cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise RagError("Dimensão da consulta incompatível com o índice.")
    left_norm, right_norm = math.hypot(*left), math.hypot(*right)
    # Normalizar antes do produto também evita overflow em índices locais inválidos.
    return max(-1.0, min(1.0, sum((a / left_norm) * (b / right_norm) for a, b in zip(left, right))))
