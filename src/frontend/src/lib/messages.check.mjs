import assert from "node:assert/strict";
import { mergeUniqueMessages, normalizeMessageEvent } from "./messagesSocket.js";

const first = { id: "1", body: "hello" };
assert.equal(mergeUniqueMessages([first], first).length, 1);
assert.equal(mergeUniqueMessages([], { id: "2", client_id: "c1" }).length, 1);
assert.equal(mergeUniqueMessages([{ id: "old", client_id: "c1" }], { id: "new", client_id: "c1" }).length, 1);
assert.equal(normalizeMessageEvent({ type: "message.created", data: { id: "3", conversation_id: "c1", body: "hi" } }).message.id, "3");
assert.equal(normalizeMessageEvent({ type: "message.read", data: { conversation_id: "c1", message_id: "3" } }).message_id, "3");
console.log("messages checks passed");
