# Base documental do RAG

Esta pasta contém o primeiro lote real de orientações gerais sobre jogos,
plataformas e serviços. São sínteses autorais de fontes oficiais, consultadas em
19–20/10/2026 e revisadas documentalmente em 20/10/2026. Não foram executados 
procedimentos nos dispositivos nem testados jogos individuais.
O chatbot consulta um índice construído a partir dos documentos, se o RAG estiver
habilitado; não lê esta pasta a cada mensagem. Este README é excluído da indexação.
Não coloque as instruções do agente aqui: elas continuam em
[`game_agent.md`](../backend/app/agents/game_agent.md).

## Lote inicial e finalidade

| Documento | Decisão que ajuda a tomar |
| --- | --- |
| [Steam Cloud](plataformas/steam-cloud-conflitos.md) | Investigar progresso divergente entre dispositivos sem escolher uma cópia arbitrariamente |
| [Xbox Play Anywhere](plataformas/xbox-play-anywhere.md) | Distinguir compra elegível, progresso compartilhado e multiplayer entre plataformas |
| [Steam Remote Play](plataformas/steam-remote-play.md) | Diferenciar transmissão do PC e multiplayer local remoto |
| [Steam Deck](plataformas/steam-deck-compatibilidade.md) | Interpretar avaliações de compatibilidade sem certificar um título por suposição |
| [DualSense](plataformas/dualsense-dispositivos.md) | Distinguir conexão do controle de suporte a seus recursos |
| [Retrocompatibilidade PS5](plataformas/ps5-retrocompatibilidade.md) | Separar versão, disco, licença e controle compatível |
| [Nuvem PlayStation](plataformas/playstation-nuvem.md) | Distinguir sincronização e download de saves entre gerações |

O corpus não contém listas de jogos compatíveis, preços atuais, rankings,
presets profissionais ou instruções de gameplay de um título específico.
Cada guia tem uma única unidade curta de conteúdo, com condições e limitações
juntas, abaixo do limite padrão de 1.200 caracteres. Fontes ficam nos metadados
e são devolvidas pela ferramenta. Perguntas e critérios de avaliação ficam
[fora do corpus](../backend/tests/evaluation/knowledge-cases.json).

Os antigos `docs/rag-drafts/` são histórico editorial e não integram este lote.
Para construir e ativar, consulte o [guia do lote generalista](../docs/knowledge-general.md).

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
| `scope` | `general` para orientações gerais; `game` para evidências de um jogo. Padrão `game` para compatibilidade com documentos anteriores |
| `game` | Obrigatório e não vazio em `scope=game`; ausente ou `null` em `scope=general` |
| `products` | Lista de serviços/produtos: Steam, Steam Deck, Xbox, PlayStation, DualSense; vazia não confirma um produto |
| `platforms` | Lista opcional de nomes não vazios; vazia significa não informada, não "todas" |
| `game_version` | Versão opcional de jogo; deve ser `null` em documentos gerais |
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
3. Identifique escopo, serviço/produto, jogo, plataforma e versão, quando aplicáveis.
4. Revise a correspondência entre o conteúdo e os metadados.
5. Escolha um `document_id` único na base, mantenha o par Markdown/JSON e registre
   perguntas de avaliação fora desta pasta. A ingestão atual de um único documento não verifica
   duplicidade de IDs; a construção da coleção agora rejeita IDs duplicados.

Os exemplos de testes ficam exclusivamente em `backend/tests/fixtures/rag/`.
Não mova esses exemplos para uma futura base de produção nem os apresente como
fatos sobre jogos. `synthetic` identifica a natureza do conteúdo. A construção e
o carregamento do índice bloqueiam exemplos fictícios por padrão; demonstrações
exigem permissões explícitas no comando e na configuração do backend.

Veja o [guia da primeira etapa do RAG](../docs/rag.md) para executar e inspecionar a ingestão.
Para indexar, pesquisar e conectar ao chat, use o [guia completo](../docs/rag-usage.md).

## Manutenção

Revise as fontes a cada 30 dias ou quando um usuário relatar divergência.
Registre `reviewed_at` somente após conferir a fonte; esse campo não é atualizado
automaticamente e não representa a data de publicação do fornecedor.
Após alterar um guia, revise os casos relacionados, execute os testes,
reconstrua o índice e reinicie o backend. Preserve o escopo das condições:
uma orientação de serviço não confirma a disponibilidade em todos os títulos.
