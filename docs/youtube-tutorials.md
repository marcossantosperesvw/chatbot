# Tutoriais do YouTube no chat

A feature pesquisa vídeos e anexa até um tutorial à resposta. O player é carregado
por clique e o anexo acompanha a conversa da sessão.

## Configurar a API

1. No [Google Cloud Console](https://console.cloud.google.com/), crie ou selecione um projeto.
2. Na Biblioteca de APIs, habilite **YouTube Data API v3**.
3. Em **APIs e serviços → Credenciais**, crie uma chave de API. OAuth/login do
   YouTube não é necessário para esta pesquisa de metadados públicos.
4. Restrinja a chave à YouTube Data API v3. Chamadas saem do backend: restrições
   por referenciador de navegador não servem para este fluxo. No deploy com IP
   de saída fixo, avalie também restrição por IP.
5. Edite somente estes campos no `backend/.env` existente, preservando as demais configurações:

```dotenv
YOUTUBE_API_KEY=COLE_SUA_CHAVE_LOCALMENTE
YOUTUBE_TIMEOUT_SECONDS=5
YOUTUBE_MAX_SEARCHES_PER_DAY=30
YOUTUBE_PREFERRED_CHANNEL_IDS=
```

6. Reinicie o backend, em `backend/`: `uv run --locked uvicorn app.main:app --reload`.
7. Execute o frontend em outro terminal: `npm run dev`, em `frontend/`.
8. Leia a política na interface, habilite tutoriais e pergunte:
   “Como instalar o inicializador da Epic Games no Windows?”.

Não coloque a chave no frontend, em `NEXT_PUBLIC_*`, em commits ou em mensagens.
Ela é enviada ao Google em cabeçalho HTTP, evitando sua inclusão na URL.
Sem chave/configuração válida, o chat mantém as respostas textuais.
Referências: [configuração oficial](https://developers.google.com/youtube/data/getting-started)
e [proteção de chaves](https://docs.cloud.google.com/docs/authentication/api-keys-best-practices).

## Responsabilidades e contrato

- `app/videos/youtube.py`: HTTPX existente, configuração, cache e orçamento local.
- `app/videos/schemas.py`: ID, título, canal e data; nenhum HTML arbitrário.
- `app/tools/videos.py`: autorização, uma busca por mensagem e até três candidatos.
- O agente escolhe até um resultado com o marcador interno `[VIDEO:ID]`. O serviço
  valida-o contra os resultados atuais e converte em `message.videos`. ID inventado
  é rejeitado; sem seleção, devolve lista vazia. O marcador não aparece na interface.
- `tutorial-video.tsx`: título/canal, player sem autoplay, link externo e opção de fechar.
- A sessão preserva o anexo. O histórico enviado à IA continua somente com papel
  e texto; vídeos antigos não se tornam evidências de consultas novas.

Pedidos sem `include_videos` continuam válidos e não autorizam pesquisa. O campo
`message.videos` é novo. Exemplo fictício apenas do formato do anexo:

```json
{
  "video_id": "abcdefghijk",
  "title": "Exemplo fictício",
  "channel": "Canal fictício",
  "retrieved_at": "2026-10-20T12:00:00Z"
}
```

## Busca e limites

Solicitamos até cinco resultados por relevância, preferindo português e região
Brasil, com filtros de incorporação. Uma consulta adicional em lote confirma
estado público, processamento e permissão e exclui lives, restrições etárias,
bloqueios regionais conhecidos e metadados incompletos. Até três opções chegam
ao agente, que pode omitir todas. Não há download de vídeo ou transcrição.

Idioma preferencial não garante áudio em português. Metadados não comprovam
qualidade, segurança ou atualidade; o agente não pode afirmar que assistiu.
`YOUTUBE_PREFERRED_CHANNEL_IDS` prioriza canais cuja identidade você revisou,
por IDs reais. Vazio mantém a ordem do YouTube; não há selo automático de oficial.

Cache: uma hora, até 128 consultas e limpeza periódica. Pesquisas iguais
concorrentes reutilizam resultados. O teto diário conta tentativas, reinicia em
UTC, é por processo e não sobrevive a reinícios. Não substitui a cota do Google
nem proteção distribuída contra abuso. Erros 403/429 suspendem novas chamadas
por 60 segundos, sem retry. Confira a cota vigente no Console do seu projeto.

A busca inteira tem até cinco segundos, incluindo espera por outras buscas.
O chat mantém o prazo total de até 25 segundos. Com vídeos autorizados/configurados,
permite uma rodada adicional do agente. Geração continua consumindo créditos OpenAI.
Referências: [busca](https://developers.google.com/youtube/data/reference/rest/v3/search/list),
[detalhes](https://developers.google.com/youtube/data/reference/rest/v3/videos/list)
e [player](https://developers.google.com/youtube/player_parameters).

## Privacidade

A pesquisa começa desligada e a autorização não persiste após recarregar. O
usuário aceita a política indicada antes de habilitar. O backend só então expõe
a ferramenta. O agente envia termos relevantes e é instruído a excluir dados
pessoais e histórico completo.

O player usa `youtube-nocookie.com` e só é inserido após clique, sem promessa de
ausência de coleta pelo YouTube. A interface informa o compartilhamento e oferece
link externo quando a reprodução falha. Disponibilidade pode mudar após a consulta.

Metadados expiram após 29 dias e são filtrados ao recuperar/salvar. A aba ativa
salva periodicamente para limpar anexos antigos; abas suspensas dependem de
retomada/recarregamento. O texto é preservado. Não há OAuth ou banco permanente
no servidor. Mantenha a política da aplicação alinhada às
[políticas do YouTube](https://developers.google.com/youtube/terms/developer-policies).

## Testes

Em `backend/`: `uv run --locked pytest tests/test_videos.py -q -W error`.
Em `frontend/`: `npm test`, `npm run lint`, `npm run build`.

Os testes usam transportes simulados, sem cotas reais. Cobrem filtros, cache,
orçamento, falhas, autorização, IDs inventados, SDK, contrato e sessão.
Avalie com sua chave: relevância/idioma, pedidos ambíguos, troca de conversa,
recarga e reprodução em celular. Conteúdo real não foi validado nesta entrega.
