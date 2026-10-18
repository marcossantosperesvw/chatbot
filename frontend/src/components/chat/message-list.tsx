import { useEffect, useRef } from "react";

import type { ChatMessage } from "@/types/chat";

interface MessageListProps {
  messages: ChatMessage[];
  isSending: boolean;
}

export function MessageList({ messages, isSending }: MessageListProps) {
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
      block: "nearest",
    });
  }, [messages, isSending]);

  return (
    <div
      role="log"
      aria-label="Mensagens da conversa"
      aria-live="polite"
      aria-relevant="additions"
      className="flex-1 overflow-y-auto overscroll-contain px-4 py-6 sm:px-8"
    >
      <ol className="mx-auto flex max-w-3xl flex-col gap-6">
        {messages.map((message) => {
          const isUser = message.role === "user";
          return (
            <li
              key={message.id}
              className={`flex flex-col gap-2 ${isUser ? "items-end" : "items-start"}`}
            >
              <span className="px-1 text-xs font-medium text-slate-400">
                {isUser ? "Você" : "Chat Jogos"}
              </span>
              <p
                className={`max-w-[92%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-7 [overflow-wrap:anywhere] sm:max-w-[85%] ${
                  isUser
                    ? "rounded-tr-sm bg-indigo-500 text-white"
                    : "rounded-tl-sm border border-slate-700/70 bg-slate-800/80 text-slate-200"
                }`}
              >
                {message.content}
              </p>
            </li>
          );
        })}
        {isSending && (
          <li className="flex items-center gap-3 text-sm text-slate-400">
            <span className="h-2 w-2 rounded-full bg-indigo-400 motion-safe:animate-pulse" />
            Preparando resposta…
          </li>
        )}
      </ol>
      <div ref={end} />
    </div>
  );
}
