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

- Conversa em memória, com mensagens do usuário e do assistente.
- Envio pelo botão ou por Enter; Shift+Enter insere uma quebra de linha.
- Sugestões iniciais que preenchem o campo sem enviar automaticamente.
- Indicação de carregamento e bloqueio de envios simultâneos.
- Erros em português, preservando o rascunho e as mensagens anteriores.
- Nova conversa com confirmação antes de descartar mensagens ou rascunho.
- Layout responsivo, rótulos acessíveis, foco visível e movimento reduzido.

O backend ainda responde com texto simulado. O histórico enviado não é
interpretado por um modelo nesta etapa. Atualizar ou fechar a página apaga a
conversa: `sessionStorage` será implementado em uma etapa separada.

## Organização

| Local | Responsabilidade |
| --- | --- |
| `src/app/page.tsx` | Compor a página com o componente de chat |
| `src/components/chat/` | Apresentar mensagens, formulário e estados da interface |
| `src/hooks/use-chat.ts` | Coordenar o estado, o envio e a recuperação após falhas |
| `src/lib/api.ts` | Fazer chamadas HTTP e validar respostas em tempo de execução |
| `src/lib/chat.ts` | Preparar requisições e verificar limites do contrato |
| `src/types/chat.ts` | Definir tipos TypeScript correspondentes ao contrato HTTP |
| `tests/` | Testar preparação do histórico e comunicação HTTP com respostas simuladas |

O identificador UUID é criado no primeiro envio e reutilizado até iniciar uma
nova conversa. Cada requisição inclui somente as mensagens anteriores em
`history`; a mensagem atual aparece uma única vez em `message`. IDs locais da
interface não são enviados dentro das mensagens.

Em caso de falha, a tentativa é retirada do histórico e seu texto original
volta ao campo de edição. Não há reenvio automático. As chamadas têm tempo
limite de 30 segundos e são canceladas quando o componente é desmontado.

## Limites atuais

- Até 4.000 caracteres por mensagem, após remover espaços nas extremidades.
  A contagem considera pontos de código Unicode, como o backend, inclusive
  para emojis.
- Até 50 mensagens anteriores por requisição. Ao ultrapassar esse limite, a
  interface solicita uma nova conversa; não descarta o histórico silenciosamente.
- O simulador pode devolver uma resposta maior que 4.000 caracteres ao repetir
  uma mensagem longa. Essa resposta permanece visível, mas não pode ser enviada
  no histórico do próximo turno. A interface avisa e permite iniciar uma nova
  conversa. A compatibilidade desses limites poderá ser revista na etapa de IA.

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
único processo e sem uma dependência adicional de testes. As chamadas HTTP são substituídas nos testes:
não exigem backend em execução, acesso à rede ou credenciais.

## Roteiro de verificação manual

1. Abra a interface com o backend em execução e envie uma mensagem pelo botão.
   Confira o balão do usuário e a resposta simulada.
2. Envie outra mensagem usando Enter. Na aba Network do navegador, verifique
   o mesmo `conversation_id`, o histórico anterior e a mensagem atual separada.
3. Use Shift+Enter e confira uma quebra de linha. Tente enviar somente espaços:
   o botão deve permanecer desabilitado.
4. Envie mais de 4.000 caracteres: o contador indica o excesso e impede o envio.
5. Atrase a rede pelas ferramentas do navegador: durante o envio, o formulário
   e o botão de nova conversa ficam bloqueados.
6. Pare o backend e envie uma mensagem: o erro deve aparecer, com o rascunho
   preservado e sem duplicar mensagens. Reinicie o backend e tente novamente.
7. Inicie uma nova conversa: cancelar a confirmação deve preservar o conteúdo;
   confirmar deve limpar a interface e gerar outro identificador no próximo envio.
8. Confira o uso por teclado e a apresentação em uma largura de 390 pixels.
9. Atualize a página: nesta etapa, a conversa deve ser apagada.

## Próximas etapas

Salvamento na sessão da aba, integração com OpenAI e RAG, conforme aprovação
de cada etapa. O fluxo Git usa branches `feature/*` a partir de `develop`, com
commits em português no formato Conventional Commits. Após testes e revisão,
as funcionalidades podem ser integradas em `develop`; versões aprovadas
seguem para `main`.
