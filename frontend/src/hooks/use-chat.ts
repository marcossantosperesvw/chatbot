"use client";

import { useEffect, useReducer, useRef } from "react";

import { sendChatMessage } from "@/lib/api";
import { createChatRequest, getHistoryError } from "@/lib/chat";
import { loadConversationSession, saveConversationSession } from "@/lib/conversation-storage";
import { conversationsReducer, createConversation, initialConversationsState } from "@/lib/conversations";
import type { ChatMessage, ChatRequest } from "@/types/chat";

export function useChat() {
  const [state, dispatch] = useReducer(conversationsReducer, initialConversationsState);
  const canPersist = useRef(false);
  const inFlight = useRef(false);
  const activeRequest = useRef<AbortController | null>(null);

  useEffect(() => {
    const restored = loadConversationSession();
    canPersist.current = restored.canPersist;
    let session = restored.session;
    if (!session) {
      const conversation = createConversation(crypto.randomUUID(), new Date().toISOString());
      session = { version: 1, conversations: [conversation], activeConversationId: conversation.id };
    }
    dispatch({ type: "restore", session, warning: restored.warning });
    return () => activeRequest.current?.abort();
  }, []);

  useEffect(() => {
    if (!state.session || !canPersist.current) return;
    const warning = saveConversationSession(state.session);
    dispatch({ type: "storage-warning", warning });
  }, [state.session]);

  const conversation = state.session?.conversations.find(
    ({ id }) => id === state.session?.activeConversationId,
  );
  const isSending = Boolean(conversation && state.pending?.conversationId === conversation.id);
  const messages = conversation
    ? isSending && state.pending
      ? [...conversation.messages, state.pending.userMessage]
      : conversation.messages
    : [];

  function setDraft(draft: string) {
    if (!conversation) return;
    dispatch({ type: "draft", conversationId: conversation.id, draft, now: new Date().toISOString() });
  }

  function startNewConversation() {
    if (!state.session) return;
    dispatch({ type: "create", conversation: createConversation(crypto.randomUUID(), new Date().toISOString()) });
  }

  function selectConversation(conversationId: string) {
    dispatch({ type: "select", conversationId });
  }

  async function sendMessage() {
    if (inFlight.current || !conversation) return;
    const conversationId = conversation.id;
    let request: ChatRequest;

    try {
      request = createChatRequest(conversationId, conversation.draft, conversation.messages);
    } catch (cause) {
      dispatch({
        type: "error",
        conversationId,
        error: cause instanceof Error ? cause.message : "Não foi possível enviar.",
      });
      return;
    }

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: request.message,
    };
    const controller = new AbortController();
    activeRequest.current = controller;
    inFlight.current = true;
    dispatch({
      type: "begin",
      pending: { conversationId, userMessage },
      now: new Date().toISOString(),
    });

    try {
      const response = await sendChatMessage(request, controller.signal);
      if (controller.signal.aborted) return;
      dispatch({
        type: "success",
        conversationId,
        requestId: userMessage.id,
        assistant: { id: crypto.randomUUID(), ...response.message },
        now: new Date().toISOString(),
      });
    } catch (cause) {
      if (controller.signal.aborted) return;
      dispatch({
        type: "failure",
        conversationId,
        requestId: userMessage.id,
        error: cause instanceof Error ? cause.message : "Não foi possível enviar. Tente novamente.",
      });
    } finally {
      inFlight.current = false;
    }
  }

  return {
    conversations: state.session?.conversations ?? [],
    activeConversation: conversation,
    pendingConversationId: state.pending?.conversationId ?? null,
    isReady: state.session !== null,
    storageWarning: state.storageWarning,
    messages,
    draft: isSending ? "" : conversation?.draft ?? "",
    setDraft,
    isSending,
    isWaitingForOtherConversation: Boolean(state.pending && !isSending),
    error: conversation ? state.errors[conversation.id] || null : null,
    historyError: conversation ? getHistoryError(conversation.messages) : null,
    sendMessage,
    startNewConversation,
    selectConversation,
  };
}
