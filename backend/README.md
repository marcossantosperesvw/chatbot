# Backend

API do chatbot construída com FastAPI.

## Configuração

Copie `.env.example` para `.env` e ajuste `CORS_ORIGINS`. A variável recebe uma
lista de origens separadas por vírgulas, por exemplo:

```dotenv
CORS_ORIGINS=https://chat.exemplo.com,https://admin.exemplo.com
```

## Executar localmente

```bash
uv sync
uv run uvicorn app.main:app --reload
```

A API fica disponível em <http://localhost:8000>. Para verificar o serviço,
acesse `GET /api/health`.
