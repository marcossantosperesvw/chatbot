import type { ChatMessage, Conversation, ConversationSession } from "@/types/chat";
import { copyVideo, isVideoCurrent, isVideoList } from "./videos.ts";

export const CONVERSATION_STORAGE_KEY = "chat-jogos:session:v1";

type StorageAccess = () => Pick<Storage, "getItem" | "setItem">;

interface LoadResult {
  session: ConversationSession | null;
  warning: string | null;
  canPersist: boolean;
}

const UNAVAILABLE_WARNING =
  "O armazenamento da sessão está indisponível. As conversas ficarão apenas em memória e poderão ser perdidas ao atualizar a página.";
const INVALID_WARNING =
  "Não foi possível recuperar os dados salvos. Eles foram preservados; as novas conversas ficarão apenas em memória nesta aba.";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isId(value: unknown): value is string {
  return typeof value === "string" && /^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$/i.test(value);
}

function isDate(value: unknown): value is string {
  return typeof value === "string" && Number.isFinite(Date.parse(value));
}

function isMessage(value: unknown): value is ChatMessage {
  return isRecord(value) && isId(value.id) &&
    (value.role === "user" || value.role === "assistant") &&
    typeof value.content === "string" && value.content.trim().length > 0;
}

function isConversation(value: unknown): value is Conversation {
  if (!isRecord(value)) return false;
  return isId(value.id) &&
    typeof value.title === "string" && value.title.trim().length > 0 &&
    Array.from(value.title).length <= 60 &&
    typeof value.draft === "string" && isDate(value.createdAt) && isDate(value.updatedAt) &&
    Array.isArray(value.messages) && value.messages.every(isMessage) &&
    new Set(value.messages.map(({ id }) => id)).size === value.messages.length;
}

function isSession(value: unknown): value is ConversationSession {
  if (!isRecord(value) || value.version !== 1 || !Array.isArray(value.conversations)) return false;
  return value.conversations.length > 0 && value.conversations.every(isConversation) &&
    new Set(value.conversations.map(({ id }) => id)).size === value.conversations.length &&
    value.conversations.some(({ id }) => id === value.activeConversationId);
}

export function loadConversationSession(
  getStorage: StorageAccess = () => window.sessionStorage,
): LoadResult {
  let raw: string | null;
  try {
    raw = getStorage().getItem(CONVERSATION_STORAGE_KEY);
  } catch {
    return { session: null, warning: UNAVAILABLE_WARNING, canPersist: false };
  }
  if (raw === null) return { session: null, warning: null, canPersist: true };

  try {
    const data: unknown = JSON.parse(raw);
    if (isSession(data)) {
      // Copia somente campos conhecidos. Estados de envio e erros não são restaurados.
      const session: ConversationSession = {
        version: 1,
        activeConversationId: data.activeConversationId,
        conversations: data.conversations.map((conversation) => ({
          id: conversation.id,
          title: conversation.title,
          draft: conversation.draft,
          createdAt: conversation.createdAt,
          updatedAt: conversation.updatedAt,
          messages: conversation.messages.map(({ id, role, content, videos }) => ({
            id, role, content,
            ...(role === "assistant" && isVideoList(videos) && videos?.length
              ? { videos: videos.filter((video) => isVideoCurrent(video)).map(copyVideo) }
              : {}),
          })),
        })),
      };
      return { session, warning: null, canPersist: true };
    }
  } catch {
    // Dados inválidos ou de uma versão desconhecida não são sobrescritos.
  }
  return { session: null, warning: INVALID_WARNING, canPersist: false };
}

export function saveConversationSession(
  session: ConversationSession,
  getStorage: StorageAccess = () => window.sessionStorage,
): string | null {
  try {
    const sanitized = { ...session, conversations: session.conversations.map((conversation) => ({
      ...conversation, messages: conversation.messages.map((message) => {
        if (message.videos === undefined) return message;
        return { ...message, videos: message.role === "assistant" && isVideoList(message.videos)
          ? (message.videos ?? []).filter((video) => isVideoCurrent(video)).map(copyVideo) : [] };
      }),
    })) };
    getStorage().setItem(CONVERSATION_STORAGE_KEY, JSON.stringify(sanitized));
    return null;
  } catch {
    return "Não foi possível salvar a sessão. As conversas continuam em memória; evite atualizar a página para não perder alterações.";
  }
}
