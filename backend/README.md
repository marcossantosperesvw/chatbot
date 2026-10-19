# Backend

API do chatbot construída com FastAPI e OpenAI Agents SDK para Python.

## Configuração

### Configurar a OpenAI — passo a passo

1. Entre na [OpenAI Platform](https://platform.openai.com/) e selecione seu projeto.
2. Crie uma chave em [API keys](https://platform.openai.com/api-keys), com permissão
   de geração de respostas. Verifique o faturamento, saldo e limites do projeto
   antes de usar a API. Não presuma que sua assinatura do ChatGPT habilita esta aplicação.
3. Na pasta `backend/`, copie `.env.example` para `.env` **somente se ainda não
   existir**. Não sobrescreva sua configuração anterior:

   ```bash
   cp -n .env.example .env
   ```

4. Edite `.env` localmente, sem compartilhar a chave no chat ou no Git:

   ```dotenv
   OPENAI_API_KEY=SUA_CHAVE_REAL_AQUI
   OPENAI_MODEL=ID_DO_MODELO_ESCOLHIDO
   OPENAI_TIMEOUT_SECONDS=25
   OPENAI_MAX_OUTPUT_TOKENS=800
   ```

   Os valores acima de chave/modelo são marcadores: substitua ambos. Escolha um
   modelo de texto acessível no seu projeto e compatível com a Responses API,
   consultando o [catálogo oficial](https://developers.openai.com/api/docs/models).
   Não há modelo padrão, para evitar uma escolha de custo implícita. Modelos com
   raciocínio podem precisar de outro orçamento de tokens/latência; a compatibilidade
   efetiva precisa ser conferida com o modelo escolhido.
5. Instale as dependências e inicie a API com os comandos abaixo. O `uv sync`
   instala `openai-agents`; o import Python é `agents`. Não instale um pacote
   chamado `agents`. Não é necessário criar um agente no painel: ele é definido
   em `app/agents/game_agent.py`, conforme o
   [quickstart oficial do SDK](https://developers.openai.com/api/docs/guides/agents/quickstart).
6. Reinicie o backend após mudar `.env`. O arquivo é carregado a partir da pasta
   `backend/`; variáveis já exportadas no terminal têm precedência sobre ele.

`OPENAI_TIMEOUT_SECONDS` aceita de 1 a 25 segundos e `OPENAI_MAX_OUTPUT_TOKENS`
aceita de 16 a 2048 tokens. Esses limites não equivalem a um teto financeiro:
o histórico também consome tokens e chamadas que falham ou expiram podem ter custo.

`CORS_ORIGINS` recebe uma lista de origens separadas por vírgulas, por exemplo:

```dotenv
CORS_ORIGINS=https://chat.exemplo.com,https://admin.exemplo.com
```

## Executar localmente

```bash
uv sync --locked
uv run --locked uvicorn app.main:app --reload
```

A API fica disponível em <http://localhost:8000>. Para verificar o serviço,
acesse `GET /api/health`.

## Catálogo de jogos — IGDB

A pesquisa independente de IA está disponível em `GET /api/games?query=nome&limit=5`.
Ela consulta a IGDB e devolve metadados normalizados, página de origem e links de
lojas recebidos do catálogo, quando disponíveis. O agente do chat agora usa a mesma
instância do cliente por meio da ferramenta `search_games`, sem chamar a própria API
via HTTP. A pesquisa independente não utiliza créditos da OpenAI; o chat utiliza.

Configure `IGDB_CLIENT_ID` e `IGDB_CLIENT_SECRET` no `.env` do backend, usando um
aplicativo confidencial registrado na Twitch. `IGDB_TIMEOUT_SECONDS` é opcional
(padrão 5; de 1 a 15 segundos). Não sobrescreva as configurações OpenAI existentes.
Sem credenciais IGDB, a rota do catálogo fica indisponível e a ferramenta do agente
informa a falha. Perguntas gerais podem continuar, mas recomendações fundamentadas
e links dependem da consulta.

O [guia do catálogo](../docs/igdb-catalog.md) explica como criar as credenciais,
testar pelo Swagger, interpretar os resultados e reconhecer os limites de cache,
autenticação e links. O [guia do agente com catálogo](../docs/catalog-agent.md)
explica filtros, limites e o roteiro de avaliação das etapas 3B e 3C.

## Contrato do chat

`POST /api/chat` recebe JSON e executa um agente via Responses API. Ainda não há
consultas RAG nem busca na web. O agente pode consultar o catálogo externo IGDB
com argumentos tipados, dentro dos limites por requisição.

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

O histórico validado fornece contexto ao agente. O backend não armazena conversas:
o frontend mantém mensagens e rascunhos no `sessionStorage` da aba. Não usamos
sessões persistentes do SDK nem IDs de conversas hospedadas na OpenAI.

### Resposta de sucesso — HTTP 200

```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": {
    "role": "assistant",
    "content": "Você joga em qual plataforma e com quantas pessoas?"
  }
}
```

O identificador devolvido permite associar a resposta à conversa correta. O
texto é retornado como conteúdo, não como HTML para execução no navegador.
O conteúdo real varia. Respostas vazias, não textuais ou acima de 4.000 caracteres
são rejeitadas, sem truncamento silencioso, para manter o próximo turno válido.

### Erros

- **HTTP 422:** JSON malformado ou contrato inválido. O campo `detail` contém
  uma lista de erros de validação do FastAPI/Pydantic; `loc` identifica o campo,
  `type` identifica a categoria e `msg` explica o problema. As mensagens de
  validação podem estar em inglês. A interface poderá apresentar textos em
  português a partir dessas informações.
- **HTTP 500:** falha inesperada durante o processamento. O campo `detail`
  contém o texto `Não foi possível processar a mensagem. Tente novamente.`.
  O log registra somente a categoria da exceção e o identificador da conversa.
- **HTTP 502:** falha de comunicação/provedor ou resposta inválida da IA, incluindo
  chave recusada, modelo inacessível ou cota excedida. Confira credenciais,
  acesso ao modelo, saldo e limites no painel; os detalhes do provedor não são expostos.
- **HTTP 503:** chave/modelo ausentes ou configuração local inválida. Corrija `.env`
  e reinicie a API. O health check continua disponível, mas não testa a OpenAI.
- **HTTP 504:** timeout da IA. O frontend preserva o rascunho, sem reenvio automático.

O cliente deve tratar `detail` conforme o status HTTP: é uma lista no erro 422
e um texto nos demais erros documentados.

### Testar manualmente

Com o servidor em execução, abra <http://localhost:8000/docs> ou execute:

```bash
curl -i http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"conversation_id":"550e8400-e29b-41d4-a716-446655440000","message":"Quero um jogo cooperativo."}'
```

Troque `message` por um texto vazio para observar o erro 422. Uma requisição válida
ao chat usa sua chave no backend e pode gerar cobrança. Não faça testes reais em loop.

Na interface, diga "Jogo no PC e gosto de cooperação" e depois "O que recomenda?".
Confira se a resposta considera o contexto. Crie outra conversa e verifique que
suas mensagens não contêm o histórico da anterior; isso é garantido pelo envio
separado, não por uma suposta memória global do agente.

## Organização e privacidade

- `api/`: valida o contrato e traduz falhas para HTTP.
- `services/chat_service.py`: monta histórico + mensagem atual uma única vez,
  aplica timeout e valida a saída. Abre e fecha um cliente assíncrono por requisição;
  é simples para o MVP, embora reaproveitar conexões possa ser útil depois.
- `agents/game_agent.md`: instruções editáveis de comportamento, lidas em UTF-8
  a cada requisição. Salve uma alteração e teste numa conversa nova; não é necessário
  reiniciar ao editar apenas esse Markdown. Nunca coloque credenciais nele.
- `agents/game_agent.py`: carrega e valida o Markdown, configura modelo e limite
  de geração. Arquivo ausente, vazio ou ilegível causa HTTP 503, sem chamada ao modelo.
  Um agente basta; há uma ferramenta de consulta, sem handoffs ou compras automáticas.
- `tools/catalog.py`: adapta a consulta para o SDK, limita resultados/chamadas e
  registra as URLs permitidas apenas durante a requisição atual.
- `catalog/`: autentica na Twitch, resolve filtros por nome na IGDB, controla cache
  e ritmo de requisições e normaliza os resultados. Não interpreta o perfil do usuário.
- `core/config.py`: lê e valida configurações, protegendo a representação da chave.
- `core/errors.py` e `core/logging.py`: falhas classificadas e logs do SDK sem
  mensagens brutas do provedor. Não habilite logs de depuração HTTP com dados reais.

O histórico da conversa selecionada é enviado à OpenAI a cada turno. Tracing do
SDK está desativado e enviamos `store=False`. Isso **não significa retenção zero**
nem elimina políticas de monitoramento do provedor; consulte os
[controles de dados oficiais](https://developers.openai.com/api/docs/guides/your-data).
Quando a ferramenta é acionada, os argumentos extraídos (nome/filtros) também são
enviados à IGDB; não enviamos a ela o histórico completo. Os metadados consultados
são enviados à OpenAI para compor a resposta. Não envie informações sensíveis.
`.env` é ignorado pelo Git; nunca use
`NEXT_PUBLIC_OPENAI_API_KEY` nem coloque uma chave em arquivos de exemplo.

Sem login e sem proteção contra abuso, esta versão é para desenvolvimento local.
CORS não autentica clientes. Antes de publicar, precisamos aprovar limites de
requisições, proteção da API e controle de custos. Até 50 mensagens de 4.000
caracteres ainda podem consumir muito contexto; sumarização/limite total de tokens
serão decisões futuras, sem descarte silencioso nesta entrega.

## Testes automatizados

Na pasta `backend/`:

```bash
uv sync --locked
uv run --locked pytest -q -W error
```

As dependências de teste (`pytest` e `httpx2`) ficam no grupo `dev`. O `httpx2`
é o cliente recomendado pela versão do Starlette instalada neste projeto.
A suíte usa
`TestClient` para exercitar a API sem iniciar um servidor de rede. Ela verifica
o contrato, os limites de entrada, as falhas inesperadas e o health check.
Os testes de IA executam o próprio SDK com transporte HTTP falso, chave fictícia,
sem rede ou cobrança, verificando contexto, isolamento, erros, logs e fechamento
do cliente. O cliente `openai` está limitado à faixa 2.26: a versão 2.54 exigia
um campo de uso de tokens que o Agents SDK 0.13.6 não preenchia. Atualize essa
combinação somente após repetir os testes; `uv.lock` fixa a combinação verificada.

## Avaliar perguntas e recomendações do agente

O agente investiga pedidos abertos com uma ou duas perguntas curtas, usando as
respostas e o histórico para decidir o próximo passo. Quando já há contexto
suficiente, consulta candidatos e recomenda somente quando houver evidência para
os requisitos essenciais. Pedir sugestões imediatas não autoriza inventar
preferências ou ignorar critérios. Aproximações exigem que o usuário aceite
flexibilizá-los. Plataforma, estilo, orçamento, dificuldade e modo de jogo não
formam um questionário obrigatório.

As regras e exemplos ficam em [`app/agents/game_agent.md`](app/agents/game_agent.md).
O módulo `app/agents/game_agent.py` lê esse arquivo em UTF-8 a cada criação do
agente e passa o texto para `Agent(instructions=...)`. Salvar o Markdown é suficiente
para a próxima requisição; não é necessário reiniciar ao editar somente esse arquivo.
Uma requisição em andamento continua com as instruções já carregadas. Ajustar o
texto muda o comportamento solicitado ao modelo, sem treinar um modelo novo ou
adicionar dados externos. A redação das respostas e a obediência podem variar.
O arquivo deve acompanhar o backend no deploy; se ausente, vazio ou ilegível, o
chat retorna HTTP 503, sem fallback silencioso para regras antigas.

Use o [roteiro de avaliação colaborativa](../docs/agent-evaluation.md) para testar
pedidos ambíguos, investigação gradual, contexto suficiente, correções e conversas
independentes. Ele também explica como registrar suas observações para decidirmos
os próximos ajustes juntos. Os testes automatizados continuam sem custo de API;
avaliar respostas reais na interface usa os créditos da OpenAI.

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

Melhorias seguintes, sujeitas à aprovação por etapa: recuperação RAG, streaming
e implantação. A ferramenta de catálogo já está integrada ao agente.
A evolução de infraestrutura está descrita em
[Arquitetura](../docs/architecture.md).
