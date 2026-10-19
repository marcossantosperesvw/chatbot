export type MessageRole = "user" | "assistant";

export interface HistoryMessage {
  role: MessageRole;
  content: string;
}

export interface ChatMessage extends HistoryMessage {
  id: string;
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  draft: string;
  createdAt: string;
  updatedAt: string;
}

export interface ConversationSession {
  version: 1;
  conversations: Conversation[];
  activeConversationId: string;
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
