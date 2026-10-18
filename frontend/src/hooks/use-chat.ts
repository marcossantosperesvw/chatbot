"use client";

import { useEffect, useRef, useState } from "react";

import { sendChatMessage } from "@/lib/api";
import { createChatRequest, getHistoryError } from "@/lib/chat";
import type { ChatMessage } from "@/types/chat";

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const conversationId = useRef<string | null>(null);
  const inFlight = useRef(false);
  const activeRequest = useRef<AbortController | null>(null);

  useEffect(() => () => activeRequest.current?.abort(), []);

  async function sendMessage() {
    // O ref também impede dois envios antes da próxima renderização do React.
    if (inFlight.current) return;

    const previousMessages = messages;
    const submittedDraft = draft;
    let request;

    try {
      const id = conversationId.current ?? crypto.randomUUID();
      request = createChatRequest(id, submittedDraft, previousMessages);
      conversationId.current = id;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Não foi possível enviar.");
      return;
    }

    const controller = new AbortController();
    activeRequest.current = controller;
    inFlight.current = true;
    setIsSending(true);
    setError(null);
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: request.message,
    };
    setMessages([...previousMessages, userMessage]);
    setDraft("");

    try {
      const response = await sendChatMessage(request, controller.signal);
      if (controller.signal.aborted) return;

      setMessages([
        ...previousMessages,
        userMessage,
        { id: crypto.randomUUID(), ...response.message },
      ]);
    } catch (cause) {
      if (controller.signal.aborted) return;
      // Uma tentativa com falha não entra no histórico do próximo envio.
      setMessages(previousMessages);
      setDraft(submittedDraft);
      setError(
        cause instanceof Error ? cause.message : "Não foi possível enviar. Tente novamente.",
      );
    } finally {
      inFlight.current = false;
      if (!controller.signal.aborted) setIsSending(false);
    }
  }

  function startNewConversation() {
    if (inFlight.current) return;
    conversationId.current = null;
    setMessages([]);
    setDraft("");
    setError(null);
  }

  return {
    messages,
    draft,
    setDraft,
    isSending,
    error,
    historyError: isSending ? null : getHistoryError(messages),
    sendMessage,
    startNewConversation,
  };
}
