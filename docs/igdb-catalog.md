# Catálogo IGDB — primeira entrega

## O que está disponível

`GET /api/games?query=nome&limit=5` pesquisa jogos por nome no backend. Retorna
metadados normalizados, a página de origem na IGDB e links de lojas presentes
na resposta do catálogo. Esta consulta não chama a OpenAI nem consome seus créditos.

O agente do chat ainda não utiliza essa pesquisa. A próxima entrega conectará
o cliente a uma ferramenta do agente, com regras sobre quando consultar. Cards,
links clicáveis no chat, vídeos e RAG serão implementados separadamente.

Não há uma lista fixa de jogos: a pesquisa considera os registros disponíveis
na IGDB. Cobertura, preenchimento dos campos e nomes alternativos variam. Uma
pesquisa por nome não é uma busca semântica por frases como "quero um jogo calmo".
Filtros por preferências serão acrescentados posteriormente.

## Configurar suas credenciais

1. Entre na sua conta Twitch e habilite autenticação em dois fatores.
2. Acesse o [portal de aplicativos Twitch](https://dev.twitch.tv/console/apps)
   e registre um aplicativo para o projeto. Use o tipo **Confidential** para
   poder gerar um segredo. Se for exigida uma URL OAuth de redirecionamento,
   informe uma URL local aceita pelo portal, como `http://localhost:8000`;
   o fluxo usado pela IGDB não utiliza esse redirecionamento.
3. Abra o gerenciamento do aplicativo e obtenha **Client ID** e **Client Secret**.
   A aplicação usará credenciais de aplicativo; os usuários do chat não precisam
   fazer login na Twitch.
4. Edite o arquivo `backend/.env` existente e acrescente:

   ```dotenv
   IGDB_CLIENT_ID=SEU_CLIENT_ID_TWITCH
   IGDB_CLIENT_SECRET=SEU_CLIENT_SECRET_TWITCH
   IGDB_TIMEOUT_SECONDS=5
   ```

   Substitua os marcadores localmente. Estas credenciais são diferentes da chave
   OpenAI. Não coloque o segredo no frontend nem o envie no chat. O `.env` é
   ignorado pelo Git; `.env.example` contém somente nomes e valores de exemplo.
5. Instale as dependências e inicie ou reinicie o backend:

   ```bash
   cd /home/marcos/chatbot/backend
   uv sync --locked
   uv run --locked uvicorn app.main:app --reload
   ```

Variáveis exportadas no terminal têm precedência sobre `.env`. As configurações
IGDB são lidas na primeira consulta válida e mantidas até reiniciar o processo.
Sem elas, o catálogo devolve 503 e o chat e o health check continuam disponíveis.

Referências: [configuração IGDB](https://api-docs.igdb.com/#account-creation) e
[autenticação de aplicativo Twitch](https://dev.twitch.tv/docs/authentication/getting-tokens-oauth/#client-credentials-grant-flow).

## Testar o acesso real

Abra <http://127.0.0.1:8000/docs>, expanda **GET /api/games**, use **Try it out**,
preencha `query` com `Stardew Valley`, `limit` com `3` e execute.

Também é possível usar um segundo terminal:

```bash
curl --get 'http://127.0.0.1:8000/api/games' \
  --data-urlencode 'query=Stardew Valley' \
  --data 'limit=3'
```

Confira:

- `source` é `IGDB` e `query` corresponde ao nome pesquisado.
- `games` contém candidatos: verifique se é o jogo desejado, e não outra edição.
- `source_url` e `store_links` podem estar ausentes. Não completamos URLs por palpite.
- `retrieved_at` informa quando os dados foram obtidos pelo backend.
- Ao repetir a mesma pesquisa e limite, `cached` passa a `true`, por até cinco minutos.

Tente também um título improvável. Se a IGDB não encontrar registros, uma resposta
200 com `games: []` é um resultado válido. A consulta não garante uma correspondência
exata com o primeiro candidato retornado.

O teste real depende de você configurar as credenciais e executar a consulta.
Os testes automatizados usam dados sintéticos e não comprovam o acesso da sua conta.

## Contrato

- `query`: obrigatório, com 1 a 120 caracteres após remover espaços nas extremidades.
  Não aceita caracteres de controle. Aspas e barras são tratadas como parte do nome,
  não como comandos da linguagem de consulta.
- `limit`: inteiro de 1 a 10; padrão 5. Parâmetros desconhecidos são rejeitados.
- `games`: cada item tem `id`, `name`, `summary`, `platforms`, `genres`, `game_modes`,
  `release_date`, `source_url` e `store_links`.
- Campos opcionais não disponíveis são representados por `null` ou listas vazias.
- `store_links`: lista de pares `store`/`url`; não contém preços ou disponibilidade.

Os links vêm de `websites.url` da IGDB e passam por uma lista de domínios de lojas
conhecidas, aceitando apenas HTTPS e sem credenciais embutidas. A página de origem
deve pertencer ao domínio IGDB. Links de domínios não reconhecidos são omitidos.
O cliente não segue os links nem verifica se o jogo está comprável na sua região,
se a página continua ativa ou se a edição é a pretendida. Essa validação requer
conferir o resultado real. Não há comparação de preços nesta entrega.

## Funcionamento e limites

O ciclo é: rota FastAPI → cliente IGDB → token Twitch → validação do token →
pesquisa IGDB → normalização → JSON. Há um cliente HTTP reutilizado durante a
vida da aplicação e fechado ao encerrar o backend.

- O segredo é enviado no corpo do POST de autenticação, não na URL. Endpoints
  externos são fixos e redirecionamentos HTTP automáticos estão desativados.
- Tokens ficam somente em memória e são renovados antes da expiração. Um 401
  na pesquisa permite uma única renovação e repetição; falhas comuns não disparam
  novas tentativas automáticas.
- Validamos o token após obtê-lo e periodicamente a cada hora, seguindo a
  [orientação Twitch](https://dev.twitch.tv/docs/authentication/validate-tokens/).
  Uma falha invalida o token local; a consulta seguinte precisa obter outro.
- Pesquisas normalizadas por nome e limite ficam em cache por 300 segundos,
  incluindo resultados vazios. O cache tem no máximo 128 entradas e desaparece
  ao reiniciar. Dados são copiados para evitar que um consumidor altere o cache.
- Consultas são serializadas e espaçadas em pelo menos 0,26 segundo entre
  requisições à IGDB. Esse controle é por processo; múltiplos workers ou outras
  aplicações usando as mesmas credenciais exigirão coordenação posterior.
- O timeout total padrão é cinco segundos, configurável de 1 a 15. Inclui espera,
  autenticação, validação, pesquisa e eventual renovação. Não há fila externa.
- Depois de 429, pesquisas não disponíveis em cache respeitam um intervalo local
  antes de consultar novamente. `Retry-After` numérico é propagado; se ausente ou
  inválido, usamos um segundo. A aplicação continua sujeita aos limites do provedor.

As descrições podem estar em outro idioma. A futura ferramenta entregará dados
ao agente, que poderá explicá-los em português sem alterar sua origem.

## Erros e testes

| HTTP | Significado |
| --- | --- |
| 422 | Parâmetros ausentes ou inválidos |
| 429 | Limite do provedor ou período local de espera; conferir `Retry-After` |
| 502 | Credenciais recusadas, falha de conexão ou resposta inválida do provedor |
| 503 | Configuração IGDB ausente ou inválida |
| 504 | Tempo limite da pesquisa excedido |

Os erros omitem corpos do provedor, tokens e segredos. Por exemplo, um 502 não
permite concluir sozinho que a chave está errada: confira também a conta, a
configuração do aplicativo e o serviço IGDB. Não habilite logs de depuração HTTP
com credenciais reais. CORS não autentica clientes; o uso público continua a
depender da etapa de proteção contra abuso e controle de acesso.

Na pasta `backend/`, execute:

```bash
uv run --locked pytest tests/test_catalog.py -q -W error
uv run --locked pytest -q -W error
```

A suíte usa `httpx.MockTransport` para simular autenticação, validação, pesquisa
e falhas, sem chamadas externas. O `httpx` já era instalado pelo cliente OpenAI;
agora está declarado como dependência direta porque o catálogo o utiliza.

## Fontes e próximos passos

A IGDB foi escolhida para fundamentar dados de jogos e possibilitar links
recebidos de uma fonte identificável. Ela não garante recomendações corretas por
si só e não equivale a uma base RAG de tutoriais. Veja os
[dados e limites oficiais](https://api-docs.igdb.com/).

O projeto acadêmico utiliza o acesso não comercial. Se houver monetização,
confirme as condições de parceria e atribuição descritas no
[FAQ IGDB](https://api-docs.igdb.com/#business-related-faq). Exiba atribuição à fonte
quando os dados forem apresentados na interface.

Depois de validar a consulta real: aprovar filtros por preferências e a ferramenta
do agente (3B), limitar suas chamadas e resultados, ajustar o número de turnos do
runner e decidir como exibir fontes e links no chat. A etapa de investigação de
preferências continua com avaliação própria pendente; esta feature parte de `develop`.
