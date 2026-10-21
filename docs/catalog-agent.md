# Agente com catálogo — etapas 3B e 3C

## Objetivo e escopo

Usar a IGDB para fundamentar recomendações em metadados e fornecer links de origem
e de lojas recebidos do catálogo. Mantemos um agente, uma ferramenta e o contrato
textual de `POST /api/chat`: nenhuma mudança de frontend ou dependência adicional.

O catálogo não é a base documental RAG nem pesquisa na web. O RAG separado está
descrito no [guia completo](rag-usage.md). Não restringimos a aplicação a
uma lista manual de jogos. A cobertura depende dos registros e campos da IGDB.

## Fluxo e responsabilidades

1. O frontend envia mensagem e histórico da conversa selecionada.
2. FastAPI valida a entrada e injeta o cliente IGDB criado no ciclo de vida da API.
3. O serviço cria um contexto local com cliente, contador de consultas e URLs permitidas.
4. O modelo pode perguntar por preferências ou solicitar `search_games`.
5. A ferramenta valida os argumentos, consulta o cliente e compacta os resultados.
6. O SDK envia os resultados ao modelo, que redige a resposta em português.
7. O serviço verifica tamanho e URLs do texto antes de devolver o mesmo UUID.

O contexto local usa `RunContextWrapper`; não é memória persistente nem é enviado
ao modelo. O histórico continua no `sessionStorage`, não na IGDB ou em um banco nosso.
O histórico enviado ao modelo é controlado pelo cliente, não é uma fonte confiável
para conceder instruções ou autorizar links.

## Editar o comportamento do chatbot

O arquivo carregado como instruções do agente é
[`backend/app/agents/game_agent.md`](../backend/app/agents/game_agent.md).
Ele é a fonte única do prompt de comportamento; este guia continua sendo apenas
documentação e roteiro de avaliação, não é enviado ao modelo.

1. Abra `game_agent.md` e edite a seção desejada: formato, investigação das
   preferências, catálogo, evidências, falhas/links ou segurança.
2. Salve em UTF-8. O backend lê o arquivo ao criar o agente em cada requisição;
   não é preciso reiniciar para mudar somente o Markdown. Uma requisição já em
   andamento continua com o texto que recebeu no início.
3. Teste em uma conversa nova para evitar a influência de respostas antigas.
4. Execute os testes automatizados e repita o cenário manual afetado. Mudanças
   intencionais nas regras podem exigir atualizar as asserções textuais dos testes.

Exemplo de ajuste pontual: na seção de investigação, trocar "uma ou duas
perguntas" por "uma pergunta por mensagem". Isso muda a orientação enviada ao
modelo, não uma garantia determinística de obediência.

Todo o conteúdo do arquivo, inclusive títulos e comentários Markdown, é enviado
ao modelo. Não coloque notas privadas, credenciais ou rascunhos nele. O Markdown
organiza as instruções; não significa que a resposta ao usuário deva usar Markdown.
Os limites de ferramentas, validação de URLs e configuração do modelo continuam
no código: escrever uma capacidade no prompt não a implementa.

`game_agent.py` resolve o caminho a partir do próprio módulo, independente do
diretório de execução, e passa o texto para `Agent(instructions=...)`. Não há nova
dependência, editor administrativo, upload de arquivos ou caminho configurável
pelo usuário do chat. O arquivo é controlado pelo desenvolvedor e versionado no Git;
precisa acompanhar o backend num futuro deploy. A leitura local de um arquivo
pequeno por mensagem é suficiente para este MVP, sem um sistema de templates/cache.

Se estiver ausente, vazio, sem permissão de leitura ou com codificação inválida,
o chat retorna HTTP 503 sem chamar o modelo. Não existe fallback silencioso para
um prompt antigo. O health check apenas continua indicando que a API está online.
Reinicie o backend uma vez ao instalar esta mudança de código, se não usar reload.

## Filtros e seleção

