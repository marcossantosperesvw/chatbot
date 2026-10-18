# Arquitetura do Chat Jogos

## MVP atual

Monorepo com frontend Next.js/TypeScript e backend Python/FastAPI. São dois
componentes de uma aplicação, não uma arquitetura de microsserviços. Um único
agente do OpenAI Agents SDK responde via Responses API, sem ferramentas externas.

Fluxo: usuário → frontend → `POST /api/chat` → serviço → agente → OpenAI → serviço
→ resposta JSON → frontend → histórico da sessão da aba.

1. O frontend recupera a sessão local e seleciona a conversa pelo UUID.
2. Ao enviar, separa histórico anterior e mensagem atual, validando limites.
3. A API valida novamente os dados; `system`/`tool` e campos extras são rejeitados.
4. O serviço monta o contexto uma vez, cria o agente e aguarda a resposta com timeout.
5. O backend valida o texto e devolve o mesmo UUID, sem salvar a conversa.
6. O frontend associa a resposta à origem, mesmo após trocar de conversa, e salva
   o par concluído no `sessionStorage`. Erros preservam o rascunho, sem reenvio automático.

| Local | Responsabilidade |
| --- | --- |
| `frontend/src/components/chat/` | Interface, mensagens, menu e formulário |
| `frontend/src/hooks/` | Coordenação do estado e dos envios |
| `frontend/src/lib/` | HTTP, regras de conversa e armazenamento da sessão |
| `backend/app/api/` | Contrato público, validação e status HTTP |
| `backend/app/services/` | Orquestração da requisição sem estado compartilhado |
| `backend/app/agents/` | Instruções e configuração do agente |
| `backend/app/core/` | Configuração, erros e proteção dos logs |
| `backend/app/tools/` | Reservado para integrações futuras; ainda não utilizado |
| `backend/app/rag/` e `knowledge/` | Reservados para recuperação futura; ainda não utilizados |
| `backend/app/conversations/` | Reservado; nenhuma persistência de servidor implementada |
| `backend/tests/` e `frontend/tests/` | Verificações sem serviços pagos |

Não criamos rotas Next.js que repitam as rotas de IA do FastAPI. Somente o backend
conhece a chave e as instruções do agente. O frontend não usa o SDK OpenAI.
O UUID organiza mensagens, mas não autentica usuários nem protege acesso.

## Decisões e limites

- REST com resposta completa, sem streaming: contrato menor e fácil de testar.
- `sessionStorage`: atende à recuperação na mesma sessão sem login ou banco;
  não oferece histórico permanente, sincronização entre dispositivos ou isolamento
  contra alguém com acesso à mesma aba. Fechar a aba normalmente encerra a sessão,
  sujeito à restauração de sessões pelo navegador.
- Contexto explícito por requisição: evita duplicar a memória do frontend com
  sessões do SDK ou estado hospedado. O histórico é reenviado e tem custo.
- Um agente sem ferramentas: permite perguntas sobre jogos em geral com base no
  conhecimento do modelo, mas não garante cobertura, precisão ou atualização.
  O agente não consulta um catálogo, preços, fontes ou vídeos nesta etapa.
- Limites atuais: mensagem de 4.000 caracteres, até 50 mensagens anteriores,
  saída de 4.000 caracteres, geração padrão de 800 tokens e timeout de até 25s.
  Caracteres, tokens e custo são medidas diferentes. Não há teto financeiro por usuário.
- `store=False` e tracing desativado: minimizam estado adicional; não representam
  garantia de retenção zero pelo provedor. Veja o guia de privacidade do backend.
- Cliente assíncrono por requisição: ciclo de vida explícito e sem estado global
  de conversa. Reutilização do cliente pode ser avaliada se houver necessidade medida.

## Evolução aprovada apenas como planejamento

Cada implementação exige escopo e aprovação próprios.

1. **RAG:** selecionar fontes licenciadas e verificáveis; depois criar ingestão,
   recuperação e respostas com indicação de fontes. Um catálogo estruturado de
   metadados não é automaticamente RAG. Uma base pequena melhora respostas sobre
   seu conteúdo, mas não deve limitar o chatbot exclusivamente àqueles jogos.
2. **Catálogo externo:** escolher API, cobertura e termos de uso para consultar
   jogos, plataformas e lojas. Distinguir dados consultados de conhecimento do modelo.
3. **Lojas e vídeos:** usar URLs verificadas e embeds permitidos, sem inventar links.
4. **Persistência permanente:** somente quando houver requisito de recuperar
   conversas entre sessões; decidir banco, autenticação, retenção e exclusão juntos.
5. **Deploy e AWS:** AWS é uma opção futura de infraestrutura, não requisito para
   usar a OpenAI e não substitui o SDK. Planejar hospedagem dos dois componentes,
   HTTPS, segredos fora do código, logs/monitoramento e limites de custo. Armazenamento
   de documentos e banco gerenciado só entram quando RAG/persistência justificarem.
   Serviços específicos, região, orçamento, CI/CD e eventual uso do `template.yaml`
   existente serão decididos na etapa de deploy; nenhum recurso AWS foi criado.

Antes de expor a aplicação publicamente, adicionar proteção contra abuso,
limitação de requisições e custos, configuração segura de ambientes e análise
de privacidade. CORS sozinho não protege uma API pública.

## Fluxo Git

`feature/*` nasce de `develop`. Após testes e revisão, integra-se em `develop`;
`main` recebe apenas versões aprovadas, nunca implementação direta. Commits em
português seguem Conventional Commits. Publicar uma branch não significa aprovar
sua integração nem implantar a aplicação.
