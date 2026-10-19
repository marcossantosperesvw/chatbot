# Avaliação colaborativa da conversa do agente

## Objetivo e decisões aprovadas

Melhorar pedidos abertos por investigação gradual: uma pergunta curta por vez,
escolhida a partir do contexto, até haver informação suficiente para recomendar.
O agente deve responder diretamente quando o pedido já estiver claro e aceitar
quem prefere receber sugestões sem responder perguntas.

As regras e os exemplos estão em `backend/app/agents/game_agent.py`, na constante
`INSTRUCTIONS`. É o primeiro lugar para discutir e ajustar o comportamento.
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

Se o servidor já estiver em execução com `--reload`, confirme que recarregou após
a alteração do agente. Se estiver sem reload, reinicie-o para carregar as regras.

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

Esperado: uma pergunta que diferencie intenções, como construir cidades, bases
de sobrevivência ou criar livremente. O agente não deve escolher Fortnite nem
qualquer outro jogo antes de entender qual experiência foi pedida.

### C2 — Investigação gradual

Na mesma conversa de C1, responda `Construir cidades.`. Depois, responda à próxima
pergunta com uma preferência sua e continue até receber sugestões.

Esperado: uma pergunta por resposta enquanto faltar informação relevante, sem
repetir o tipo de construção já informado. Deve chegar a recomendações usando
as respostas, sem exigir uma lista fixa de preferências. Registre a sequência
completa para discutirmos se fez perguntas demais ou parou cedo demais.

### C3 — Pedido já específico

Em nova conversa, envie:
`Quero construir cidades no PC, sozinho, com foco em gestão e sem combate.`

Esperado: recomendações diretas, com justificativa ligada ao pedido. Não deve
perguntar novamente plataforma, modo ou preferência sobre combate, nem exigir
orçamento ou dificuldade apenas para completar um formulário.

### C4 — Correção de uma preferência

Em nova conversa, envie `Quero construir uma base e enfrentar inimigos no PC.`.
Depois envie `Na verdade, não quero combate. Prefiro construir com tranquilidade.`.

Esperado: as próximas perguntas ou recomendações respeitam a correção. Não deve
tratar combate como preferência ainda válida nem repetir a pergunta sobre plataforma.

### C5 — Sugestões sem investigação

Em nova conversa, envie:
`Quero um jogo de construção. Não quero responder perguntas agora; me dê três sugestões.`

Esperado: sugestões imediatas cobrindo interpretações diferentes, com suposições
identificadas. Não deve insistir em uma pergunta antes de ajudar.

### C6 — Ausência de preferência

Em nova conversa, envie `Quero um jogo para PC.`. Responda à pergunta do agente
com `Tanto faz esse aspecto, pode sugerir algumas opções variadas.`.

Esperado: aceitar a ausência de preferência e recomendar opções, usando PC como
contexto conhecido. Não deve insistir para obter uma resposta mais específica.

### C7 — Pergunta factual clara

Em nova conversa, envie: `Qual é a diferença entre modo criativo e sobrevivência no Minecraft?`

Esperado: explicação direta sobre a diferença. Não deve perguntar orçamento,
plataforma ou estilo favorito antes de explicar.

### C8 — Conversas independentes

Na conversa A, envie `Quero construir cidades no PC, sozinho, sem combate.` e
aguarde a resposta. Crie a conversa B e envie `Quero um jogo de construção.`.

Esperado: B começa investigando o pedido, sem atribuir ao usuário as preferências
de A. Ao voltar para A e enviar `Mais opções nesse estilo, por favor.`, deve usar
o histórico de A sem perguntar outra vez as preferências que já conhece.

## Critérios de revisão

Avalie cada resposta por intenção, sem exigir uma frase literal:

- Pergunta quando a informação faltante realmente muda a recomendação.
- Explora um aspecto por vez, com alternativas compreensíveis quando úteis.
- Usa o histórico e respeita correções, sem inventar preferências.
- Para de investigar quando já consegue ajudar ou quando o usuário pede sugestões.
- Explica por que as recomendações atendem ao pedido; admite incertezas.
- Mantém as limitações atuais: não afirma consultar a web e não inventa URLs,
  preços, fontes ou disponibilidade. Lojas, vídeos e RAG serão tarefas posteriores.

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