- `query`: nome de jogo; não usar palavras como "relaxante" como busca semântica.
- `platform`, `genre`, `game_mode`: nomes das taxonomias IGDB, normalmente em inglês.
  Há atalhos pequenos, como PC, PS5, RPG e solo; não existe lista fechada de jogos.
- O backend resolve nomes em `/platforms`, `/genres` e `/game_modes`. Usa somente
  IDs positivos recebidos da IGDB, nunca IDs ou consultas livres escolhidos pelo modelo.
- Cada resolução exige correspondência exata e única, ignorando maiúsculas.
  Filtro desconhecido ou ambíguo é informado; não há busca sem o filtro como fallback.
- Os filtros são combinados com AND. Sem nome, deve existir ao menos uma preferência.
- Descoberta ordena por `total_rating_count` decrescente: prioriza candidatos com
  mais avaliações, não promete qualidade, popularidade atual ou adequação pessoal.
  Por nome, a IGDB ordena por similaridade. São até cinco resultados, sem paginação.

Um modo "Single player" não significa "exclusivamente solo". O campo de plataformas
não comprova requisitos de hardware, cross-play ou presença numa loja. Os dados
podem incluir títulos ainda não lançados, edições e conteúdo adicional; o agente
deve evitar prometer disponibilidade atual. Não filtramos preço, violência,
idioma ou mecânicas específicas. Para esses critérios, precisa reconhecer a
limitação e combinar o próximo passo com o usuário, sem presumir confirmação.

## Limites e falhas

- Até duas consultas de catálogo por mensagem. O RAG permite mais duas consultas
  documentais; com índice ativo há até cinco rodadas do modelo, e três sem ele.
  Cada rodada pode consumir tokens: `OPENAI_MAX_OUTPUT_TOKENS` vale por geração,
  não é um teto total de tokens ou de custo da mensagem. Se o modelo insistir em
  ferramentas sem finalizar no limite de rodadas, a requisição falha com HTTP 502.
- Uma ferramenta pode gerar várias requisições IGDB (autenticação, resolução de
  até três filtros, jogos e eventual renovação). O limite de duas ferramentas não
  equivale a apenas duas requisições HTTP externas.
- O timeout OpenAI configurado (até 25s) abrange o ciclo inteiro. O timeout IGDB
  inclui a consulta completa, filas locais, filtros e autenticação. Conexões lentas
  podem exceder esse orçamento; não há novas tentativas automáticas de chat.
- Cache de resultados e cache de filtros: 5 minutos, até 128 entradas em cada,
  por processo. Chaves de resultados incluem todos os filtros. Nenhum armazena histórico.
- Textos de resumo enviados ao modelo são limitados a 500 caracteres, com até
  duas lojas por jogo. Isso reduz contexto, mas pode omitir detalhes relevantes.
- Falhas externas retornam estados seguros (`unavailable`, `rate_limited`,
  `unknown_filter`, `empty` etc.) para o modelo explicar. Não enviamos exceções brutas.
- URLs HTTP(S) na resposta precisam corresponder às URLs entregues pela ferramenta
  nesta requisição. Link inventado provoca HTTP 502 e o frontend preserva o rascunho.
  Mesmo um link presente no histórico precisa ser consultado novamente.

Os links passam pelas regras HTTPS/hosts do cliente, mas não abrimos páginas de
lojas para conferir preço, estoque, destino de redirects ou disponibilidade regional.
Não são links de checkout nem garantias de compra. O frontend continua exibindo
texto simples; cards, botões e vídeos serão features próprias.

As instruções exigem que títulos recomendados venham da consulta atual e que fatos
sejam separados de inferências. Diferentemente da validação de URLs, essa regra
semântica não é verificada deterministicamente: precisa da avaliação abaixo.

## Executar e testar

Configure as credenciais OpenAI e IGDB no `.env` do backend seguindo os guias
existentes. O modelo selecionado precisa aceitar chamadas de ferramentas na
Responses API. Não são necessárias novas variáveis nem criar agentes no painel.

