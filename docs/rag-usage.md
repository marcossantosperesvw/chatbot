# RAG local — indexação, busca e integração com o agente

## O que está implementado

O fluxo completo do MVP é: documentos Markdown/JSON → ingestão → índice JSON
versionado → busca local → ferramenta `search_knowledge` → resposta do agente
com indicação de fontes. A IGDB permanece separada para metadados e lojas.

O índice é local. Há dois modos:

- **Lexical:** ranking BM25 simples, sem dependências adicionais, embeddings ou
  cobrança na indexação/busca. Termos precisam coincidir; não entende sinônimos,
  flexões ou relações semânticas automaticamente. Normaliza acentos/caixa e ignora
  algumas palavras comuns. É uma baseline educacional, não um motor de busca completo.
- **Semântico:** embeddings gerados pela OpenAI e comparação local por cosseno.
  Documentos e perguntas são enviados à API de embeddings; portanto NÃO é offline
  nem tem garantia de retenção zero. Indexação exige `--allow-paid` e modelo explícito.
  O chat habilitado com índice semântico gera embeddings de consultas automaticamente.

RAG não significa necessariamente busca vetorial: a versão lexical também recupera
documentos e fornece esse contexto à geração. Não adicionamos banco vetorial,
LangChain, microsserviços ou filas. Para até 5.000 trechos, um snapshot em memória
e busca linear é um ponto inicial simples; desempenho e relevância devem ser medidos
antes de aumentar esse limite ou migrar para outra infraestrutura.

**Ainda não temos corpus real.** O código pode ser testado integralmente com
exemplos fictícios, mas isso não comprova qualidade de respostas sobre jogos reais.
Por padrão `RAG_ENABLED=false`, e documentos sintéticos são bloqueados na construção
e no carregamento. Nenhum arquivo foi enviado à OpenAI para testar esta entrega.

## Organização

- `app/rag/ingestion.py` e `schemas.py`: preparo e contratos dos documentos.
- `app/rag/index.py`: construção, revisão por hash, validação e persistência atômica.
- `app/rag/retrieval.py`: filtros por metadados, BM25 e ranking por cosseno.
- `app/rag/embeddings.py`: lotes limitados, validação de vetores e integração opcional.
- `app/rag/config.py`: configuração desativada por padrão, independente da IA/IGDB.
- `app/rag/cli.py`: comandos de construção e inspeção, fora das requisições de chat.
- `app/tools/knowledge.py`: fronteira tipada entre o modelo e os trechos, com quotas.
- `app/tools/catalog.py`: contexto local compartilhado das ferramentas; não é memória global.

O carregador do índice roda no ciclo de vida FastAPI, uma vez por processo. Cada
requisição cria seu contador e permissões de fontes/URLs. O histórico continua
no `sessionStorage` e não é indexado. Nenhum endpoint de upload foi criado.

## 1. Testar sem gastar créditos

Na raiz do projeto:

```bash
cd backend
uv sync --locked
uv run --locked pytest -q -W error
```

Para executar apenas o RAG:

```bash
uv run --locked pytest tests/test_rag_ingestion.py tests/test_rag_retrieval.py tests/test_rag_agent.py -q -W error
```

Esses testes usam documentos fictícios e transportes HTTP simulados, inclusive
para o SDK e embeddings. Não chamam serviços reais. Os dados e asserções editáveis
de recuperação ficam em `tests/fixtures/rag/retrieval-cases.json`; eles verificam
o primeiro trecho esperado ou ausência de evidência. Não avaliam a redação do modelo.

## 2. Criar e consultar um índice lexical de demonstração

Ainda na pasta `backend/`:

```bash
uv run --locked python -m app.rag.cli build --input tests/fixtures/rag --output .data/rag-demo.json --allow-synthetic
uv run --locked python -m app.rag.cli search --index .data/rag-demo.json --game 'Cidade Aurora — jogo fictício' --query 'bairros ruas' --allow-synthetic
```

