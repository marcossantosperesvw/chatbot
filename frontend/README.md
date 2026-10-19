# Interface do Chat Jogos

Frontend em Next.js, React, TypeScript e Tailwind CSS. A interface conversa
diretamente com a API FastAPI por HTTP/JSON, usando `POST /api/chat`.

## Executar localmente

Na pasta `frontend/`, instale as dependências com `npm ci`. Crie seu arquivo
local de configuração a partir de `.env.example` e defina, se necessário:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Em um terminal, execute o backend a partir da pasta `backend/`:

```bash
uv run --locked uvicorn app.main:app --reload
```

Em outro terminal, na pasta `frontend/`:

```bash
npm run dev
```

Abra <http://localhost:3000>. O backend deve permitir essa origem em
`CORS_ORIGINS`. `localhost:3000` e `127.0.0.1:3000` são permitidos pela
configuração padrão de desenvolvimento.

`NEXT_PUBLIC_API_URL` é uma URL pública incorporada durante o build. Ela não
deve conter credenciais. Chaves da OpenAI pertencem exclusivamente ao backend.

## Funcionalidades desta etapa

- Várias conversas salvas na sessão da aba, com mensagens e rascunhos separados.
- Menu lateral com títulos automáticos, seleção ativa e conversas mais recentes primeiro.
- Envio pelo botão ou por Enter; Shift+Enter insere uma quebra de linha.
- Sugestões iniciais que preenchem o campo sem enviar automaticamente.
- Indicação de carregamento e bloqueio de envios simultâneos.
- Erros em português, preservando o rascunho e as mensagens anteriores.
- Nova conversa sem apagar as anteriores; recuperação pelo menu lateral.
- Navegação entre conversas enquanto uma resposta está sendo preparada.
- Menu recolhível em telas pequenas, acessível pelo botão "Conversas".
- Layout responsivo, rótulos acessíveis, foco visível e movimento reduzido.

O backend usa o OpenAI Agents SDK e considera o histórico da conversa selecionada.
Configure chave e modelo conforme o [guia do backend](../backend/README.md).
As conversas são recuperadas ao atualizar
a página; fechar a aba normalmente encerra a sessão de armazenamento.

## Persistência da sessão

O `sessionStorage` guarda o histórico na chave `chat-jogos:session:v1`, por origem
e por aba. Use o mesmo endereço ao voltar: `localhost` e `127.0.0.1` são origens
diferentes. Não há sincronização entre dispositivos nem compartilhamento ao vivo
entre abas. Alguns navegadores podem copiar ou restaurar uma sessão ao duplicar
ou reabrir uma aba; este recurso não é uma garantia de histórico permanente.

O documento salvo tem versão, lista de conversas e identificador da selecionada.
Cada conversa tem UUID, título, mensagens, rascunho e datas de criação/atualização.
O título é derivado da primeira mensagem enviada, com até 60 caracteres Unicode.
As alterações são salvas após as atualizações do estado, inclusive rascunhos.

Os dados são carregados somente após a montagem no navegador. Até a recuperação
terminar, o formulário permanece bloqueado. Isso evita sobrescrever o histórico
com um estado inicial vazio e mantém a renderização inicial consistente no Next.js.

O conteúdo recuperado é validado: versão, identificadores, papéis de mensagens,
datas e conversa ativa. Dados inválidos ou de versão desconhecida são preservados
na chave original; a interface avisa e continua somente em memória. Quando o
armazenamento está bloqueado ou sem espaço, um aviso informa que alterações
podem ser perdidas ao recarregar. Nenhuma outra chave do navegador é removida.

Este armazenamento é local ao navegador, sem conta ou banco no backend. As
mensagens são enviadas à API ao solicitar uma resposta, como nas etapas anteriores.

## Organização

| Local | Responsabilidade |
| --- | --- |
| `src/app/page.tsx` | Compor a página com o componente de chat |
| `src/components/chat/` | Apresentar mensagens, formulário e estados da interface |
| `src/hooks/use-chat.ts` | Coordenar sessão, chamadas HTTP e persistência no navegador |
| `src/lib/api.ts` | Fazer chamadas HTTP e validar respostas em tempo de execução |
| `src/lib/chat.ts` | Preparar requisições e verificar limites do contrato |
| `src/lib/conversations.ts` | Atualizar conversas por identificador e tratar respostas sem misturar históricos |
| `src/lib/conversation-storage.ts` | Validar, recuperar e salvar o documento da sessão |
| `src/types/chat.ts` | Definir tipos TypeScript correspondentes ao contrato HTTP |
| `tests/` | Testar preparação do histórico e comunicação HTTP com respostas simuladas |

