import type { Conversation } from "@/types/chat";

interface ConversationSidebarProps {
  conversations: Conversation[];
  activeConversationId?: string;
  pendingConversationId: string | null;
  isOpen: boolean;
  onSelect: (id: string) => void;
}

export function ConversationSidebar({
  conversations,
  activeConversationId,
  pendingConversationId,
  isOpen,
  onSelect,
}: ConversationSidebarProps) {
  const ordered = [...conversations].sort(
    (a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt),
  );

  return (
    <aside
      id="conversation-sidebar"
      aria-label="Conversas da sessão"
      className={`${isOpen ? "flex" : "hidden"} max-h-64 shrink-0 flex-col border-b border-slate-800 bg-slate-950/40 md:flex md:max-h-none md:w-64 md:border-r md:border-b-0`}
    >
      <div className="flex items-center justify-between px-4 py-5">
        <h2 className="text-sm font-medium text-slate-200">Conversas da sessão</h2>
        <span className="text-xs text-slate-400">{conversations.length}</span>
      </div>
      <nav aria-label="Selecionar conversa" className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        <ul className="flex flex-col gap-1">
          {ordered.map((conversation) => {
            const isActive = conversation.id === activeConversationId;
            const isPending = conversation.id === pendingConversationId;
            const count = conversation.messages.length;
            return (
              <li key={conversation.id}>
                <button
                  type="button"
                  aria-current={isActive ? "true" : undefined}
                  aria-label={`Abrir conversa: ${conversation.title}`}
                  title={conversation.title}
                  onClick={() => onSelect(conversation.id)}
                  className={`w-full rounded-xl border px-3 py-3 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-300 ${isActive ? "border-indigo-400/30 bg-indigo-500/15 text-indigo-100" : "border-transparent text-slate-300 hover:bg-slate-800/60"}`}
                >
                  <span className="block truncate text-sm font-medium">{conversation.title}</span>
                  <span className={`mt-1 block text-xs ${isPending ? "text-indigo-300" : "text-slate-400"}`}>
                    {isPending ? "Aguardando resposta…" : `${count} ${count === 1 ? "mensagem" : "mensagens"}`}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </nav>
      <p className="hidden px-4 py-4 text-xs leading-5 text-slate-500 md:block">
        Seu histórico fica nesta aba durante a sessão.
      </p>
    </aside>
  );
}