O jogo Cidade Aurora é inventado para testes. A construção não sobrescreve um
índice existente: para reconstruí-lo, acrescente `--force` conscientemente. A
troca do arquivo é atômica, preservando o índice anterior se houver falha antes
da substituição. Não é um histórico de versões: mantenha backup quando necessário.
`.data/` é ignorada pelo Git; nela há texto e vetores, não somente IDs.

Resultados incluem metadados, seção, texto, score e posições. Score é uma medida
de ranking, não uma probabilidade de verdade ou garantia de resposta correta.
O valor inicial de corte é 0,35; ajuste `--min-score` em experimentos e avalie
perguntas sem resposta. Não existe um limiar universal validado para qualquer base.

## 3. Habilitar no chat — demonstração opcional, com geração paga

Edite apenas estas variáveis no `.env` existente do backend, sem substituir suas
credenciais ou os demais valores:

```dotenv
RAG_ENABLED=true
RAG_INDEX_PATH=.data/rag-demo.json
RAG_ALLOW_SYNTHETIC=true
RAG_MIN_SCORE=0.35
```

Reinicie o backend, pois configuração e índice são snapshots do processo:

```bash
uv run --locked uvicorn app.main:app --reload
```

Mantenha o frontend rodando como antes (`npm run dev`, na pasta `frontend/`). Em
uma conversa nova, experimente: "Na demonstração do jogo fictício Cidade Aurora —
jogo fictício, como organizar bairros e ruas?". O nome do jogo nos metadados é
`Cidade Aurora — jogo fictício`; o filtro de nome é exato após normalizar acentos,
caixa e espaços. Uma variação no nome pode não recuperar resultados.

O agente deve explicar que é conteúdo fictício e citar o trecho, por exemplo
`[RAG:cidade-aurora-teste:2]`. O frontend continua exibindo texto simples, não cards
ou uma página de documentos. Não é necessário alterar o contrato HTTP.

A geração no chat usa seus créditos OpenAI, mesmo com índice lexical. No modo
semântico, há também embeddings das consultas. Para sair da demonstração, mude
`RAG_ALLOW_SYNTHETIC=false`, use um índice real revisado ou desative o RAG e reinicie.

## 4. Usar documentos reais

Siga o formato de [`knowledge/README.md`](../knowledge/README.md). Selecione material
próprio ou com permissão de uso, revise fonte, plataforma, versão e data. Marcar
`synthetic=false` NÃO comprova veracidade ou autorização de uso.

Com pares Markdown/JSON reais na pasta `knowledge/`, na pasta `backend/`:

```bash
uv run --locked python -m app.rag.cli build --input ../knowledge --output .data/rag-index.json
```

O comando ignora arquivos chamados `README.md` e falha se os demais Markdown não
tiverem metadados válidos. IDs de documentos devem ser únicos em toda a base.
Não há crawling, download automático ou ingestão do histórico. O diretório pode
conter subpastas; symlinks de documentos e caminhos fora da base são rejeitados.
Não salve o índice dentro do diretório do corpus.

Configure `RAG_INDEX_PATH=.data/rag-index.json` e mantenha
`RAG_ALLOW_SYNTHETIC=false`. Reinicie para carregar. Uma alteração no corpus NÃO
atualiza o índice automaticamente: reconstrua com `--force` e reinicie. Índices
guardam hashes do conteúdo/metadados para comparar revisões, mas não observam os
arquivos nem verificam frescor durante cada consulta.

## 5. Busca semântica opcional

