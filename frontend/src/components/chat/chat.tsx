"use client";

import { useEffect, useRef, useState } from "react";

import { useChat } from "@/hooks/use-chat";

import { ChatComposer } from "./chat-composer";
import { MessageList } from "./message-list";

const SUGGESTIONS = [
  "Quero um jogo cooperativo",
  "Gosto de RPG e exploração",
  "Procuro um jogo para partidas rápidas",
];

export function Chat() {
  const chat = useChat();
  const [isConfirmingReset, setIsConfirmingReset] = useState(false);
  const cancelReset = useRef<HTMLButtonElement>(null);
  const newConversationButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (isConfirmingReset) cancelReset.current?.focus();
  }, [isConfirmingReset]);

  function startNewConversation() {
    if (chat.messages.length || chat.draft) {
      setIsConfirmingReset(true);
      return;
    }
    chat.startNewConversation();
  }

  function finishReset(confirmed: boolean) {
    if (confirmed) chat.startNewConversation();
    setIsConfirmingReset(false);
    newConversationButton.current?.focus();
  }

  return (
    <main className="mx-auto flex min-h-svh w-full max-w-6xl flex-col px-3 py-4 sm:px-6 sm:py-6">
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
          Demonstração
        </span>
      </header>

      <section
        aria-label="Chat sobre jogos"
        className="flex h-[calc(100svh-10rem)] min-h-96 flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/80 shadow-2xl shadow-black/20 sm:h-[calc(100svh-11rem)]"
      >
        <div className="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-4 sm:px-8">
          <h2 className="text-sm font-medium text-slate-200">Conversa atual</h2>
          <button
            ref={newConversationButton}
            type="button"
            onClick={startNewConversation}
            disabled={chat.isSending}
            className="rounded-lg border border-slate-700 px-3 py-2 text-xs font-medium text-slate-300 transition-colors hover:border-indigo-400 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-300 disabled:cursor-not-allowed disabled:opacity-40"
          >
            + Nova conversa
          </button>
        </div>

        {isConfirmingReset && (
          <div
            role="region"
            aria-label="Confirmar nova conversa"
            className="border-b border-amber-300/20 bg-amber-300/5 px-4 py-4 sm:px-8"
            onKeyDown={(event) => {
              if (event.key === "Escape") finishReset(false);
            }}
          >
            <p className="text-sm text-amber-100">
              Iniciar uma nova conversa? As mensagens e o rascunho atuais serão apagados.
            </p>
            <div className="mt-3 flex flex-wrap gap-3">
              <button
                ref={cancelReset}
                type="button"
                onClick={() => finishReset(false)}
                className="rounded-lg border border-slate-600 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-300"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={() => finishReset(true)}
                className="rounded-lg bg-amber-200 px-3 py-2 text-sm font-medium text-slate-950 hover:bg-amber-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-100"
              >
                Apagar e iniciar
              </button>
            </div>
          </div>
        )}

        {chat.messages.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center overflow-y-auto px-5 py-10 text-center">
            <h2 className="max-w-lg text-2xl font-semibold leading-tight tracking-tight text-white sm:text-3xl">
              Qual será a próxima aventura?
            </h2>
            <p className="mt-4 max-w-md text-sm leading-6 text-slate-400">
              Conte o que você gosta de jogar ou faça uma pergunta. Nesta
              demonstração, você receberá uma resposta simulada.
            </p>
            <div className="mt-7 flex max-w-xl flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  disabled={isConfirmingReset}
                  onClick={() => chat.setDraft(suggestion)}
                  className="rounded-xl border border-slate-700 bg-slate-800/50 px-4 py-3 text-xs text-slate-300 transition-colors hover:border-indigo-400/70 hover:bg-indigo-500/10 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-300"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <MessageList messages={chat.messages} isSending={chat.isSending} />
        )}

        <ChatComposer
          draft={chat.draft}
          isSending={chat.isSending}
          isBlocked={isConfirmingReset}
          error={chat.error}
          historyError={chat.historyError}
          onDraftChange={chat.setDraft}
          onSend={chat.sendMessage}
        />
      </section>
      <p className="mt-4 text-center text-xs leading-5 text-slate-500">
        Ao atualizar ou fechar esta página, a conversa é apagada.
      </p>
    </main>
  );
}