O identificador UUID é criado junto com cada conversa e mantido após recarregar
a página. Cada requisição inclui somente as mensagens anteriores da conversa em
`history`; a mensagem atual aparece uma única vez em `message`. IDs locais da
interface não são enviados dentro das mensagens.

Só um envio é executado por vez, mas é possível criar e selecionar conversas
durante a espera. Em outra conversa, o campo continua editável e somente o envio
fica bloqueado. Respostas e erros são associados à conversa que originou o envio;
chegadas tardias não alteram a seleção ou os rascunhos de outras conversas.

A mensagem do usuário aparece enquanto aguarda, mas só entra no histórico
persistido junto com uma resposta bem-sucedida. O rascunho original permanece
salvo até esse momento. Uma recarga durante o envio recupera o rascunho e as
mensagens concluídas, sem restaurar um carregamento infinito nem reenviar a
requisição. Erros transitórios também não são restaurados após a recarga.

Em caso de falha, o texto original volta ao campo de edição da conversa de
origem. Não há reenvio automático. As chamadas têm tempo limite de 30 segundos
e são canceladas quando o componente é desmontado.

## Limites atuais

- Até 4.000 caracteres por mensagem, após remover espaços nas extremidades.
  A contagem considera pontos de código Unicode, como o backend, inclusive
  para emojis.
- Até 50 mensagens anteriores por requisição. Ao ultrapassar esse limite, a
  interface solicita uma nova conversa; não descarta o histórico silenciosamente.
- O backend agora rejeita saídas da IA acima de 4.000 caracteres. Conversas antigas
  da etapa simulada podem conter respostas maiores; a interface preserva esses
  dados e orienta iniciar uma nova conversa, sem apagar conteúdo silenciosamente.

Mensagens são exibidas como texto. Conteúdo HTML recebido da API não é executado.

## Verificações automatizadas

Com Node.js 24, usado nesta implementação:

```bash
npm test
npm run lint
npx tsc --noEmit
npm run build
```

Os testes usam o executor nativo do Node.js com suporte a TypeScript, em um
único processo e sem uma dependência adicional de testes. As chamadas HTTP são
substituídas nos testes: não exigem backend em execução, rede ou credenciais.
A suíte também verifica a recuperação da sessão, falhas de armazenamento,
rascunhos e chegada de respostas/erros após trocar a conversa selecionada.

## Roteiro de verificação manual

1. Abra a interface com o backend em execução e envie uma mensagem pelo botão.
   Confira o balão do usuário e a resposta da IA (este teste usa sua API e pode ter custo).
2. Envie outra mensagem usando Enter. Na aba Network do navegador, verifique
   o mesmo `conversation_id`, o histórico anterior e a mensagem atual separada.
3. Use Shift+Enter e confira uma quebra de linha. Tente enviar somente espaços:
   o botão deve permanecer desabilitado.
4. Envie mais de 4.000 caracteres: o contador indica o excesso e impede o envio.
5. Crie uma nova conversa. Confira que a anterior continua no menu e que seus
   títulos passam a refletir a primeira mensagem enviada.
6. Escreva rascunhos diferentes em duas conversas. Alterne entre elas e confira
   que mensagens e rascunhos permanecem separados.
7. Atualize a página: a lista, a conversa selecionada e os rascunhos devem voltar.
8. Atrase uma resposta pelas ferramentas de rede do navegador. Crie ou selecione
   outra conversa, escreva nela e confira que a resposta chega apenas à conversa
   de origem. Durante a espera, nenhum segundo envio deve ser permitido.
9. Recarregue durante um envio: a mensagem deve voltar como rascunho, sem ser
   enviada automaticamente e sem deixar uma indicação permanente de carregamento.
10. Pare o backend e envie uma mensagem: o erro deve aparecer, com o rascunho
   preservado e sem duplicar mensagens. Reinicie o backend e tente novamente.
11. Confira o uso por teclado e a apresentação em uma largura de 390 pixels;
    o botão "Conversas" deve abrir o menu e a seleção deve recolhê-lo.

## Próximas etapas

RAG e catálogo externo, conforme aprovação de cada etapa. Persistência entre
sessões e contas de usuário podem ser avaliadas futuramente. O fluxo Git usa
branches `feature/*` a partir de `develop`, com
commits em português no formato Conventional Commits. Após testes e revisão,
as funcionalidades podem ser integradas em `develop`; versões aprovadas
seguem para `main`.
