# RAG local — etapa 1: ingestão de documentos

Este guia descreve o componente de ingestão. O fluxo completo agora está no
[guia de indexação, busca e uso do agente](rag-usage.md).

## Escopo implementado

Leitura de um par Markdown/JSON, validação de metadados e divisão em trechos
rastreáveis. Usa a biblioteca padrão Python e Pydantic já instalados.

Este componente NÃO implementa busca, embeddings, índice persistente, banco vetorial,
upload pela interface ou integração com o agente. Não faz requisições externas,
não usa créditos e não modifica o fluxo de chat ou as ferramentas IGDB existentes.

É preparação para o RAG, não todo o mecanismo. Os módulos adicionais de índice,
recuperação e integração estão descritos no guia completo. Não há documentos reais selecionados:
o jogo e os procedimentos dos exemplos são fictícios e isolados nos testes.

## Arquivos e responsabilidades

- `knowledge/README.md`: formato dos documentos e orientações de seleção.
- `backend/app/rag/schemas.py`: contratos `DocumentMetadata`, `KnowledgeDocument`
  e `KnowledgeChunk`, com campos extras rejeitados e marcação sintética obrigatória.
- `backend/app/rag/ingestion.py`: leitura de arquivos e divisão do texto, sem API ou IA.
- `backend/tests/fixtures/rag/cidade-aurora.md` e `.json`: par fictício para testes.
- `backend/tests/test_rag_ingestion.py`: testes isolados do leitor e dos trechos.

O arquivo de instruções `backend/app/agents/game_agent.md` define comportamento;
não é um documento da base RAG. As credenciais continuam fora desses arquivos.

## Como funciona

1. `load_document(path)` exige extensão `.md`, lê UTF-8 e busca o JSON de mesmo
   nome-base. O Pydantic valida os metadados e rejeita Markdown vazio.
2. `chunk_document(document, max_chars=1200)` identifica as seções e suas posições.
3. Cada seção é subdividida até respeitar o limite, priorizando fronteiras de
   parágrafos, depois linhas e espaços. Uma palavra maior que o limite precisa
   ser dividida; não se descarta seu restante.
4. Cada `KnowledgeChunk` preserva os metadados, `section_path`, texto e offsets.
5. `ingest_document(path, max_chars=1200)` é o atalho de leitura e divisão. Retorna
   uma lista de modelos em memória; não escreve outros arquivos.

### Tamanho, limites e preservação

O limite conta caracteres Python, não bytes nem tokens. Não representa orçamento
exato de contexto do modelo e não inclui os metadados ou títulos em `section_path`.
Pode ser alterado pelo argumento `max_chars`, que deve ser um inteiro positivo.
1.200 é um ponto inicial de experimento, não um tamanho ideal validado para busca.

O texto original fica em `KnowledgeDocument.text`, com finais de linha normalizados
para `\n` pela leitura. Os trechos removem apenas espaços em branco nas bordas;
intervalos contendo somente espaços/quebras de linha não geram trechos vazios.
Nenhum caractere não branco deve desaparecer ou mudar de ordem. O texto completo
continua no documento para inspeção, incluindo os intervalos brancos omitidos.

`start_char` é inclusivo e `end_char` exclusivo: para cada trecho,
`document.text[start_char:end_char] == chunk.text`. Os offsets se referem ao texto
normalizado, não às posições em bytes do arquivo. Trechos não se sobrepõem nesta
etapa; overlap será avaliado com a recuperação, se os resultados justificarem.

### Seções e identificadores

São reconhecidos títulos ATX com um a seis `#`, espaço e texto, com até três espaços
de indentação. A hierarquia é preservada ao entrar e sair de subseções. Uma
introdução antes do primeiro título usa `section_path` vazio. Títulos consecutivos
podem gerar trechos com apenas o cabeçalho: ele também é conteúdo do documento.

Cercas de código com crases ou tils impedem que linhas `#` internas sejam tratadas
como títulos. Não implementamos um parser Markdown completo: títulos Setext
(`===`/`---`), HTML, listas aninhadas e outras estruturas não têm tratamento semântico
especial. Seu texto é preservado. Um bloco de código longo também pode ser dividido
por tamanho; a ingestão não promete trechos individualmente renderizáveis como Markdown.

