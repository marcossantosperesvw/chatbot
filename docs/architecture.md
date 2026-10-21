# Arquitetura do Chat Jogos

## MVP atual

Monorepo com frontend Next.js/TypeScript e backend Python/FastAPI. São dois
componentes de uma aplicação, não uma arquitetura de microsserviços. Um único
agente do OpenAI Agents SDK responde via Responses API, com ferramenta IGDB e
ferramenta RAG local opcional. Não existem múltiplos agentes ou banco vetorial.

O backend também oferece `GET /api/games`, uma pesquisa por nome no catálogo IGDB
com autenticação Twitch, cache em memória e metadados/links normalizados. Ela é
independente do chat; o agente reutiliza o mesmo cliente, sem HTTP interno entre
rotas. Configuração em [Catálogo IGDB](igdb-catalog.md) e avaliação da integração
em [Agente com catálogo](catalog-agent.md).

Fluxo: usuário → frontend → `POST /api/chat` → serviço → agente → OpenAI → serviço
→ resposta JSON → frontend → histórico da sessão da aba.

1. O frontend recupera a sessão local e seleciona a conversa pelo UUID.
2. Ao enviar, separa histórico anterior e mensagem atual, validando limites.
3. A API valida novamente os dados; `system`/`tool` e campos extras são rejeitados.
4. O serviço monta o contexto uma vez, cria o agente e aguarda a resposta com timeout.
   Se necessário, OpenAI solicita `search_games`; o SDK executa a ferramenta no
   backend, consulta a IGDB e envia os resultados normalizados ao modelo. Este
   pode realizar uma segunda consulta antes da resposta final. Dependências,
   credenciais e lista local de URLs permitidas não são enviadas ao modelo.
5. O backend valida o texto e devolve o mesmo UUID, sem salvar a conversa.
6. O frontend associa a resposta à origem, mesmo após trocar de conversa, e salva
   o par concluído no `sessionStorage`. Erros preservam o rascunho, sem reenvio automático.

| Local | Responsabilidade |
| --- | --- |
| `frontend/src/components/chat/` | Interface, mensagens, menu e formulário |
| `frontend/src/hooks/` | Coordenação do estado e dos envios |
| `frontend/src/lib/` | HTTP, regras de conversa e armazenamento da sessão |
| `backend/app/api/` | Contrato público, validação e status HTTP |
| `backend/app/services/` | Orquestração da requisição sem estado compartilhado |
| `backend/app/agents/` | Instruções e configuração do agente |
| `backend/app/core/` | Configuração, erros e proteção dos logs |
| `backend/app/catalog/` | Cliente IGDB, credenciais e normalização dos dados |
| `backend/app/tools/` | Ferramenta tipada IGDB, orçamento local e URLs permitidas |
| `backend/app/videos/` | Cliente YouTube opcional, metadados, cache e orçamento |
| `backend/app/rag/` e `knowledge/` | Ingestão, índice JSON, busca lexical/semântica e documentos curados |
| `backend/app/conversations/` | Reservado; nenhuma persistência de servidor implementada |
| `backend/tests/` e `frontend/tests/` | Verificações sem serviços pagos |

Não criamos rotas Next.js que repitam as rotas de IA do FastAPI. Somente o backend
conhece a chave e as instruções do agente. O frontend não usa o SDK OpenAI.
O UUID organiza mensagens, mas não autentica usuários nem protege acesso.

## Decisões e limites

- REST com resposta completa, sem streaming: contrato menor e fácil de testar.
- `sessionStorage`: atende à recuperação na mesma sessão sem login ou banco;
  não oferece histórico permanente, sincronização entre dispositivos ou isolamento
  contra alguém com acesso à mesma aba. Fechar a aba normalmente encerra a sessão,
  sujeito à restauração de sessões pelo navegador.
- Contexto explícito por requisição: evita duplicar a memória do frontend com
  sessões do SDK ou estado hospedado. O histórico é reenviado e tem custo.
