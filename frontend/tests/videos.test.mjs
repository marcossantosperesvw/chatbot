import assert from "node:assert/strict";
import { afterEach, mock, test } from "node:test";
import { isTutorialVideo, isVideoCurrent, videoUrls } from "../src/lib/videos.ts";
import { sendChatMessage } from "../src/lib/api.ts";
import { loadConversationSession, saveConversationSession } from "../src/lib/conversation-storage.ts";
import { createChatRequest } from "../src/lib/chat.ts";

const ID = "abcdefghijk";
const video = { video_id: ID, title: "Como instalar", channel: "Canal teste", retrieved_at: new Date().toISOString() };
const A = "550e8400-e29b-41d4-a716-446655440001";
const M = "550e8400-e29b-41d4-a716-446655440002";
const request = { conversation_id: A, message: "Como instalar?", history: [], include_videos: true };

afterEach(() => mock.restoreAll());

test("constrói URLs somente a partir de IDs seguros e desativa autoplay", () => {
  assert.equal(videoUrls(ID).watch, `https://www.youtube.com/watch?v=${ID}`);
  assert.match(videoUrls(ID).embed, /youtube-nocookie\.com\/embed\/abcdefghijk\?autoplay=0/);
  for (const id of ["../arquivo", "https://evil.test", '<script>', `${ID}?autoplay=1`]) {
    assert.throws(() => videoUrls(id), /inválido/);
    assert.equal(isTutorialVideo({ ...video, video_id: id }), false);
  }
});

test("API aceita anexo válido e rejeita metadados/quantidade inválidos", async () => {
  const reply = { conversation_id: A, message: { role: "assistant", content: "Tutorial", videos: [video] } };
  mock.method(globalThis, "fetch", async () => Response.json(reply));
  assert.deepEqual((await sendChatMessage(request)).message.videos, [video]);
  for (const videos of [[{ ...video, title: "" }], [{ ...video, video_id: "javascript:evil" }], [video, video], null, "html"]) {
    mock.restoreAll();
    mock.method(globalThis, "fetch", async () => Response.json({ ...reply, message: { ...reply.message, videos } }));
    await assert.rejects(sendChatMessage(request), /inválida/);
  }
});

test("recupera vídeos na sessão sem enviar anexos novamente ao modelo", () => {
  const message = { id: M, role: "assistant", content: "Tutorial", videos: [{ ...video, extra: "ignorar" }] };
  const session = { version: 1, activeConversationId: A, conversations: [
    { id: A, title: "Tutorial", messages: [message], draft: "", createdAt: video.retrieved_at, updatedAt: video.retrieved_at },
  ] };
  let saved;
  const storage = () => ({ setItem(key, value) { saved = value; }, getItem() { return saved; } });
  assert.equal(saveConversationSession(session, storage), null);
  const restored = loadConversationSession(storage).session.conversations[0].messages[0];
  assert.deepEqual(restored.videos, [video]);
  assert.deepEqual(createChatRequest(A, "Continue", [restored]).history, [{ role: "assistant", content: "Tutorial" }]);
});

test("metadados expirados ou adulterados são descartados sem perder o texto", () => {
  const old = { ...video, retrieved_at: "2000-01-01T00:00:00Z" };
  assert.equal(isVideoCurrent(old), false);
  for (const videos of [[old], [{ ...video, video_id: "../unsafe" }]]) {
    const session = { version: 1, activeConversationId: A, conversations: [
      { id: A, title: "Tutorial", messages: [{ id: M, role: "assistant", content: "Preservar", videos }], draft: "", createdAt: video.retrieved_at, updatedAt: video.retrieved_at },
    ] };
    const result = loadConversationSession(() => ({ getItem: () => JSON.stringify(session) }));
    assert.equal(result.canPersist, true);
    const message = result.session.conversations[0].messages[0];
    assert.equal(message.content, "Preservar");
    assert.equal(message.videos?.length ?? 0, 0);
  }
});
