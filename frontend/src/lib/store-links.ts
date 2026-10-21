import policy from "../../../shared/trusted-stores.json" with { type: "json" };
import type { StoreLink } from "../types/chat.ts";

export function trustedStore(value: unknown): string | null {
  if (typeof value !== "string" || !value.startsWith("https://") || value.length > 2000 ||
    /[^\x21-\x7e]|[\\%<>"'`]/.test(value)) return null;
  try {
    const url = new URL(value);
    // Verificar a autoridade original: URL() normaliza porta padrão e segmentos.
    const authority = value.slice(8).split(/[/?#]/, 1)[0];
    const originalPath = value.slice(8 + authority.length).split(/[?#]/, 1)[0] || "/";
    if (authority.toLowerCase() !== url.hostname || value.includes("#") ||
        originalPath.split("/").some((part) => part === "." || part === "..")) return null;
    for (const store of policy.stores) {
      if (!store.hosts.includes(url.hostname) || !new RegExp(store.path).test(url.pathname)) continue;
      const entries = Array.from(url.searchParams.entries());
      const query = store.query as Record<string, string>;
      if (new Set(entries.map(([key]) => key)).size !== entries.length) return null;
      if (entries.some(([key, val]) => !Object.hasOwn(query, key) || !new RegExp(query[key]).test(val))) return null;
      // URLSearchParams aceita pares sem '='; o backend os recusa.
      if (url.search && url.search.slice(1).split("&").some((pair) => !pair.includes("="))) return null;
      return store.name;
    }
  } catch { /* Destino inválido permanece texto simples. */ }
  return null;
}

export function isStoreLink(value: unknown): value is StoreLink {
  if (typeof value !== "object" || value === null) return false;
  const item = value as Record<string, unknown>;
  return typeof item.store === "string" && trustedStore(item.url) === item.store;
}

export function isStoreLinkList(value: unknown): value is StoreLink[] | undefined {
  return value === undefined || (Array.isArray(value) && value.length <= 20 && value.every(isStoreLink));
}

export function splitStoreLinks(content: string, links: StoreLink[] = []) {
  const allowed = new Set(links.filter(isStoreLink).map((link) => link.url));
  const parts: { text: string; href?: string }[] = [];
  let offset = 0;
  for (const match of content.matchAll(/https?:\/\/[^\s<>"']+/gi)) {
    const raw = match[0];
    const url = allowed.has(raw) ? raw : raw.replace(/[.,;:!?)\]}]+$/, "");
    parts.push({ text: content.slice(offset, match.index) });
    if (allowed.has(url)) {
      parts.push({ text: url, href: url }, { text: raw.slice(url.length) });
    } else parts.push({ text: raw });
    offset = match.index + raw.length;
  }
  parts.push({ text: content.slice(offset) });
  return parts;
}
