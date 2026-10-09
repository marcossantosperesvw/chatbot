# Chatbot

Aplicação de chatbot organizada como um monorepo, com uma API FastAPI e uma
interface Next.js.

## Estrutura

```text
.
├── backend/     # API e serviços Python
├── frontend/    # Aplicação web Next.js
├── knowledge/   # Fontes para a base de conhecimento
└── template.yaml
```

Há um único repositório Git na raiz. As regras de arquivos ignorados também
ficam centralizadas no `.gitignore` da raiz.

## Requisitos

- Python 3.14 e [uv](https://docs.astral.sh/uv/)
- Node.js compatível com Next.js 16 e npm

## Desenvolvimento local

Crie os arquivos locais de configuração a partir dos exemplos:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

Instale e execute o backend:

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

Em outro terminal, instale e execute o frontend:

```bash
cd frontend
npm ci
npm run dev
```

A interface estará em <http://localhost:3000> e a API em
<http://localhost:8000>. O endpoint de diagnóstico é
<http://localhost:8000/api/health>.

## Configuração de ambientes

- `NEXT_PUBLIC_API_URL`: URL pública do backend usada pelo navegador. Como o
  Next.js incorpora variáveis `NEXT_PUBLIC_*` durante o build, defina o valor
  do ambiente de destino antes de executar `npm run build`.
- `CORS_ORIGINS`: origens autorizadas pelo backend, separadas por vírgulas.
  Em produção, informe a URL completa do frontend, por exemplo
  `https://chat.exemplo.com`.

Os valores padrão aceitam `localhost` e `127.0.0.1` apenas para desenvolvimento
local.

## Verificações

Antes de enviar alterações, execute:

```bash
cd frontend
npm run lint
npm run build

cd ../backend
uv run python -m compileall app scripts
```

Arquivos de ambiente e credenciais devem permanecer locais. Quando o projeto
precisar documentar variáveis, use arquivos `.env.example` sem valores
secretos.