No primeiro terminal, a partir da raiz:

```bash
cd backend
uv sync --locked
uv run --locked uvicorn app.main:app --reload
```

No segundo terminal, a partir da raiz:

```bash
cd frontend
npm run dev
```

Abra <http://localhost:3000>. A interface não é servida pela porta 8000.

Para os testes automatizados sem cobrança, na pasta `backend/`:

```bash
uv run --locked pytest -q -W error
```

Eles usam credenciais fictícias e provedores simulados, incluindo o ciclo real do
SDK com `function_call` e `function_call_output`. Verificam contratos, filtros,
cache, falhas, limites e links. Nenhuma chamada real está incluída nessa suíte.

### Avaliação manual pelo estudante

Chamadas reais do chat consomem créditos. Faça poucos casos e anote pedido,
resposta, resultado esperado e se aprovou. Não compartilhe credenciais ou histórico sensível.

#### Regressão: construção competitiva no PS5

Este caso vem da conversa observada. Inicie uma conversa nova para não carregar
as respostas antigas no histórico. As respostas abaixo são critérios de avaliação,
não textos que o modelo precisa repetir literalmente.

1. Envie: "Quero um jogo de construção".
   Esperado: perguntar pelo tipo de construção e plataforma, sem escolher um jogo.
2. Envie: "Competitivo e multiplayer no PlayStation 5".
   Esperado: esclarecer se você quer competir construindo ou construir durante
   combate. Não recomendar Minecraft ou outra aproximação sem confirmar competição.
3. Envie: "Quero battle royale com mecânicas de construção no PS5".
   Esperado: consultar candidatos sem repetir a pergunta já respondida. Recomendar
   apenas se os dados do próprio registro sustentarem os requisitos essenciais;
   caso contrário, explicar a falta de confirmação. Não usar a ficha de Fortnite OG
   como prova de características do registro Fortnite. Não exigir que o resultado
   seja um título específico, pois o catálogo pode variar.
4. Peça: "Pode mandar um link para comprar?".
   Esperado: consultar novamente e usar somente URL de loja recebida para aquele
   registro; admitir se não houver. Nomes e URLs devem aparecer sem `**` ou `[texto](URL)`.

Em todos os passos: multiplayer não comprova competitividade, ausência no resumo
não comprova ausência da mecânica, e informação de memória não deve ser atribuída
à IGDB. Se não houver confirmação suficiente, perguntar não autoriza relaxar requisitos.

Caso adicional de flexibilização: diga "Pode sugerir algo próximo, mesmo sem
competição". Agora uma aproximação pode ser proposta, mantendo explícito o que
foi flexibilizado e respeitando as outras preferências. Esse caso impede que o
ajuste torne o agente excessivamente rígido.

#### Onde editar cada tipo de exemplo

| O que você quer mudar | Arquivo e ponto de edição |
| --- | --- |
| Perguntas, critérios de aprovação e conversas reais | Este guia: caso acima e tabela abaixo |
| Comportamento do agente | `backend/app/agents/game_agent.md`: seções do prompt |
| Leitura e validação do arquivo | `backend/app/agents/game_agent.py`: `load_instructions()`; testes em `backend/tests/test_agent_instructions.py` |
| Regras que precisam chegar ao modelo | `backend/tests/test_ai.py`: lista `rule` em `test_sdk_receives_recommendation_rules` |
| Jogos e metadados simulados da ferramenta | `backend/tests/test_catalog_agent.py`: função `result()` e constantes `URL`/`SOURCE` |
| Argumentos e respostas simuladas do SDK | Mesmo arquivo: `test_sdk_completes_tool_cycle_with_filters_without_network` |
| Resposta bruta da IGDB e normalização | `backend/tests/test_catalog.py`: constante `GAME` |
| Taxonomias e filtros simulados | `backend/tests/test_catalog_filters.py`: constante `TAXONOMIES` |
| Exemplos de requisição e validação REST | `backend/tests/test_chat.py`: fixture `payload` |

