export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-2xl space-y-5 px-6 py-12 text-sm leading-7 text-slate-200">
      <h1 className="text-2xl font-semibold">Privacidade — Chat Jogos</h1>
      <p>Suas conversas ficam no sessionStorage desta aba. O conteúdo da conversa atual é enviado à OpenAI para gerar respostas. O backend não mantém um banco de conversas.</p>
      <p>Ao habilitar tutoriais, você autoriza o uso da YouTube Data API. Termos de busca relacionados à pergunta podem ser enviados ao Google. O agente é orientado a não incluir dados pessoais; evite inserir informações sensíveis nas perguntas. Não solicitamos login do YouTube.</p>
      <p>Os resultados incluem ID, título, canal e data da consulta. O backend usa cache temporário de uma hora para reduzir consultas. Um vídeo selecionado é salvo junto à mensagem na sessão da aba. Os metadados expiram após 29 dias e são descartados ao recuperar ou salvar a sessão, com limpeza periódica enquanto a aba está ativa. A limpeza depende da execução do navegador; ao retornar a uma aba suspensa, recarregue a página.</p>
      <p>O player é carregado apenas após seu clique. A partir daí o YouTube pode receber informações como endereço IP e dados do navegador, usar tecnologias de armazenamento e exibir publicidade. Não baixamos vídeos nem controlamos o conteúdo ou a disponibilidade deles.</p>
      <p>Desmarque a opção de tutoriais para interromper novas buscas. Fechar a aba normalmente encerra a sessão, sujeito à restauração do navegador; você também pode limpar os dados do site nas configurações do navegador.</p>
      <p>Consulte os <a className="underline" href="https://www.youtube.com/t/terms">Termos de Serviço do YouTube</a> e a <a className="underline" href="https://policies.google.com/privacy">Política de Privacidade do Google</a>. Ao habilitar a opção, você concorda com esses termos e com esta política.</p>
      <Link href="/" className="text-indigo-300 underline">Voltar ao chat</Link>
    </main>
  );
}
import Link from "next/link";
