# Avaliação colaborativa da conversa do agente

## Objetivo e decisões aprovadas

Melhorar pedidos abertos por investigação gradual: uma ou duas perguntas curtas,
escolhidas a partir do contexto, até haver informação suficiente para consultar
candidatos. Recomendações exigem evidência para os requisitos essenciais.
O agente não deve prolongar a investigação se o pedido já estiver claro, mas um
pedido de sugestões imediatas não autoriza inventar preferências, evidências ou
relaxar critérios sem consentimento.

As regras e os exemplos estão em
[`backend/app/agents/game_agent.md`](../backend/app/agents/game_agent.md).
Esse é o arquivo para discutir e ajustar o comportamento. O módulo
`backend/app/agents/game_agent.py` apenas carrega e valida o texto, configura o
agente e fornece o conteúdo em `Agent(instructions=...)`. Este roteiro não é
carregado como instruções do chatbot.
Não há classificador adicional, formulário fixo, novas dependências ou alteração
no contrato HTTP. O histórico já enviado pela aplicação sustenta a conversa.

Esta é uma avaliação de comportamento, não uma base RAG nem um dataset de jogos.
As respostas abaixo são referências de intenção; a redação e os jogos podem variar.

## Como participar

1. Revise os exemplos e proponha uma resposta que você gostaria de receber.
2. Execute o cenário na interface e anote a resposta real, mesmo quando ela falhar.
3. Compare a resposta com os critérios, explicando o que ficou útil ou incômodo.
4. Ajustamos uma regra ou exemplo por vez e repetimos os cenários afetados.

Não basta inserir uma frase desejada e conferir se ela aparece no arquivo: isso
não demonstra que o modelo segue a orientação. Os testes com HTTP falso continuam
verificando a integração; a avaliação abaixo observa respostas reais do modelo.
Não colocamos respostas prontas no código para fingir uma investigação.

## Preparação

O modelo e a chave devem estar configurados no ambiente local do backend. Anote
somente o ID do modelo e os limites de geração usados, nunca a chave.

Em um terminal:

```bash
cd /home/marcos/chatbot/backend
uv run --locked uvicorn app.main:app --reload
```

Ao editar somente `game_agent.md`, salve em UTF-8: o backend relê o arquivo a cada
nova requisição, mesmo sem `--reload`. Uma requisição em andamento mantém o texto
que já recebeu. Alterações no código Python exigem reload ou reinício.
Se o Markdown estiver ausente, vazio ou ilegível, o chat retorna HTTP 503 sem
chamar o modelo. Não coloque credenciais ou notas privadas nele: todo o conteúdo
é enviado como instruções. Os limites de ferramentas e a validação de URLs
continuam no código; editar o prompt não adiciona funcionalidades.

Em outro terminal, caso o frontend ainda não esteja em execução:

```bash
cd /home/marcos/chatbot/frontend
npm run dev
```

Abra <http://localhost:3000> e crie uma nova conversa para cada cenário. Dentro de
um cenário, mantenha a mesma conversa para testar o histórico. Chamadas reais
usam seus créditos; comece por uma execução de cada cenário e repita falhas para
investigar variação. Nenhuma chamada paga é executada por este roteiro ou pelos
testes automatizados sem uma ação sua.

## Cenários iniciais

### C1 — Construção sem contexto

Envie: `Quero um jogo de construção.`

Esperado: uma ou duas perguntas curtas que diferenciem intenções, como construir
cidades, bases de sobrevivência ou criar livremente, e esclareçam a plataforma
quando necessário. O agente não deve escolher Fortnite nem
qualquer outro jogo antes de entender qual experiência foi pedida.

### C2 — Investigação gradual

Na mesma conversa de C1, responda `Construir cidades.`. Depois, responda à próxima
pergunta com uma preferência sua e continue até receber sugestões.

Esperado: uma ou duas perguntas curtas enquanto faltar informação relevante, sem
repetir o tipo de construção já informado. Deve chegar a recomendações usando
as respostas, sem exigir uma lista fixa de preferências. Registre a sequência
completa para discutirmos se fez perguntas demais ou parou cedo demais.

### C3 — Pedido já específico

Em nova conversa, envie:
`Quero construir cidades no PC, sozinho, com foco em gestão e sem combate.`

Esperado: consultar candidatos sem repetir plataforma, modo ou preferência sobre
combate, nem exigir orçamento ou dificuldade apenas para completar um formulário.
Recomendar somente se houver evidência suficiente, no registro do próprio jogo,
para os requisitos essenciais. Se "sem combate" não puder ser confirmado, explicar
a limitação e perguntar como prosseguir. A ausência de combate no resumo não
comprova que o jogo não tem combate; não oferecer uma aproximação sem autorização.

