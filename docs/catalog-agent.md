# Agente com catálogo — etapas 3B e 3C

## Objetivo e escopo

Usar a IGDB para fundamentar recomendações em metadados e fornecer links de origem
e de lojas recebidos do catálogo. Mantemos um agente, uma ferramenta e o contrato
textual de `POST /api/chat`: nenhuma mudança de frontend ou dependência adicional.

O catálogo não é uma base RAG nem pesquisa na web. Não restringimos a aplicação a
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

- Duas consultas de ferramenta por mensagem; três rodadas máximas do modelo.
  Cada rodada pode consumir tokens: `OPENAI_MAX_OUTPUT_TOKENS` vale por geração,
  não é um teto total de tokens ou de custo da mensagem. Se o modelo insistir em
  ferramentas sem finalizar em três rodadas, a requisição falha com HTTP 502.
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

`feature/catalog-recommendations` depende de `feature/igdb-catalog` (3A, PR #5).
Seu PR é inicialmente direcionado à feature-base para mostrar somente 3B/3C.
Nenhum desses PRs deve ser integrado sem revisão e aprovação. Após integrar 3A,
retargetar este PR para `develop` e verificar o diff e os testes novamente.

A etapa de esclarecimento mais detalhado permanece no PR #4, ainda não validado.
Esta feature altera as instruções mínimas necessárias ao catálogo; ao integrar
ambas, revisar a sobreposição em `game_agent.py`, sem sobrescrever uma pela outra.

Próximas melhorias, sujeitas a nova aprovação: avaliar relevância e orçamento de
contexto, ajustar taxonomias/atalhos, resposta estruturada com proveniência para
cards de lojas, integração de vídeos e RAG com fontes licenciadas. Não adicionamos
banco, AWS, múltiplos agentes ou busca web para viabilizar esta etapa.

Referências: [ferramentas do Agents SDK](https://developers.openai.com/api/docs/guides/agents/define-agents),
[execução do agente](https://developers.openai.com/api/docs/guides/agents/running-agents)
e [filtros IGDB](https://api-docs.igdb.com/#filters).