Escolha um modelo de **embeddings**, não o `OPENAI_MODEL` de geração. Não há escolha
implícita de modelo. Consulte a [documentação de embeddings](https://developers.openai.com/api/docs/guides/embeddings)
e confirme acesso, custos e adequação ao idioma/corpus.

O comando abaixo é ilustrativo: substitua `ID_DO_MODELO_DE_EMBEDDINGS`. Ele envia
o texto dos trechos à OpenAI e pode cobrar. Só execute após selecionar fontes
com permissão de envio e conferir orçamento/configuração da chave.

```bash
uv run --locked python -m app.rag.cli build --input ../knowledge --output .data/rag-semantic.json --mode semantic --embedding-model ID_DO_MODELO_DE_EMBEDDINGS --allow-paid
```

Para consultar esse índice pelo terminal, acrescente `--allow-paid`:

```bash
uv run --locked python -m app.rag.cli search --index .data/rag-semantic.json --game 'NOME_EXATO_DO_JOGO' --query 'SUA_PERGUNTA' --allow-paid
```

Use `RAG_INDEX_PATH=.data/rag-semantic.json` para habilitar esse modo no chat.
Modelo e dimensões são registrados no índice; a consulta usa o mesmo modelo e
rejeita vetores incompatíveis. Trocar o modelo exige reconstrução. Lotes de até
32 trechos limitam cada chamada de indexação; isso não é um teto financeiro total.
Não há retries automáticos nem cache de embeddings de perguntas. O comando
recusa sobrescrever um índice sem `--force` antes de gerar novos embeddings.

## Regras de recuperação e proteção

- Nome do jogo é obrigatório para não misturar documentos arbitrariamente.
- Plataforma e versão, quando informadas, exigem correspondência nos metadados.
  Valores desconhecidos não confirmam requisitos. Não há aliases automáticos
  de PS5/PlayStation 5 ou busca aproximada de nomes; padronize o corpus e os testes.
- Até três trechos por consulta e duas consultas RAG por mensagem. Até duas
  consultas IGDB continuam separadas. Com índice ativo, o SDK permite até cinco
  rodadas totais do modelo; sem ele, mantém três. O timeout total continua até 25s.
- O índice admite até 5.000 trechos, 2.000 caracteres por trecho e 50 MB no arquivo.
  Limites de ingestão: 1 MB por Markdown e 100 KB por JSON. São limites do MVP,
  não números validados por teste de carga ou garantias de capacidade.
- URLs de fonte só são permitidas se vierem dos metadados dos trechos entregues
  nesta requisição. Links soltos no corpo do documento não são autorizados.
- Marcadores no formato `[RAG:...]` não entregues nesta requisição geram HTTP 502;
  o frontend preserva o rascunho. Marcadores do histórico não são autorizações.
- A exigência de citar evidências usadas, o aviso de ficção e a resistência a
  instruções maliciosas são regras de prompt, não garantias semânticas. O código
  valida marcadores fornecidos, mas não prova que cada afirmação é sustentada,
  não obriga citações se o modelo omiti-las e não detecta todo formato informal de fonte.
- Não há consulta a preços/estoque. Não transfira informação entre jogos, versões
  ou plataformas. RAG não substitui a consulta IGDB para recomendações e lojas.

Se o índice estiver ausente, corrompido, com versão incompatível, com dados sintéticos
bloqueados ou com configuração inválida, o RAG fica indisponível e registra aviso
seguro. A API e a IGDB continuam operando; o modelo recebe `unavailable` ao tentar
consultar a base. `/api/health` não testa a qualidade da base nem o provedor.

## Avaliação e próximos passos

Comece medindo se o trecho certo aparece nas primeiras posições e se perguntas
sem resposta retornam vazio. Compare lexical e semântico no mesmo conjunto de
perguntas, avaliando filtros de jogo/plataforma/versão. Depois avalie o texto final:
fidelidade, uso das fontes, limites e latência. Os testes simulados comprovam o
encadeamento técnico, não relevância de embeddings reais ou qualidade editorial.

Ainda faltam fontes reais e avaliação com o modelo escolhido pelo estudante.
Não enviamos material nem fizemos chamadas pagas durante o desenvolvimento.
Possíveis evoluções: overlap calibrado, busca híbrida, reranking, IDs estáveis entre
revisões, atualização incremental, fontes estruturadas na interface e banco vetorial
somente quando houver necessidade medida. Não há AWS, login ou vídeos nesta entrega.
