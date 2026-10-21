# Lote generalista do RAG

O primeiro lote real está em [knowledge/plataformas](../knowledge/plataformas/).
São sete guias independentes de títulos específicos, com sete fontes oficiais,
metadados e critérios verificáveis. O objetivo é responder condições e diferenças
entre serviços que o modelo pode confundir ou generalizar indevidamente.

## Decisões de implementação

- Pares Markdown/JSON, sem banco vetorial ou dependência nova.
- Cada guia é uma unidade curta e autossuficiente; mantém regra e exceções juntas.
  O divisor atual é suficiente para este lote: não foi alterado nem foi adicionado
  enriquecimento por LLM. Os textos cabem no limite padrão de 1.200 caracteres.
- Fonte e data ficam no JSON. Perguntas, respostas esperadas e notas editoriais
  ficam fora do conteúdo indexado, evitando contaminação da busca.
- `scope=general` usa `game=null`; documentos específicos continuam com
  `scope=game` e nome obrigatório. Versão de jogo não faz sentido em escopo geral.
- Na ferramenta e na CLI, omitir jogo seleciona apenas documentos gerais.
  `product` filtra o serviço; `platform` continua exato e opcional. Informar jogo
  seleciona apenas documentos daquele jogo, sem fallback genérico silencioso.
- A descrição da ferramenta e o prompt explicam essa distinção ao agente.
  O SDK mantém o esquema estrito com campos anuláveis, conforme a
  [documentação oficial de function calling](https://developers.openai.com/api/docs/guides/function-calling).
- Índices anteriores continuam legíveis; novos campos assumem escopo de jogo.
  Para disponibilizar o lote novo, construa um índice novo e reinicie o servidor.

## Executar sem chamadas pagas

Na pasta `backend/`:

```bash
uv run --locked pytest tests/test_knowledge_corpus.py -q
uv run --locked python -m app.rag.cli build --input ../knowledge --output .data/knowledge-general.json
uv run --locked python -m app.rag.cli search --index .data/knowledge-general.json --query 'DualSense: resposta tátil no PC por Bluetooth ou USB?' --product DualSense --platform PC
```

O comando build não sobrescreve arquivos. Para atualizar deliberadamente um índice
já existente, acrescente `--force`. Não é necessário `--allow-synthetic`, nem
`--allow-paid`, nem chave de API para a indexação e consulta lexicais.

## Usar no chatbot

No `.env` do backend, preserve suas credenciais e ajuste somente:

```dotenv
RAG_ENABLED=true
RAG_INDEX_PATH=.data/knowledge-general.json
RAG_ALLOW_SYNTHETIC=false
RAG_MIN_SCORE=0.35
```

Reinicie o backend. O frontend e a API REST permanecem iguais. A geração de
respostas pelo agente continua usando créditos OpenAI, mesmo com busca lexical.
Esta entrega não altera credenciais nem inicia chamadas reais de geração.

Experimente perguntas com contexto: diferenças entre Play Anywhere e crossplay,
uso do DualShock 4 com versões PS4/PS5, ou upload de saves PS4 para PS5.
Uma pergunta vaga como "Como transfiro meu progresso?" exige esclarecer serviço
e dispositivos; a base não permite adivinhar a situação.

## Avaliação e limites do resultado

Os [22 casos editáveis](../backend/tests/evaluation/knowledge-cases.json) incluem
14 perguntas respondíveis, cinco negativas e três situações conversacionais.
Os 19 primeiros são executados automaticamente: exigem documento correto na
primeira posição com evidência presente, ou nenhum resultado quando aplicável.
Os três casos conversacionais exigem avaliação do agente; não são apresentados
como testes de geração já aprovados. `answer_check` orienta a revisão humana.

Esse conjunto inicial é de desenvolvimento/regressão. Não é um benchmark
independente, não mede o universo de perguntas e não comprova ganho sobre o modelo
sem RAG. Os resultados com geração devem ser medidos separadamente, mantendo
modelo, contexto e configuração iguais nas duas condições e registrando fontes,
correção factual, utilidade, latência e custo. Perguntas novas devem compor uma
amostra separada antes de ajustar a busca para elas.

Validação desta entrega: 292 testes do backend passaram; os 19 casos automáticos
do corpus passaram, incluindo 14 documentos esperados na primeira posição e
cinco buscas negativas. O fluxo API → SDK → ferramenta → evidência/citação foi
verificado com provedor simulado. A CLI real construiu sete trechos a partir dos
sete documentos sem embeddings nem envio de dados externos.

A busca lexical exige palavras coincidentes e pode recuperar conteúdo parecido
sem responder à pergunta. O score não é confiança factual. O agente ainda precisa
verificar sustentação e reconhecer limites. Busca semântica continua opcional e
não foi executada com provedor real para esta entrega.

## Atualização do conteúdo

Revisão documental: 20/10/2026. Revisar mensalmente e após relatos de divergência.
Datas não são garantia de validade: não há atualização automática das fontes.
As sínteses preservam condições conhecidas, sem copiar páginas inteiras nem
reivindicar licença de redistribuição dos textos originais. Testes de hardware,
compras e manipulação de saves não foram realizados.
