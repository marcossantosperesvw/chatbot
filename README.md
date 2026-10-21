# Chat Jogos

Chatbot web especializado em jogos eletrônicos, com recomendações contextualizadas,
consulta ao catálogo IGDB, recuperação de documentos locais (RAG) e tutoriais do
YouTube com reprodução na conversa.

O projeto foi desenvolvido de forma incremental, com propósito educacional:
aplicar desenvolvimento full-stack, integração com modelos de linguagem e boas
práticas de engenharia sem introduzir infraestrutura desnecessária ao MVP.

**Estágio atual:** MVP para execução e avaliação local. Não há implantação pública,
autenticação ou persistência de conversas no servidor. AWS está prevista como
evolução futura; esta documentação não representa uma certificação de produção.

## Navegação

- [Funcionalidades](#funcionalidades)
- [Tecnologias](#tecnologias)
- [Arquitetura](#arquitetura)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Execução local](#execução-local)
- [Configuração](#configuração)
- [Base documental e RAG](#base-documental-e-rag)
- [API](#api)
- [Testes e qualidade](#testes-e-qualidade)
- [Segurança, privacidade e custos](#segurança-privacidade-e-custos)
- [Solução de problemas](#solução-de-problemas)
- [Fluxo de desenvolvimento](#fluxo-de-desenvolvimento)
- [Limitações e evolução](#limitações-e-evolução)
- [Documentação complementar](#documentação-complementar)

## Funcionalidades

- Conversas em português, com histórico usado para contextualizar respostas.
- Investigação de preferências antes de recomendar jogos em pedidos ambíguos.
- Pesquisa de jogos por nome ou filtros de plataforma, gênero e modo via IGDB.
- Links de compra provenientes do catálogo, sujeitos à lista de lojas permitidas.
- RAG opcional sobre documentos curados, com filtros e identificação dos trechos.
- Busca opcional de tutoriais no YouTube, autorizada pelo usuário, com player
  carregado por clique e sem reprodução automática.
- Múltiplas conversas e rascunhos na sessão da aba, recuperáveis pelo menu lateral.
- Interface responsiva, estados de carregamento e erros com preservação do rascunho.

As instruções do agente exigem consultar o catálogo antes de recomendar títulos.
Essa orientação depende do comportamento do modelo; não constitui uma garantia
determinística de correção. O sistema não possui busca web geral, não executa
compras e não consulta preços ou estoque em tempo real.

## Tecnologias

| Camada | Tecnologia | Papel no projeto |
| --- | --- | --- |
| Interface | Next.js 16, React 19, TypeScript | Páginas, componentes e contratos tipados |
| Estilização | Tailwind CSS 4 | Layout responsivo e identidade visual |
| Execução do frontend | Node.js e npm | Servidor Next.js, dependências, build e testes |
| API | Python 3.14, FastAPI, Pydantic | Rotas REST, validação e respostas JSON |
| Servidor da API | Uvicorn | Execução da aplicação FastAPI |
| Agente | OpenAI Agents SDK e OpenAI API | Geração de respostas e uso de ferramentas |
| Integrações HTTP | HTTPX | Comunicação com IGDB/Twitch e YouTube |
| Recuperação documental | Índice JSON local, BM25 ou embeddings opcionais | Busca de evidências para o agente |
| Histórico | `sessionStorage` do navegador | Conversas temporárias, sem banco ou login |
| Qualidade | pytest, Node.js Test Runner, ESLint e TypeScript | Testes e verificações estáticas |

As versões exatas das dependências estão em `backend/uv.lock` e
`frontend/package-lock.json`. Não é necessário instalar LangChain, banco vetorial,
filas ou microsserviços para executar este MVP.

## Arquitetura

O monorepo reúne dois componentes de uma aplicação: frontend e backend.
O frontend não acessa diretamente a OpenAI nem recebe suas credenciais.

```text
Navegador: Next.js / React
  ├── Interface e estado das conversas
  └── sessionStorage da aba
                │ POST /api/chat — JSON
                ▼
Backend: FastAPI
  └── Validação → serviço do chat → agente OpenAI
                                      │ ferramentas, conforme a pergunta
                                      ├── IGDB: metadados e lojas
                                      ├── RAG: documentos do índice local
                                      └── YouTube: tutoriais, se autorizados
                │ resposta JSON validada
                ▼
Navegador: mensagem, links aprovados e eventual vídeo
```

1. O usuário envia uma mensagem na conversa selecionada.
2. O frontend envia identificador, mensagem atual, histórico anterior e autorização
   opcional para vídeos, sem repetir a mensagem atual no histórico.
3. O FastAPI valida os dados e chama o serviço do chat.
4. O serviço carrega as instruções, prepara o contexto e executa o agente.
5. O modelo pode pedir esclarecimentos, responder conceitos gerais ou solicitar
   ferramentas. Não existe uma consulta IGDB obrigatória antes de toda pergunta.
6. As ferramentas executam no backend e devolvem dados ao modelo, que compõe a resposta.
7. O backend verifica limites de saída, URLs e marcadores de fontes/anexos.
8. O frontend associa a resposta à conversa de origem e atualiza a sessão local.

O UUID identifica a conversa; não autentica um usuário. O backend não mantém
memória permanente: o histórico é reenviado em cada mensagem.

## Estrutura do repositório

```text
chatbot/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI, CORS e ciclo de vida
│   │   ├── api/             # Rotas HTTP e contratos de entrada/saída
│   │   ├── services/        # Coordenação da execução do chat
│   │   ├── agents/          # Configuração e instruções Markdown do agente
│   │   ├── tools/           # Ferramentas de catálogo, documentos e vídeos
│   │   ├── catalog/         # Cliente IGDB, filtros e validação de lojas
│   │   ├── rag/             # Ingestão, índice, busca e CLI documental
│   │   ├── videos/          # Cliente YouTube e contratos dos anexos
│   │   ├── core/            # Configuração, erros e logs
│   │   └── conversations/   # Reservado; sem persistência de servidor
│   ├── scripts/             # Utilitários auxiliares
│   ├── tests/               # Testes, fixtures e casos de avaliação
│   ├── .env.example         # Variáveis documentadas, sem segredos
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/
│   ├── src/
│   │   ├── app/             # Páginas, layout, estilos e privacidade
│   │   ├── components/chat/ # Chat, menu, formulário, mensagens e vídeo
│   │   ├── hooks/           # Coordenação do estado e dos envios
│   │   ├── lib/             # Cliente HTTP, sessão e validações
│   │   └── types/           # Tipos do contrato e das conversas
│   ├── tests/
│   ├── .env.example
│   └── package-lock.json
├── knowledge/               # Documentos Markdown e metadados JSON do RAG
├── shared/                  # Política de lojas e casos de validação comuns
├── docs/                    # Guias técnicos e decisões de arquitetura
└── template.yaml            # Esboço AWS SAM; sem recursos de deploy definidos
```

## Execução local

### Pré-requisitos

- Git.
- Python 3.14 e [uv](https://docs.astral.sh/uv/).
- Node.js 24 para executar também os testes TypeScript nativos do frontend
  (ambiente usado no desenvolvimento) e npm.
- Acesso à internet e credenciais OpenAI para respostas reais.
- Credenciais Twitch/IGDB para recomendações fundamentadas no catálogo.
- Chave YouTube Data API v3 somente para habilitar tutoriais.

Embora o Next.js instalado aceite Node.js a partir de 20.9, use Node.js 24 para
seguir os comandos de teste deste projeto sem configuração adicional.

### 1. Preparar os ambientes

Na raiz do repositório, crie os arquivos locais **apenas se ainda não existirem**:

```bash
cp -n backend/.env.example backend/.env
cp -n frontend/.env.example frontend/.env.local
```

Edite `backend/.env`, preenchendo `OPENAI_API_KEY`, `OPENAI_MODEL`,
`IGDB_CLIENT_ID` e `IGDB_CLIENT_SECRET`. Nunca compartilhe esses valores.
O modelo é uma escolha explícita: não há modelo padrão definido no código.
O [guia do backend](backend/README.md) explica a configuração da OpenAI;
o [guia IGDB](docs/igdb-catalog.md) explica o aplicativo confidencial da Twitch.

### 2. Iniciar o backend

Em um terminal, a partir da raiz:

```bash
cd backend
uv sync --locked
uv run --locked uvicorn app.main:app --reload
```

### 3. Iniciar o frontend

Em outro terminal, a partir da raiz:

```bash
cd frontend
npm ci
npm run dev
```

Mantenha os dois processos ativos. `--reload` e `npm run dev` são recursos de
desenvolvimento, não uma configuração de produção.

| Endereço local | Finalidade |
| --- | --- |
| [localhost:3000](http://localhost:3000) | Interface do chatbot |
| [localhost:8000/docs](http://localhost:8000/docs) | Documentação interativa da API |
| [localhost:8000/api/health](http://localhost:8000/api/health) | Diagnóstico básico do backend |
| [localhost:3000/privacidade](http://localhost:3000/privacidade) | Política apresentada pela aplicação |

### 4. Conferir o funcionamento

1. Abra a interface e envie um pedido, como “Quero um jogo cooperativo para PC”.
2. Responda às perguntas de esclarecimento e confira a recomendação e suas fontes.
3. Crie outra conversa, alterne pelo menu e atualize a aba para testar a sessão.
4. Se configurou o YouTube, leia a autorização na interface, habilite tutoriais e
   faça uma pergunta de instalação ou configuração.

Requisições reais ao chat podem gerar cobrança OpenAI. O health check apenas
confirma que o backend responde: não testa credenciais, saldo ou todas as integrações.

## Configuração

Use os arquivos de exemplo como referência completa. Reinicie o backend após
alterar seu `.env`; variáveis já exportadas no terminal têm precedência.

| Variável | Local | Uso / padrão |
| --- | --- | --- |
| `OPENAI_API_KEY` | Backend | Chave obrigatória para gerar respostas |
| `OPENAI_MODEL` | Backend | Identificador explícito do modelo escolhido |
| `OPENAI_TIMEOUT_SECONDS` | Backend | Prazo total do chat; padrão `25` segundos |
| `OPENAI_MAX_OUTPUT_TOKENS` | Backend | Orçamento de geração; padrão `800` |
| `IGDB_CLIENT_ID`, `IGDB_CLIENT_SECRET` | Backend | Credenciais do aplicativo confidencial Twitch |
| `IGDB_TIMEOUT_SECONDS` | Backend | Prazo da pesquisa; padrão `5` segundos |
| `CORS_ORIGINS` | Backend | Origens autorizadas, separadas por vírgulas; padrão local |
| `RAG_ENABLED` | Backend | Habilita recuperação documental; padrão `false` |
| `RAG_INDEX_PATH` | Backend | Índice relativo a `backend/`; padrão `.data/rag-index.json` |
| `RAG_ALLOW_SYNTHETIC` | Backend | Permite documentos fictícios; padrão `false` |
| `RAG_MIN_SCORE` | Backend | Corte do ranking; padrão `0.35`, não confiança factual |
| `YOUTUBE_API_KEY` | Backend | Chave opcional para tutoriais |
| `YOUTUBE_TIMEOUT_SECONDS` | Backend | Prazo da busca; padrão `5` segundos |
| `YOUTUBE_MAX_SEARCHES_PER_DAY` | Backend | Teto local por processo/dia UTC; padrão `30` |
| `YOUTUBE_PREFERRED_CHANNEL_IDS` | Backend | IDs de canais revisados; opcional, vazio por padrão |
| `NEXT_PUBLIC_API_URL` | Frontend | Endereço público da API; padrão `http://localhost:8000` |

Variáveis `NEXT_PUBLIC_*` são públicas e incorporadas ao frontend durante o build.
Nunca coloque chaves nelas. Para outro ambiente, ajuste a URL da API antes de
`npm run build` e autorize a origem correta em `CORS_ORIGINS`.

Sem configuração IGDB, o catálogo fica indisponível. Sem YouTube, o chat continua
textual. Sem índice RAG habilitado e válido, não há recuperação documental.

## Base documental e RAG

RAG complementa o conhecimento do modelo com trechos recuperados dos documentos;
não treina o modelo nem cria uma base universal sobre todos os jogos.
O lote inicial cobre serviços e plataformas, como Steam Cloud, Steam Remote Play,
Steam Deck, Xbox Play Anywhere, DualSense e compatibilidade PlayStation.

Cada documento possui um Markdown e metadados JSON com fonte, escopo e revisão.
A construção do índice é explícita e fica fora do processamento das mensagens.

Para construir e consultar o índice **lexical**, sem chamadas de embeddings,
execute na pasta `backend/`:

```bash
uv run --locked python -m app.rag.cli build --input ../knowledge --output .data/rag-index.json
uv run --locked python -m app.rag.cli search --index .data/rag-index.json --query 'DualSense no PC por Bluetooth ou USB' --product DualSense --platform PC
```

O comando recusa sobrescrever um índice existente. Use `--force` somente quando
quiser substituí-lo. Para habilitar no chat, edite as variáveis correspondentes
no `.env` existente e reinicie o backend:

```dotenv
RAG_ENABLED=true
RAG_INDEX_PATH=.data/rag-index.json
RAG_ALLOW_SYNTHETIC=false
```

Editar documentos não atualiza o índice automaticamente: reconstrua-o e reinicie.
A busca lexical depende de coincidência de termos; embeddings são uma alternativa
opcional com envio de textos à OpenAI e possível cobrança. O chat continua usando
geração paga mesmo quando a recuperação é local. Consulte o
[guia RAG](docs/rag-usage.md) e o [formato dos documentos](knowledge/README.md).

## API

| Método | Rota | Responsabilidade |
| --- | --- | --- |
| `GET` | `/api/health` | Diagnóstico básico, sem verificar provedores |
| `POST` | `/api/chat` | Mensagem e histórico → resposta do agente |
| `GET` | `/api/games?query=Portal&limit=5` | Consulta direta à IGDB, sem geração OpenAI |

Exemplo de requisição do chat:

```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Quero um jogo cooperativo para PC.",
  "history": [],
  "include_videos": false
}
```

O retorno contém `conversation_id` e `message`, com `role`, `content`, `videos` e
`store_links`. As listas de anexos podem estar vazias; o texto depende do modelo.
O histórico enviado contém somente papel e texto, sem reenviar anexos.

Limites principais: mensagem de até 4.000 caracteres, histórico de até 50 mensagens
e saída de até 4.000 caracteres. Campos desconhecidos são rejeitados.
Erros incluem `422` (entrada inválida), `502` (provedor/saída inválida), `503`
(indisponibilidade/configuração) e `504` (timeout); o catálogo também pode retornar
`429`. O contrato completo está no [guia do backend](backend/README.md) e no Swagger.

## Testes e qualidade

Na pasta `backend/`:

```bash
uv sync --locked
uv run --locked pytest -q -W error
```

Na pasta `frontend/`:

```bash
npm ci
npm run lint
npm test
npx tsc --noEmit
npm run build
```

Os testes automatizados utilizam respostas e transportes simulados, sem consumir
créditos OpenAI ou cotas reais das integrações. Instalar dependências pode exigir
rede. Avaliar respostas reais pela interface é um procedimento separado e pode cobrar.
Não há garantia de qualidade factual apenas porque os testes passaram.

Pontos para adaptar e ampliar os testes:

- `backend/tests/`: contrato HTTP, agente, ferramentas, falhas, RAG e integrações.
- `backend/tests/evaluation/knowledge-cases.json`: perguntas e evidências esperadas do corpus.
- `backend/tests/fixtures/rag/`: documentos fictícios para testar ingestão e recuperação.
- `frontend/tests/`: envio, estado, isolamento, sessão, vídeos e links.
- `shared/trusted-store-cases.json`: casos comuns de aceitação/rejeição de URLs.
- [Avaliação do agente](docs/agent-evaluation.md): roteiro de revisão humana.

Não apresentamos contagem fixa ou selo de cobertura no README: resultados devem
ser registrados para a revisão e o ambiente efetivamente testados.

## Segurança, privacidade e custos

- Credenciais ficam no backend; arquivos `.env` são locais e ignorados pelo Git.
  Os exemplos versionados não devem conter valores reais.
- O histórico da conversa selecionada é enviado à OpenAI a cada turno. Tracing do
  SDK está desativado e a geração usa `store=False`, sem promessa de retenção zero.
- Consultas de catálogo enviam nome/filtros à IGDB. Busca YouTube exige autorização
  na interface; a ferramenta recebe termos relevantes, não o histórico inteiro.
- O player é inserido por clique e usa `youtube-nocookie.com`, sem garantia de
  ausência de coleta por terceiros. A autorização de busca reinicia desligada.
- O histórico fica no `sessionStorage` da aba: sobrevive ao recarregamento, mas
  não oferece backup ou sincronização. Fechar a aba normalmente encerra a sessão,
  sujeito aos mecanismos de restauração do navegador.
- Links de compra clicáveis exigem resultado do catálogo na requisição atual e
  correspondência à política em `shared/trusted-stores.json`, validada no backend
  e no frontend: Steam, GOG, Epic Games Store, PlayStation Store, Xbox e Nintendo.
  Outros endereços não se tornam links de compra autorizados. A política pode
  rejeitar URLs legítimas fora dos padrões aceitos e não garante ausência de riscos
  ou de redirecionamentos futuros nas lojas.
- Textos e documentos externos não são considerados instruções do sistema.
  As validações técnicas não provam que todas as afirmações do modelo são verdadeiras.
- CORS não autentica usuários. Sem proteção pública contra abuso e orçamento
  global, esta versão deve permanecer em ambiente controlado.
- Histórico, ferramentas e geração influenciam o custo. Timeouts e limites de
  tokens não equivalem a teto financeiro; chamadas interrompidas podem cobrar.

## Solução de problemas

| Sintoma | O que verificar |
| --- | --- |
| A interface não abre | Execute também `npm run dev` em `frontend/`; Uvicorn não serve a interface |
| “Não foi possível conectar ao servidor” | Backend ativo em `8000`, `NEXT_PUBLIC_API_URL` e origem em `CORS_ORIGINS` |
| Porta ocupada | Confira se já existe um servidor; evite iniciar processos duplicados |
| HTTP `503` no chat | Chave/modelo e configuração; confira também se `game_agent.md` está presente e legível |
| HTTP `502` no chat | Acesso ao modelo, saldo/limites e validade da saída; examine logs locais sem expor segredos |
| HTTP `504` | Prazo total excedido; tente novamente manualmente, sem loops de reenvio |
| Sem resultados IGDB | Credenciais Twitch, filtros e disponibilidade do catálogo; ausência não prova inexistência do jogo |
| RAG indisponível | Habilitação, caminho, construção e validade do índice; reinicie após ajustar |
| Sem vídeo ou reprodução bloqueada | Chave, autorização, cota, relevância e permissão de incorporação; nem toda resposta exige vídeo |
| Conversas não restauradas | Mesma aba/origem e disponibilidade do armazenamento; a interface informa falhas locais |

## Fluxo de desenvolvimento

```text
feature/* → pull request → develop → revisão de versão → main
```

- `main`: versões aprovadas; não recebe implementação direta.
- `develop`: base de integração das funcionalidades testadas.
- `feature/*`: tarefas pequenas, com escopo e critérios de conclusão definidos.
- Features dependentes podem usar branches empilhadas, com a dependência e a base
  do PR explícitas; depois da integração, a base deve ser revisada.
- Commits em português seguem Conventional Commits, por exemplo
  `docs(readme): documenta arquitetura e execução do MVP`.
- Antes de integrar, revise o diff, execute as verificações e atualize a documentação.
  Publicar uma branch não equivale a aprovar um PR ou realizar deploy.

O comportamento editável do agente fica em
[`backend/app/agents/game_agent.md`](backend/app/agents/game_agent.md), lido a cada
requisição. Não confunda esse arquivo com os guias explicativos em `docs/`.

## Limitações e evolução

A aplicação já reúne os fluxos locais de conversa, catálogo, recuperação e vídeos.
Ainda há decisões e validações antes de uma entrega pública:

- Avaliar recomendações e fidelidade às fontes com um conjunto independente de perguntas.
- Medir ganho do RAG frente ao modelo sem recuperação e revisar o corpus periodicamente.
- Revisar e integrar os PRs, executar a suíte completa na versão candidata e registrar a entrega.
- Adicionar proteção contra abuso, limites de custo, observabilidade e configuração de produção.
- Planejar hospedagem/HTTPS e gestão de segredos; AWS permanece uma opção futura.
- Avaliar streaming e atualização documental conforme necessidade, sem complexidade prematura.
- Implementar login e banco de conversas somente se houver requisito de histórico permanente.

Não há busca automática na web, preços em tempo real, compras, banco de conversas,
CI/CD ou infraestrutura AWS operacional nesta entrega. Busca semântica opcional
não implica que embeddings reais já tenham sido avaliados.

## Documentação complementar

| Guia | Conteúdo |
| --- | --- |
| [Backend](backend/README.md) | OpenAI, contrato HTTP, erros e operação |
| [Frontend](frontend/README.md) | Interface, sessão e execução |
| [Arquitetura](docs/architecture.md) | Responsabilidades, decisões e evolução |
| [Catálogo IGDB](docs/igdb-catalog.md) | Credenciais, consultas e limites |
| [Agente com catálogo](docs/catalog-agent.md) | Filtros e critérios de recomendação |
| [RAG operacional](docs/rag-usage.md) | Indexação, busca, configuração e segurança |
| [Projeto RAG](docs/rag.md) | Fundamentos e desenho documental |
| [Base de conhecimento](knowledge/README.md) | Formato dos documentos e metadados |
| [Lote generalista](docs/knowledge-general.md) | Fontes, critérios e avaliação do corpus |
| [Avaliação do agente](docs/agent-evaluation.md) | Cenários para revisão humana |
| [YouTube](docs/youtube-tutorials.md) | Configuração, autorização, player e limites |

Os guias técnicos registram entregas incrementais; números de testes e notas
históricas neles não substituem a validação da revisão atual.

## Autoria e licença

Projeto de Marcos Santos Peres, desenvolvido como prática de Engenharia de Computação.
Não há licença de distribuição definida neste repositório até o momento; não se
presume autorização irrestrita de uso ou redistribuição. Marcas, APIs, vídeos e
documentação de terceiros permanecem sujeitos aos termos de seus titulares.
