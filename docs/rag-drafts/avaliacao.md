# Roteiro de revisão e avaliação documental

Este arquivo é material de desenvolvimento, não conteúdo para indexar.
Os casos abaixo são um roteiro manual, não testes automatizados já executados.

## Antes da integração

Para cada guia, confira a fonte, corrija o texto e registre no final do documento:

```text
Revisor:
Data da revisão humana:
Ambiente/versão/idioma, se verificados:
Validação prática: executada / não executada
Condições de uso: revisadas / pendentes
Resultado: aprovado / requer ajustes
Pendências:
```

Não preencha como executado ou aprovado sem realizar a revisão correspondente.
Use o [modelo](modelo-documento.md) para novos temas.

## Depois da adaptação e indexação

Execute perguntas independentes, em conversas novas, evitando que respostas
anteriores forneçam a informação que queremos avaliar. Registre a configuração
e o identificador do índice utilizados. Os rascunhos sozinhos não ativam o RAG.

| Pergunta | Documento esperado ou comportamento |
| --- | --- |
| Como verifico a integridade de um jogo instalado na Steam? | `steam-verificacao-arquivos.md` |
| Como verifico um jogo na Epic Games? | `epic-verificacao-arquivos.md`; não misturar clientes |
| Como personalizo os botões do DualSense no PS5? | `ps5-remapeamento-controle.md` |
| O que são layouts de controle na Steam? | `steam-input-keybinds.md` |
| Como descubro minha RAM e versão do Windows? | `windows-especificacoes.md` |
| Quais atalhos do Windows ajudam a navegar entre aplicativos? | `windows-atalhos.md` |
| Onde confiro se um jogo da Steam suporta meu sistema? | `steam-compatibilidade-sistemas.md` |
| O que preciso conferir na PlayStation Store antes de comprar? | `playstation-store-compras.md` |
| Como verifico os arquivos do meu jogo? | Perguntar qual loja/plataforma, sem escolher por suposição |
| Esses guias confirmam o botão de salto no meu jogo? | Reconhecer ausência do mapa específico |
| Qual o preço de um jogo hoje? | Não usar este corpus como cotação atual |
| Como configuro isso no Xbox? | Reconhecer ausência de documentação Xbox neste lote |
| Verificar arquivos preserva todos os meus mods? | Não transformar informação ausente em garantia |

## Evidências a registrar

- Pergunta, resposta e trechos efetivamente retornados pela ferramenta.
- Documento correto recuperado ou ausência de correspondência.
- Citação sustentando a afirmação e respeito ao produto/plataforma do documento.
- Informações inventadas, confusão entre clientes ou ressalvas omitidas.
- Falha de recuperação separada de falha na redação da resposta.

Critério inicial proposto: cada caso respondível deve recuperar o guia esperado;
casos ambíguos devem pedir contexto; lacunas não podem gerar certezas ou URLs
inventadas. Ajustaremos esse critério com resultados observados, sem confundir
pontuação de busca com precisão factual.

Uma comparação futura com e sem recuperação deve manter modelo, prompt e
perguntas equivalentes. Chamadas reais podem gerar custo e não foram feitas
para preparar estes arquivos.
