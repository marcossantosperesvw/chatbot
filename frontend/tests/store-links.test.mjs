import assert from "node:assert/strict";
import { afterEach, mock, test } from "node:test";
import cases from "../../shared/trusted-store-cases.json" with { type: "json" };
import { trustedStore, splitStoreLinks } from "../src/lib/store-links.ts";
import { sendChatMessage } from "../src/lib/api.ts";
import { loadConversationSession, saveConversationSession } from "../src/lib/conversation-storage.ts";
import { createChatRequest } from "../src/lib/chat.ts";

const URL = "https://store.steampowered.com/app/42/test/";
const link = { store: "Steam", url: URL };
const A = "550e8400-e29b-41d4-a716-446655440001";
const M = "550e8400-e29b-41d4-a716-446655440002";

afterEach(() => mock.restoreAll());

for (const item of cases) test(`política compartilhada: ${item.url}`, () => {
  assert.equal(trustedStore(item.url), item.store);
});

test("transforma apenas URLs autorizadas, preservando texto e pontuação", () => {
  const text = `Compre aqui: ${URL}. Fonte: https://www.igdb.com/games/test`;
  const parts = splitStoreLinks(text, [link]);
  assert.equal(parts.map((part) => part.text).join(""), text);
  assert.deepEqual(parts.filter((part) => part.href), [{ text: URL, href: URL }]);
  assert.equal(splitStoreLinks(URL).some((part) => part.href), false);
  assert.equal(splitStoreLinks("https://evil.example/test", [{ store: "Steam", url: "https://evil.example/test" }]).some((part) => part.href), false);
  assert.equal(splitStoreLinks(URL, [{ store:"Outra loja", url:URL }]).some((part) => part.href), false);
});

test("API rejeita links ou rótulos adulterados", async () => {
  const request = { conversation_id:A, message:"Onde comprar?", history:[] };
  for (const links of [[{ store:"Steam", url:"https://evil.example/test" }], [{ store:"Outra", url:URL }], null]) {
    mock.method(globalThis, "fetch", async () => Response.json({ conversation_id:A,
      message:{ role:"assistant", content:URL, store_links:links } }));
    await assert.rejects(sendChatMessage(request), /inválida/);
    mock.restoreAll();
  }
});

test("sessão preserva links aprovados e remove anexos inválidos sem perder mensagens", () => {
  const now = new Date().toISOString();
  for (const store_links of [[link], [{ store:"Steam", url:"https://evil.example/test" }]]) {
    const session = { version:1, activeConversationId:A, conversations:[{ id:A, title:"Teste", draft:"",
      createdAt:now, updatedAt:now, messages:[{ id:M, role:"assistant", content:URL, store_links }] }] };
    let saved;
    const storage = () => ({ getItem:()=>saved, setItem(key, value) { saved=value; } });
    saveConversationSession(session, storage);
    const restored = loadConversationSession(storage).session.conversations[0].messages[0];
    assert.equal(restored.content, URL);
    assert.equal(restored.store_links?.length ?? 0, store_links[0].url === URL ? 1 : 0);
    assert.deepEqual(createChatRequest(A, "Continue", [restored]).history, [{ role:"assistant", content:URL }]);
  }
});
