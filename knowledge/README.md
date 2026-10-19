# Base documental do RAG

Esta pasta é reservada para documentos reais selecionados e com permissão de uso.
Ela ainda não contém uma base de conhecimento nem é consultada pelo chatbot.
Não coloque as instruções do agente aqui: elas continuam em
[`game_agent.md`](../backend/app/agents/game_agent.md).

## Formato aprovado

Cada documento usa dois arquivos no mesmo diretório e com o mesmo nome-base:

```text
guia-exemplo.md
guia-exemplo.json
```

- Markdown: conteúdo em UTF-8, com títulos ATX (`#`, `##`, `###` etc.).
- JSON: metadados validados pelo Pydantic, sem campos desconhecidos.
- Não é necessário instalar um leitor YAML nem outro pacote para ingestão.

Exemplo de metadados **fictícios**, somente para explicar o formato:

```json
{
  "document_id": "exemplo-ficticio",
  "title": "Exemplo de documento",
  "game": "Jogo fictício",
  "platforms": [],
  "game_version": null,
  "source": "Exemplo sintético, não utilizar como informação sobre jogos reais.",
  "source_url": null,
  "reviewed_at": "2026-10-19",
  "synthetic": true
}
```

| Campo | Regra |
| --- | --- |
| `document_id` | Obrigatório; 1–80 caracteres, primeiro letra minúscula ou número, demais também permitem `_` e `-` |
| `title` | Título não vazio do documento |
| `game` | Nome não vazio do jogo; não prova correspondência com um registro IGDB |
| `platforms` | Lista opcional de nomes não vazios; vazia significa não informada, não "todas" |
| `game_version` | Versão opcional; `null` significa não informada, não "qualquer versão" |
| `source` | Descrição obrigatória da origem; registrar autoria e condições de uso conhecidas |
| `source_url` | Opcional; URL HTTPS sem credenciais, ou `null`; não é consultada automaticamente |
| `reviewed_at` | Data obrigatória da revisão, no formato `AAAA-MM-DD` |
| `synthetic` | Booleano obrigatório: `true` para exemplo fictício, `false` para conteúdo real revisado |

Não invente fonte, plataforma, versão ou data de revisão. Use os campos opcionais
quando a informação não existir. Descrever a origem ou usar `synthetic: false`
não comprova precisão, atualidade ou autorização de uso: isso depende de revisão humana.

## Antes de incluir um documento real

1. Defina quais perguntas ele poderá responder.
2. Verifique autoria e condições de uso; não copie páginas inteiras indiscriminadamente.
3. Identifique jogo, plataforma e versão, quando aplicáveis.
4. Revise a correspondência entre o conteúdo e os metadados.
5. Escolha um `document_id` único na base, mantenha o par Markdown/JSON e registre
   perguntas de avaliação. A ingestão atual de um único documento não verifica
   duplicidade de IDs entre arquivos diferentes.

Os exemplos de testes ficam exclusivamente em `backend/tests/fixtures/rag/`.
Não mova esses exemplos para uma futura base de produção nem os apresente como
fatos sobre jogos. `synthetic` identifica a natureza do conteúdo; ainda não existe
um mecanismo de publicação, recuperação ou filtro de produção.

Veja o [guia da primeira etapa do RAG](../docs/rag.md) para executar e inspecionar a ingestão.
