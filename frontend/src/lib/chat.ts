import type { ChatRequest, HistoryMessage } from "@/types/chat";

export const MAX_MESSAGE_LENGTH = 4000;
export const MAX_HISTORY_LENGTH = 50;

export function countCharacters(text: string): number {
  // Python conta pontos de código Unicode, enquanto string.length conta UTF-16.
  return Array.from(text).length;
}

export function getHistoryError(history: HistoryMessage[]): string | null {
  if (history.length > MAX_HISTORY_LENGTH) {
    return "Esta conversa atingiu o limite de histórico. Inicie uma nova conversa para continuar.";
  }

  if (
    history.some(
      ({ content }) => countCharacters(content.trim()) > MAX_MESSAGE_LENGTH,
    )
  ) {
    return "Uma resposta ultrapassou o limite aceito no histórico. Inicie uma nova conversa para continuar.";
  }

  return null;
}

export function createChatRequest(
  conversationId: string,
  message: string,
  history: HistoryMessage[],
): ChatRequest {
  const content = message.trim();

  if (!content) {
    throw new Error("Escreva uma mensagem antes de enviar.");
  }

  if (countCharacters(content) > MAX_MESSAGE_LENGTH) {
    throw new Error("Sua mensagem pode ter até 4.000 caracteres.");
  }

  const historyError = getHistoryError(history);
  if (historyError) {
    throw new Error(historyError);
  }

  return {
    conversation_id: conversationId,
    message: content,
    // IDs e outros dados da interface não fazem parte do contrato do backend.
    history: history.map(({ role, content }) => ({ role, content: content.trim() })),
  };
}
