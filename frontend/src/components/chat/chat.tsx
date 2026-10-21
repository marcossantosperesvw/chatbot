"use client";

import { useRef, useState } from "react";

import { useChat } from "@/hooks/use-chat";

import { ChatComposer } from "./chat-composer";
import { MessageList } from "./message-list";
import { ConversationSidebar } from "./conversation-sidebar";

const SUGGESTIONS = [
  "Quero um jogo cooperativo",
  "Gosto de RPG e exploração",
  "Procuro um jogo para partidas rápidas",
];

export function Chat() {
  const chat = useChat();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const sidebarToggle = useRef<HTMLButtonElement>(null);

  function startNewConversation() {
    chat.startNewConversation();
    setIsSidebarOpen(false);
  }

  function selectConversation(id: string) {
    chat.selectConversation(id);
    if (isSidebarOpen) {
      setIsSidebarOpen(false);
      sidebarToggle.current?.focus();
    }
  }

  return (
    <main className="mx-auto flex min-h-svh w-full max-w-7xl flex-col px-3 py-4 sm:px-6 sm:py-6">
      <header className="mb-5 flex items-center justify-between gap-3 px-1">
        <div className="flex items-center gap-3">
          <span
            className="flex h-10 w-10 items-center justify-center rounded-xl border border-indigo-400/30 bg-indigo-500/10 text-indigo-300"
            aria-hidden="true"
          >
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
            >
              <path d="M8 7h8a4 4 0 0 1 3.9 3.1l1.2 5.4a2.5 2.5 0 0 1-4.2 2.3L14 15h-4l-2.9 2.8a2.5 2.5 0 0 1-4.2-2.3l1.2-5.4A4 4 0 0 1 8 7Z" />
              <path
                d="M7 9v5m-2.5-2.5h5M16 10h.01M18 12h.01"
                strokeLinecap="round"
              />
            </svg>
          </span>
          <div>
            <h1 className="text-base font-semibold tracking-tight text-white sm:text-lg">
              Chat Jogos
            </h1>
            <p className="text-xs text-slate-400">
              Uma conversa sobre o seu próximo jogo
            </p>
          </div>
        </div>
        <span className="rounded-full border border-indigo-400/20 bg-indigo-500/10 px-3 py-1 text-xs font-medium text-indigo-200">
          Assistente IA
        </span>
      </header>

      {chat.storageWarning && (
        <p role="status" className="mb-3 rounded-xl border border-amber-300/20 bg-amber-300/5 px-4 py-3 text-sm text-amber-200">
          {chat.storageWarning}
        </p>
      )}
      <div
        className="flex h-[calc(100svh-10rem)] min-h-96 flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/80 shadow-2xl shadow-black/20 sm:h-[calc(100svh-11rem)] md:flex-row"
      >
        <ConversationSidebar
          conversations={chat.conversations}
          activeConversationId={chat.activeConversation?.id}
          pendingConversationId={chat.pendingConversationId}
          isOpen={isSidebarOpen}
          onSelect={selectConversation}
        />
        <section
          aria-label="Chat sobre jogos"
          className="flex min-h-0 min-w-0 flex-1 flex-col"
        >
          <div className="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-4 sm:px-8">
            <div className="flex min-w-0 items-center gap-3">
              <button
                ref={sidebarToggle}
                type="button"
                aria-controls="conversation-sidebar"
                aria-expanded={isSidebarOpen}
                onClick={() => setIsSidebarOpen((open) => !open)}
                className="shrink-0 rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-200 focus-visible:outline-2 focus-visible:outline-indigo-300 md:hidden"
              >
                Conversas
              </button>
              <h2 className="truncate text-sm font-medium text-slate-200" title={chat.activeConversation?.title}>
                {chat.activeConversation?.title ?? "Conversa atual"}
              </h2>
            </div>
            <button
              type="button"
              onClick={startNewConversation}
              disabled={!chat.isReady}
              className="shrink-0 rounded-lg border border-slate-700 px-3 py-2 text-xs font-medium text-slate-300 transition-colors hover:border-indigo-400 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-300 disabled:cursor-not-allowed disabled:opacity-40"
            >
              + Nova conversa
            </button>
          </div>

          {chat.isWaitingForOtherConversation && (
            <p role="status" className="border-b border-slate-800 px-4 py-3 text-xs leading-5 text-indigo-200 sm:px-8">
              Uma resposta está sendo preparada em outra conversa. Você pode navegar e escrever; aguarde para enviar.
            </p>
          )}

          {!chat.isReady ? (
            <div role="status" className="flex flex-1 items-center justify-center text-sm text-slate-400">
              Recuperando conversas da sessão…
            </div>
          ) : chat.messages.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center overflow-y-auto px-5 py-10 text-center">
              <p className="mb-4 text-xs font-semibold tracking-[0.2em] text-indigo-300">
                APERTE START
              </p>
              <h2 className="max-w-lg text-2xl font-semibold leading-tight tracking-tight text-white sm:text-3xl">
                Qual será a próxima aventura?
              </h2>
              <p className="mt-4 max-w-md text-sm leading-6 text-slate-400">
                Conte o que você gosta de jogar ou faça uma pergunta.
                Suas preferências nesta conversa ajudam nas recomendações.
              </p>
              <div className="mt-7 flex max-w-xl flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => chat.setDraft(suggestion)}
                    className="rounded-xl border border-slate-700 bg-slate-800/50 px-4 py-3 text-xs text-slate-300 transition-colors hover:border-indigo-400/70 hover:bg-indigo-500/10 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-300"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <MessageList
              key={`messages-${chat.activeConversation?.id}`}
              messages={chat.messages}
              isSending={chat.isSending}
            />
          )}

          <div className="border-t border-slate-800 px-4 py-2 text-xs leading-5 text-slate-400 sm:px-8">
            <label className="flex items-start gap-2">
              <input type="checkbox" checked={chat.includeVideos} disabled={chat.isSending || chat.isWaitingForOtherConversation}
                onChange={(event) => chat.setIncludeVideos(event.target.checked)} className="mt-1 accent-indigo-500" />
              <span>Incluir tutoriais do YouTube quando úteis. Autorizo o envio dos termos relevantes da pergunta ao Google e aceito os{" "}
                <a href="https://www.youtube.com/t/terms" target="_blank" rel="noopener noreferrer" className="underline">Termos do YouTube</a>{" "}
                e a <a href="/privacidade" target="_blank" rel="noopener noreferrer" className="underline">política de privacidade</a>.
              </span>
            </label>
          </div>
          <ChatComposer
            key={`composer-${chat.activeConversation?.id}`}
            draft={chat.draft}
            isSending={chat.isSending}
            isBlocked={!chat.isReady}
            isSendBlocked={chat.isWaitingForOtherConversation}
            error={chat.error}
            historyError={chat.historyError}
            onDraftChange={chat.setDraft}
            onSend={chat.sendMessage}
          />
        </section>
      </div>
      <p className="mt-4 text-center text-xs leading-5 text-slate-500">
        Respostas geradas por IA podem conter erros. O conteúdo da conversa atual é enviado à OpenAI.
        {" "}
        As conversas são recuperadas ao atualizar esta aba. Fechar a aba normalmente encerra a sessão.
      </p>
    </main>
  );
}
