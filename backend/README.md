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

## Contrato do chat

`POST /api/chat` recebe JSON e devolve uma resposta simulada. Esta etapa valida
a comunicação HTTP; ainda não chama a OpenAI nem faz consultas RAG.

### Requisição

```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Quero recomendações de jogos cooperativos.",
  "history": [
    {"role": "user", "content": "Jogo no PC."},
    {"role": "assistant", "content": "Você prefere jogar sozinho?"}
  ]
}
```

- `conversation_id`: UUID obrigatório, criado pelo cliente para identificar a
  conversa. Não representa autenticação ou armazenamento no servidor.
- `message`: texto obrigatório entre 1 e 4.000 caracteres, após remover espaços
  nas extremidades. Textos compostos apenas por espaços são rejeitados.
- `history`: lista opcional, vazia por padrão, com até 50 mensagens anteriores,
  em ordem cronológica. Cada item contém `role` (`user` ou `assistant`) e
  `content`, sujeito às mesmas regras de texto de `message`.
- A mensagem atual deve aparecer somente em `message`, sem repetição no histórico.
- Campos desconhecidos são rejeitados, inclusive dentro das mensagens anteriores.

O histórico é validado, mas ainda não é interpretado pelo simulador. Nesta etapa,
o backend não armazena conversas. O salvamento na sessão da aba será implementado
separadamente no frontend.

### Resposta de sucesso — HTTP 200

```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": {
    "role": "assistant",
    "content": "Resposta simulada: recebi sua mensagem «Quero recomendações de jogos cooperativos.». A integração com inteligência artificial ainda não está habilitada."
  }
}
```

O identificador devolvido permite associar a resposta à conversa correta. O
texto é retornado como conteúdo, não como HTML para execução no navegador.

### Erros

- **HTTP 422:** JSON malformado ou contrato inválido. O campo `detail` contém
  uma lista de erros de validação do FastAPI/Pydantic; `loc` identifica o campo,
  `type` identifica a categoria e `msg` explica o problema. As mensagens de
  validação podem estar em inglês. A interface poderá apresentar textos em
  português a partir dessas informações.
- **HTTP 500:** falha inesperada durante o processamento. O campo `detail`
  contém o texto `Não foi possível processar a mensagem. Tente novamente.`.
  Detalhes técnicos ficam no log do servidor.

O cliente deve tratar `detail` conforme o status HTTP: é uma lista no erro 422
e um texto no erro 500.

### Testar manualmente

Com o servidor em execução, abra <http://localhost:8000/docs> ou execute:

```bash
curl -i http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"conversation_id":"550e8400-e29b-41d4-a716-446655440000","message":"Quero um jogo cooperativo."}'
```

Troque `message` por um texto vazio para observar o erro 422. O endpoint de chat
não exige chave de API nesta etapa.

## Testes automatizados

Na pasta `backend/`:

```bash
uv sync --locked
uv run --locked pytest
```

As dependências de teste (`pytest` e `httpx2`) ficam no grupo `dev`. O `httpx2`
é o cliente recomendado pela versão do Starlette instalada neste projeto.
A suíte usa
`TestClient` para exercitar a API sem iniciar um servidor de rede. Ela verifica
o contrato, os limites de entrada, as falhas inesperadas e o health check.

## Fluxo de desenvolvimento

Cada tarefa começa em uma branch `feature/*`, criada a partir de `develop`.
Depois da revisão e dos testes, a funcionalidade pode ser integrada em
`develop`. A branch `main` recebe versões aprovadas, sem implementação direta.

Use commits em português no formato Conventional Commits, por exemplo:
`feat(api): adiciona contrato de chat com resposta simulada`.

Antes de cada implementação, apresente objetivo, arquivos envolvidos,
tecnologias, conceitos e justificativa das decisões, aguardando aprovação.
Depois da entrega, explique as alterações, o funcionamento, como executar e
testar, e as melhorias futuras. Cada aprovação autoriza somente a etapa descrita.

Melhorias seguintes, sujeitas à aprovação por etapa: interface de chat,
histórico na sessão do navegador, integração com OpenAI e recuperação RAG.
