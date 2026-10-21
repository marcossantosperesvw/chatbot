"""python -m app.rag.cli: indexação e inspeção explícitas, fora da API do chat."""

import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import ValidationError

from app.rag.config import BACKEND_ROOT
from app.rag.embeddings import embed_texts
from app.rag.errors import RagError
from app.rag.index import IndexedPassage, KnowledgeIndex, build_index, load_index, save_index
from app.rag.retrieval import KnowledgeQuery, KnowledgeStore


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="RAG local: construir índice ou consultar sem gerar respostas.")
    commands = result.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--input", type=Path, required=True)
    build.add_argument("--output", type=Path, default=BACKEND_ROOT / ".data/rag-index.json")
    build.add_argument("--mode", choices=["lexical", "semantic"], default="lexical")
    build.add_argument("--embedding-model")
    build.add_argument("--max-chars", type=int, default=1200)
    build.add_argument("--force", action="store_true", help="Substituir um índice existente.")
    query = commands.add_parser("search")
    query.add_argument("--index", type=Path, required=True)
    query.add_argument("--query", required=True)
    query.add_argument("--game", help="Omitir para buscar somente documentos gerais.")
    query.add_argument("--product", help="Filtro exato de serviço/produto, por exemplo Steam.")
    query.add_argument("--platform")
    query.add_argument("--game-version")
    query.add_argument("--min-score", type=float, default=0.35)
    for command in (build, query):
        command.add_argument("--allow-synthetic", action="store_true", help="Somente demonstração com conteúdo fictício.")
        command.add_argument("--allow-paid", action="store_true", help="Autorizar envio de texto à API de embeddings (pode cobrar).")
    return result


def _client() -> AsyncOpenAI:
    load_dotenv(BACKEND_ROOT / ".env")
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RagError("Configure OPENAI_API_KEY para embeddings.")
    return AsyncOpenAI(api_key=key, base_url="https://api.openai.com/v1", timeout=20, max_retries=0)


async def run(args):
    if args.command == "build":
        if args.output.resolve().is_relative_to(args.input.resolve()):
            raise RagError("Salve o índice fora do diretório dos documentos.")
        if args.output.exists() and not args.force:
            raise RagError("Índice já existe; use --force para substituir explicitamente.")
        if args.mode == "lexical" and args.embedding_model:
            raise RagError("--embedding-model exige --mode semantic.")
        if args.mode == "semantic" and (not args.allow_paid or not args.embedding_model or not args.embedding_model.strip()):
            raise RagError("Modo semântico exige --embedding-model e --allow-paid; texto será enviado à OpenAI.")
        index = build_index(args.input, max_chars=args.max_chars, allow_synthetic=args.allow_synthetic)
        if args.mode == "semantic":
            async with _client() as client:
                vectors = await embed_texts(client, args.embedding_model.strip(), [p.chunk.text for p in index.passages])
            index = KnowledgeIndex(**(index.model_dump() | {
                "mode": "semantic", "embedding_model": args.embedding_model.strip(),
                "passages": tuple(IndexedPassage(chunk=p.chunk, vector=v) for p, v in zip(index.passages, vectors)),
            }))
        save_index(index, args.output, force=args.force)
        print(f"Índice {index.mode}: {len(index.revisions)} documento(s), {len(index.passages)} trecho(s).")
    else:
        index = load_index(args.index, allow_synthetic=args.allow_synthetic)
        store = KnowledgeStore(index, min_score=args.min_score)
        params = KnowledgeQuery(query=args.query, game=args.game, product=args.product,
                                platform=args.platform, game_version=args.game_version)
        if index.mode == "semantic":
            if not args.allow_paid:
                raise RagError("Consulta semântica exige --allow-paid; a pergunta será enviada à OpenAI.")
            async with _client() as client:
                hits = await store.search(params, client=client)
        else:
            hits = await store.search(params)
        for hit in hits:
            print(hit.model_dump_json(indent=2))
        if not hits:
            print("Nenhuma evidência acima do limiar para esses filtros.")


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        asyncio.run(run(args))
    except RagError as error:
        print(str(error))  # As mensagens desta classe são estáticas e sem documentos/segredos.
        return 1
    except (ValidationError, OSError, ValueError):
        # Exceções de validação/provedor podem conter partes dos documentos.
        print("Não foi possível concluir. Confira arquivos, metadados, permissões, flags e configuração.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