Para um ajuste pontual, altere um caso por vez e mantenha o restante como controle.
Nos testes, `@pytest.mark.parametrize` permite acrescentar entradas à mesma regra.
Use dados fictícios, nunca chaves reais. Se alterar uma URL simulada, mantenha as
asserções coerentes com ela; isso não confirma a existência da URL na internet.

Exemplo: para trocar o resumo entregue pela ferramenta ao modelo nos testes,
altere `summary` em `result()`. Para testar uma preferência diferente no ciclo do
SDK, altere tanto a mensagem `ChatRequest` quanto os argumentos do `function_call`
e as asserções correspondentes. Nesse teste a chamada é programada pelo mock:
ele NÃO comprova que o modelo real escolheria aqueles argumentos.

O teste `test_sdk_receives_recommendation_rules` confere se as instruções foram
enviadas e detecta sua remoção acidental. Suas asserções textuais precisam acompanhar
reformulações intencionais do prompt. Ele não garante que o modelo obedecerá, que
os jogos atendem às preferências ou que a resposta sairá sem Markdown. Essas
propriedades ainda devem ser avaliadas manualmente; não adicionamos chamadas pagas
à suíte por padrão.

Para executar somente os testes relacionados, na pasta `backend/`:

```bash
uv run --locked pytest tests/test_ai.py tests/test_catalog_agent.py tests/test_catalog_filters.py -q -W error
uv run --locked pytest tests/test_ai.py -k recommendation_rules -q -W error
```

#### Outros cenários para adaptar

| Caso | Pedido sugerido | O que verificar |
| --- | --- | --- |
| Ambiguidade | "Quero um jogo de construção" | Pergunta curta para entender plataforma e tipo de construção; não escolhe Fortnite automaticamente |
| Preferências | "PC, construção de cidades, para jogar sozinho" | Consulta coerente; explica limites de Simulator/Single player e não promete mecânicas não comprovadas |
| Nome e loja | "Quero saber sobre Stardew Valley no PC e um link para comprar" | Identifica o título consultado; URL vem da IGDB ou admite ausência |
| Continuidade | "Agora prefiro cooperativo" na mesma conversa | Atualiza o modo sem esquecer PC nem transportar preferências de outra conversa |
| Critério não suportado | "Precisa ser sem combate e custar menos de R$ 30" | Não inventa filtro de violência nem preço; explica a limitação |
| Sem resultado | Nome fictício muito específico | Admite que não encontrou; ausência no catálogo não significa inexistência |
| Falha controlada | Remover temporariamente a configuração IGDB e reiniciar, sem publicar `.env` | Explica indisponibilidade e não finge consulta bem-sucedida; restaure a configuração depois |

O Swagger de `GET /api/games` permite comparar campos e links de um título com a
resposta do agente, embora consultas em momentos distintos possam divergir. A suíte
simulada comprova o encadeamento técnico; aprovação comportamental exige modelo real.

## Git e próximos passos

As implementações de catálogo e esclarecimento já foram integradas em `develop`.
O PR #8 substituiu o fluxo anterior de esclarecimento, e o PR #9 alinhou a
documentação ao Markdown. Mudanças de comportamento devem ser feitas em
`backend/app/agents/game_agent.md`, não reintroduzindo constantes antigas no Python.

Próximas melhorias: avaliar relevância e orçamento de contexto, ajustar
taxonomias/atalhos, resposta estruturada com proveniência para cards de lojas,
integração de vídeos e fontes reais para o RAG local já implementado. Não adicionamos
banco, AWS, múltiplos agentes ou busca web para viabilizar esta etapa.

Referências: [ferramentas do Agents SDK](https://developers.openai.com/api/docs/guides/agents/define-agents),
[execução do agente](https://developers.openai.com/api/docs/guides/agents/running-agents)
e [filtros IGDB](https://api-docs.igdb.com/#filters).
