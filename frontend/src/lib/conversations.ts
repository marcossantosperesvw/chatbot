import type { ChatMessage, Conversation, ConversationSession } from "@/types/chat";

export interface PendingSend {
  conversationId: string;
  userMessage: ChatMessage;
}

export interface ConversationsState {
  session: ConversationSession | null;
  pending: PendingSend | null;
  errors: Record<string, string>;
  storageWarning: string | null;
}

export const initialConversationsState: ConversationsState = {
  session: null,
  pending: null,
  errors: {},
  storageWarning: null,
};

type Action =
  | { type: "restore"; session: ConversationSession; warning: string | null }
  | { type: "create"; conversation: Conversation }
  | { type: "select"; conversationId: string }
  | { type: "draft"; conversationId: string; draft: string; now: string }
  | { type: "begin"; pending: PendingSend; now: string }
  | { type: "success"; conversationId: string; requestId: string; assistant: ChatMessage; now: string }
  | { type: "failure"; conversationId: string; requestId: string; error: string }
  | { type: "error"; conversationId: string; error: string }
  | { type: "storage-warning"; warning: string | null };

export function createConversation(id: string, now: string): Conversation {
  return { id, title: "Nova conversa", messages: [], draft: "", createdAt: now, updatedAt: now };
}

function titleFromMessage(content: string): string {
  const title = content.trim().replace(/\s+/g, " ");
  const characters = Array.from(title);
  return characters.length > 60 ? `${characters.slice(0, 59).join("")}…` : title;
}

export function conversationsReducer(
  state: ConversationsState,
  action: Action,
): ConversationsState {
  if (action.type === "restore") {
    // O Strict Mode pode executar a inicialização novamente em desenvolvimento.
    return state.session ? state : { ...state, session: action.session, storageWarning: action.warning };
  }
  if (action.type === "storage-warning") {
    return action.warning === state.storageWarning
      ? state
      : { ...state, storageWarning: action.warning };
  }

  const session = state.session;
  if (!session) return state;

  switch (action.type) {
    case "create":
      if (session.conversations.some(({ id }) => id === action.conversation.id)) return state;
      return {
        ...state,
        session: {
          ...session,
          conversations: [action.conversation, ...session.conversations],
          activeConversationId: action.conversation.id,
        },
      };
    case "select":
      if (
        session.activeConversationId === action.conversationId ||
        !session.conversations.some(({ id }) => id === action.conversationId)
      ) return state;
      return { ...state, session: { ...session, activeConversationId: action.conversationId } };
    case "draft":
      if (state.pending?.conversationId === action.conversationId) return state;
      return {
        ...state,
        session: {
          ...session,
          conversations: session.conversations.map((conversation) =>
            conversation.id === action.conversationId
              ? { ...conversation, draft: action.draft, updatedAt: action.now }
              : conversation,
          ),
        },
      };
    case "begin":
      if (state.pending || !session.conversations.some(({ id }) => id === action.pending.conversationId)) return state;
      return {
        ...state,
        pending: action.pending,
        errors: { ...state.errors, [action.pending.conversationId]: "" },
        session: {
          ...session,
          conversations: session.conversations.map((conversation) =>
            conversation.id === action.pending.conversationId
              ? {
                  ...conversation,
                  title: conversation.messages.length ? conversation.title : titleFromMessage(action.pending.userMessage.content),
                  updatedAt: action.now,
                }
              : conversation,
          ),
        },
      };
    case "success":
    case "failure": {
      const pending = state.pending;
      if (!pending || pending.conversationId !== action.conversationId || pending.userMessage.id !== action.requestId) return state;
      if (action.type === "failure") {
        // O rascunho original ficou na conversa; não é necessário reconstruí-lo.
        return { ...state, pending: null, errors: { ...state.errors, [action.conversationId]: action.error } };
      }
      return {
        ...state,
        pending: null,
        session: {
          ...session,
          conversations: session.conversations.map((conversation) =>
            conversation.id === action.conversationId
              ? {
                  ...conversation,
                  messages: [...conversation.messages, pending.userMessage, action.assistant],
                  draft: "",
                  updatedAt: action.now,
                }
              : conversation,
          ),
        },
      };
    }
    case "error":
      return { ...state, errors: { ...state.errors, [action.conversationId]: action.error } };
  }
}