- Um agente com uma ferramenta de catálogo: pode explicar conceitos com seu
  conhecimento geral e consultar metadados para recomendações. As instruções
  exigem consulta antes de recomendar títulos e pedem esclarecimento para pedidos
  vagos. Isso precisa de avaliação comportamental, não é garantia determinística.
  URLs HTTP(S) ausentes dos resultados da requisição são rejeitadas pelo backend.
  Não há busca web geral ou preços. Tutoriais usam uma ferramenta YouTube opcional,
  autorizada por mensagem, com anexo estruturado e player por clique. RAG complementa o catálogo com
  documentos, fontes e filtros de jogo/plataforma/versão. Nenhuma compra é executada.
- Limites atuais: mensagem de 4.000 caracteres, até 50 mensagens anteriores,
  saída de 4.000 caracteres, geração padrão de 800 tokens e timeout de até 25s.
  Caracteres, tokens e custo são medidas diferentes. Não há teto financeiro por usuário.
- Até duas chamadas de catálogo, cinco jogos por chamada, duas consultas RAG e
  até três trechos por consulta. São cinco rodadas do modelo com índice RAG ativo
  e três sem ele. Com YouTube autorizado/configurado, soma-se uma rodada e até
  uma busca por mensagem. A memória de fontes e permissões é criada por requisição.
  O timeout total inclui ferramentas e esperas. A descoberta de catálogo filtra
  plataforma/gênero/modo com AND e prioriza volume de avaliações; não é uma busca
  semântica nem garante as melhores recomendações possíveis. Limites e cache do
  cliente são locais por processo, não uma proteção distribuída contra abuso.
- `store=False` e tracing desativado: minimizam estado adicional; não representam
  garantia de retenção zero pelo provedor. Veja o guia de privacidade do backend.
- Cliente assíncrono por requisição: ciclo de vida explícito e sem estado global
  de conversa. Reutilização do cliente pode ser avaliada se houver necessidade medida.

## Evolução e avaliação

Cada implementação exige escopo e aprovação próprios.

1. **RAG:** ingestão, índice JSON e recuperação lexical/semântica implementados,
   com ferramenta do agente e indicação de fontes. Ainda selecionar fontes reais
   e avaliar relevância/fidelidade. [Configuração e limites](rag-usage.md).
   Um catálogo estruturado de
   metadados não é automaticamente RAG. Uma base pequena melhora respostas sobre
   seu conteúdo, mas não deve limitar o chatbot exclusivamente àqueles jogos.
2. **Catálogo externo:** pesquisa independente e integração do agente com filtros
   implementadas. A aprovação das etapas depende de avaliação real pelo estudante.
   Avaliar relevância, esclarecimentos, falhas e distinção entre fatos e inferências.
3. **Lojas e vídeos:** YouTube implementado com busca, validação de incorporação e
   player na conversa. Configurar a chave e avaliar relevância com APIs reais.
   [Guia de vídeos](youtube-tutorials.md). Cards de lojas e links clicáveis no
   texto geral ainda podem ser implementados separadamente.
4. **Persistência permanente:** somente quando houver requisito de recuperar
   conversas entre sessões; decidir banco, autenticação, retenção e exclusão juntos.
5. **Deploy e AWS:** AWS é uma opção futura de infraestrutura, não requisito para
   usar a OpenAI e não substitui o SDK. Planejar hospedagem dos dois componentes,
   HTTPS, segredos fora do código, logs/monitoramento e limites de custo. Armazenamento
   de documentos e banco gerenciado só entram quando RAG/persistência justificarem.
   Serviços específicos, região, orçamento, CI/CD e eventual uso do `template.yaml`
   existente serão decididos na etapa de deploy; nenhum recurso AWS foi criado.

Antes de expor a aplicação publicamente, adicionar proteção contra abuso,
limitação de requisições e custos, configuração segura de ambientes e análise
de privacidade. CORS sozinho não protege uma API pública.

## Fluxo Git

`feature/*` normalmente nasce de `develop`. Quando há dependência de uma feature
pendente, uma branch empilhada pode nascer dela e ter um PR para essa base; depois
da integração da dependência, retargetar o PR para `develop`. Após testes e revisão,
integra-se em `develop`;
`main` recebe apenas versões aprovadas, nunca implementação direta. Commits em
português seguem Conventional Commits. Publicar uma branch não significa aprovar
sua integração nem implantar a aplicação.
