export type MessageRole = "user" | "assistant";

export interface HistoryMessage {
  role: MessageRole;
  content: string;
}

export interface ChatMessage extends HistoryMessage {
  id: string;
}

export interface ChatRequest {
  conversation_id: string;
  message: string;
  history: HistoryMessage[];
}

export interface ChatResponse {
  conversation_id: string;
  message: {
    role: "assistant";
    content: string;
  };
}
