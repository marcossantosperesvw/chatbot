import assert from "node:assert/strict";
import test from "node:test";
import { countCharacters, createChatRequest, getHistoryError } from "../src/lib/chat.ts";

const id = "550e8400-e29b-41d4-a716-446655440000";

test("separa a mensagem atual do histórico e remove IDs locais sem alterar a origem", () => {
  const history = [{ id: "local-1", role: "user", content: "  Jogo no PC.  " }];
  assert.deepEqual(createChatRequest(id, "  Prefiro RPG.\n", history), {
    conversation_id: id,
    message: "Prefiro RPG.",
    history: [{ role: "user", content: "Jogo no PC." }],
  });
  assert.equal(history[0].content, "  Jogo no PC.  ");
});

test("rejeita mensagem vazia ou composta apenas por espaços", () => {
  for (const message of ["", "  \n\t"]) {
    assert.throws(() => createChatRequest(id, message, []), /Escreva/);
  }
});

test("conta emojis como o backend e aceita exatamente 4.000 caracteres", () => {
  const message = "🎮".repeat(4000);
  assert.equal(countCharacters(message), 4000);
  assert.equal(createChatRequest(id, message, []).message, message);
  assert.throws(() => createChatRequest(id, `${message}!`, []), /4.000 caracteres/);
});

test("aceita 50 mensagens anteriores e bloqueia excedentes sem descartar dados", () => {
  const history = Array.from({ length: 50 }, () => ({ role: "user", content: "Olá" }));
  assert.equal(createChatRequest(id, "Tudo bem?", history).history.length, 50);
  history.push({ role: "assistant", content: "Sim!" });
  assert.throws(() => createChatRequest(id, "Quais jogos?", history), /limite de histórico/);
  assert.equal(history.length, 51);
});

test("avisa quando uma resposta simulada longa não pode ser reenviada no histórico", () => {
  const history = [{ role: "assistant", content: "a".repeat(4001) }];
  assert.match(getHistoryError(history), /resposta ultrapassou/);
  assert.throws(() => createChatRequest(id, "Continue", history), /resposta ultrapassou/);
  assert.equal(history[0].content.length, 4001);
});

test("aceita histórico vazio e conteúdo anterior no limite", () => {
  assert.equal(getHistoryError([]), null);
  assert.equal(getHistoryError([{ role: "user", content: "a".repeat(4000) }]), null);
});