### C4 — Correção de uma preferência

Em nova conversa, envie `Quero construir uma base e enfrentar inimigos no PC.`.
Depois envie `Na verdade, não quero combate. Prefiro construir com tranquilidade.`.

Esperado: as próximas perguntas ou recomendações respeitam a correção. Não deve
tratar combate como preferência ainda válida nem repetir a pergunta sobre plataforma.

### C5 — Sugestões sem investigação

Em nova conversa, envie:
`Quero um jogo de construção. Não quero responder perguntas agora; me dê três sugestões.`

Esperado: não transformar o pedido em um questionário obrigatório, mas também não
inventar plataforma ou interpretar construção arbitrariamente. Se faltarem dados
para uma consulta útil, explicar a limitação e pedir apenas o esclarecimento que
realmente muda a seleção. Se puder consultar candidatos sem inventar preferências,
recomendar somente os retornados com evidência suficiente; não completar três
sugestões com jogos não confirmados só para atingir a quantidade solicitada.

### C6 — Ausência de preferência

Em nova conversa, envie `Quero um jogo para PC.`. Responda à pergunta do agente
com `Tanto faz esse aspecto, pode sugerir algumas opções variadas.`.

Esperado: aceitar a ausência de preferência e consultar opções usando PC como
contexto conhecido, sem inventar gênero ou modo. Recomendar candidatos confirmados
pelo catálogo; explicar falhas ou falta de resultados sem substituí-los por jogos
de memória. Não insistir para obter uma preferência que o usuário não possui.

### C7 — Pergunta factual clara

Em nova conversa, envie: `Qual é a diferença entre modo criativo e sobrevivência no Minecraft?`

Esperado: explicação direta sobre a diferença. Não deve perguntar orçamento,
plataforma ou estilo favorito antes de explicar. Se usar conhecimento geral,
identificar essa origem e não atribuir a explicação a uma consulta IGDB inexistente.

### C8 — Conversas independentes

Na conversa A, envie `Quero construir cidades no PC, sozinho, sem combate.` e
aguarde a resposta. Crie a conversa B e envie `Quero um jogo de construção.`.

Esperado: B começa investigando o pedido, sem atribuir ao usuário as preferências
de A. Ao voltar para A e enviar `Mais opções nesse estilo, por favor.`, deve usar
o histórico de A sem perguntar outra vez as preferências que já conhece.

## Critérios de revisão

Avalie cada resposta por intenção, sem exigir uma frase literal:

- Pergunta quando a informação faltante realmente muda a recomendação.
- Faz uma ou duas perguntas curtas, com alternativas compreensíveis quando úteis.
- Usa o histórico e respeita correções, sem inventar preferências.
- Para de investigar quando já consegue consultar candidatos, sem preencher um
  questionário fixo; pedir sugestões não dispensa confirmar requisitos essenciais.
- Recomenda somente jogos consultados com evidência suficiente, mantém cada fato
  associado ao próprio registro e admite incertezas. Só flexibiliza critérios
  essenciais se o usuário aceitar.
- Mantém as limitações atuais: não afirma consultar a web e não inventa URLs,
  preços, fontes ou disponibilidade. Links de lojas podem ser enviados quando
  retornados pela ferramenta na requisição atual; não comprovam estoque ou preço.
  Cards de lojas, vídeos e RAG serão tarefas posteriores.
- Usa texto simples, sem asteriscos de negrito ou links Markdown na resposta.

Marque `Atendeu`, `Parcial` ou `Não atendeu` e registre a evidência. Um sucesso
isolado não garante consistência, e um teste com transporte falso não substitui
a avaliação do modelo. Antes de aprovar a integração, execute os oito cenários
e discuta os resultados parciais ou negativos; repita os afetados após ajustes.

## Registro da avaliação

Estado inicial: cenários preparados, **avaliação real pendente**. Não há resultados
do modelo registrados nesta entrega.

- Data:
- Commit ou branch avaliada:
- ID exato do modelo:
- Limite de saída e timeout:

| Cenário | Resultado | Resposta observada e motivo da avaliação |
| --- | --- | --- |
| C1 | Pendente | |
| C2 | Pendente | |
| C3 | Pendente | |
| C4 | Pendente | |
| C5 | Pendente | |
| C6 | Pendente | |
| C7 | Pendente | |
| C8 | Pendente | |

Para cada falha, guarde a sequência de mensagens e descreva o comportamento
desejado. Dados sintéticos e exemplos de jogos bastam para colaborar; mantenha
credenciais fora desse registro. A melhoria seguinte pode ser ampliar os cenários
ou automatizar a avaliação quando houver volume que justifique isso.

Referência: [engenharia de prompts da OpenAI](https://developers.openai.com/api/docs/guides/prompt-engineering).
