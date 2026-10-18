import type { ChatRequest, ChatResponse } from "@/types/chat";

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

function isChatResponse(value: unknown): value is ChatResponse {
  if (typeof value !== "object" || value === null) return false;
  if (!("conversation_id" in value) || !("message" in value)) return false;

  const message = value.message;
  return (
    typeof value.conversation_id === "string" &&
    typeof message === "object" &&
    message !== null &&
    "role" in message &&
    message.role === "assistant" &&
    "content" in message &&
    typeof message.content === "string" &&
    message.content.trim().length > 0
  );
}

export async function sendChatMessage(
  request: ChatRequest,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  const timeout = AbortSignal.timeout(30_000);
  const requestSignal = signal ? AbortSignal.any([signal, timeout]) : timeout;
  let response: Response;

  try {
    response = await fetch(`${API_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal: requestSignal,
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    if (timeout.aborted) {
      throw new Error("O servidor demorou para responder. Tente novamente.");
    }
    throw new Error(
      "Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente.",
    );
  }

  if (!response.ok) {
    if (response.status === 422) {
      throw new Error(
        "A mensagem ou o histórico não atende aos limites do chat. Revise o texto ou inicie uma nova conversa.",
      );
    }
    throw new Error("Não foi possível processar a mensagem. Tente novamente.");
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new Error("O servidor retornou uma resposta inválida. Tente novamente.");
  }

  if (!isChatResponse(data) || data.conversation_id !== request.conversation_id) {
    throw new Error("O servidor retornou uma resposta inválida. Tente novamente.");
  }

  return data;
}