Os IDs seguem `document_id:1`, `document_id:2`, etc. São determinísticos para a
mesma entrada e configuração, mas podem mudar ao editar o texto ou o tamanho dos
trechos. Não devem ser tratados como identificadores estáveis entre revisões de um
índice futuro. A ingestão é de um documento por chamada; não varre diretórios nem
verifica IDs duplicados na coleção inteira.

## Executar e inspecionar

Não é necessário iniciar o frontend ou o backend HTTP. Na pasta `backend/`:

```bash
uv sync --locked
uv run --locked pytest tests/test_rag_ingestion.py -q -W error
```

Para ver os trechos do exemplo fictício, no mesmo diretório:

```bash
uv run --locked python -c 'from app.rag.ingestion import ingest_document; chunks = ingest_document("tests/fixtures/rag/cidade-aurora.md", max_chars=300); print("\n".join(chunk.model_dump_json(indent=2) for chunk in chunks))'
```

Altere `max_chars=300` para `1200` e compare quantos trechos foram gerados, sua
hierarquia e os limites. Esse comando lê o exemplo e imprime os resultados;
não envia informação à OpenAI nem grava um índice.

Para a suíte completa, ainda na pasta `backend/`:

```bash
uv run --locked pytest -q -W error
```

## Como participar dos testes

- Edite os arquivos fictícios de `backend/tests/fixtures/rag/` para experimentar
  títulos, subtítulos, textos longos e plataformas/versões fictícias.
- Em `test_rag_ingestion.py`, a função `metadata()` cria metadados de teste e as
  listas de `@pytest.mark.parametrize` permitem adicionar casos pontuais.
- `assert_traceability()` verifica limites, metadados, IDs únicos na saída e se
  apenas intervalos brancos ficaram fora dos spans. Um teste com offsets detecta
  perda ou alteração de conteúdo não branco, inclusive em palavras longas.
- Os testes existentes de hierarquia e conteúdo precisam acompanhar mudanças
  intencionais nas fixtures. Novos documentos e metadados devem ser fictícios
  enquanto não houver uma fonte real selecionada e revisada.

São testados arquivos ausentes, JSON inválido, campos obrigatórios/extras,
metadados inválidos, UTF-8, textos vazios, limites, parágrafos, hierarquia e cercas
de código. Esses testes não comprovam relevância de busca ou qualidade de resposta:
os testes de recuperação e integração estão em `test_rag_retrieval.py` e `test_rag_agent.py`.

## Erros e segurança

`RagIngestionError` classifica falhas de leitura e validação sem repetir o conteúdo
do arquivo ou detalhes brutos da exceção. `max_chars` inválido gera `ValueError`.
Isso é uma biblioteca local, não um endpoint: nenhum status HTTP foi adicionado.

`source_url` opcional aceita HTTPS sem credenciais. Validar sua sintaxe não comprova
que a página exista, que seu conteúdo seja confiável ou que haja permissão de uso.
O leitor não acessa essa URL. Os caminhos dos arquivos são fornecidos pelo
desenvolvedor; não existe upload nem caminho enviado por usuários do chatbot.

Ingerir um documento não comprova a veracidade de suas afirmações. No RAG futuro,
trechos serão tratados como dados externos, nunca como instruções. Não utilizar
marcação de origem ou de exemplo como substituto de revisão humana.

## Evolução após a ingestão

1. Selecionar fontes reais e perguntas de avaliação; exemplos fictícios não
   comprovam utilidade para o usuário final.
2. Comparar a busca lexical e a opção semântica já implementadas no índice JSON.
3. Escolher explicitamente modelo de embeddings e orçamento antes de chamadas reais.
4. Avaliar tamanho dos trechos, overlap e filtros com as perguntas de avaliação.
5. Avaliar a integração existente com limites, citações e validação de URLs,
   sem misturar registros/versões de jogos.

A implementação posterior foi autorizada pelo estudante. Fontes reais, envio de
material e avaliação paga não foram realizados automaticamente.
