import { useEffect, useRef } from "react";

import { countCharacters, MAX_MESSAGE_LENGTH } from "@/lib/chat";

interface ChatComposerProps {
  draft: string;
  isSending: boolean;
  isBlocked: boolean;
  isSendBlocked: boolean;
  error: string | null;
  historyError: string | null;
  onDraftChange: (value: string) => void;
  onSend: () => void;
}

export function ChatComposer({
  draft,
  isSending,
  isBlocked,
  isSendBlocked,
  error,
  historyError,
  onDraftChange,
  onSend,
}: ChatComposerProps) {
  const input = useRef<HTMLTextAreaElement>(null);
  const wasSending = useRef(false);
  const length = countCharacters(draft.trim());
  const isTooLong = length > MAX_MESSAGE_LENGTH;
  const canSend =
    Boolean(length) && !isTooLong && !isSending && !isBlocked && !isSendBlocked && !historyError;

  useEffect(() => {
    if (wasSending.current && !isSending) input.current?.focus();
    wasSending.current = isSending;
  }, [isSending]);

  return (
    <form
      className="border-t border-slate-800 bg-slate-900/90 px-4 py-4 sm:px-8"
      aria-label="Enviar mensagem"
      aria-busy={isSending}
      onSubmit={(event) => {
        event.preventDefault();
        if (canSend) onSend();
      }}
    >
      <div className="mx-auto max-w-3xl">
        {historyError && (
          <p role="status" className="mb-3 text-sm text-amber-300">
            {historyError}
          </p>
        )}
        {error && (
          <p id="chat-error" role="alert" className="mb-3 text-sm text-rose-300">
            {error} Seu texto foi preservado para uma nova tentativa.
          </p>
        )}
        <label htmlFor="chat-message" className="sr-only">
          Sua mensagem
        </label>
        <div className="flex items-end gap-2 rounded-2xl border border-slate-700 bg-slate-950/70 p-2 transition-colors focus-within:border-indigo-400">
          <textarea
            ref={input}
            id="chat-message"
            name="message"
            rows={3}
            value={draft}
            disabled={isSending || isBlocked}
            aria-invalid={isTooLong}
            aria-describedby={`chat-help chat-count${error ? " chat-error" : ""}`}
            placeholder="Peça um jogo, um tutorial ou ajuda com sua plataforma…"
            className="max-h-44 min-h-20 flex-1 resize-y rounded-xl bg-transparent px-3 py-2 text-sm leading-6 text-slate-100 outline-none placeholder:text-slate-500 disabled:opacity-60"
            onChange={(event) => onDraftChange(event.target.value)}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                !event.shiftKey &&
                !event.nativeEvent.isComposing
              ) {
                event.preventDefault();
                if (canSend) onSend();
              }
            }}
          />
          <button
            type="submit"
            disabled={!canSend}
            className="mb-1 flex shrink-0 items-center gap-2 rounded-xl bg-indigo-500 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-indigo-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-300 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-500"
          >
            <span className="hidden sm:inline">
              {isSending ? "Enviando…" : "Enviar"}
            </span>
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <path
                d="m5 12 7-7 7 7M12 5v14"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <span className="sr-only sm:hidden">
              {isSending ? "Enviando mensagem" : "Enviar mensagem"}
            </span>
          </button>
        </div>
        <div className="mt-2 flex justify-between gap-4 text-xs text-slate-400">
          <p id="chat-help">Enter envia · Shift+Enter cria uma nova linha</p>
          <p id="chat-count" className={`shrink-0 ${isTooLong ? "text-rose-300" : ""}`}>
            {length.toLocaleString("pt-BR")} / 4.000
          </p>
        </div>
      </div>
    </form>
  );
}
