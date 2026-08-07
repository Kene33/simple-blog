import assert from "node:assert/strict";
import { mergeUniqueMessages } from "./messagesSocket.js";

const first = { id: "1", body: "hello" };
assert.equal(mergeUniqueMessages([first], first).length, 1);
assert.equal(mergeUniqueMessages([], { id: "2", client_id: "c1" }).length, 1);
assert.equal(mergeUniqueMessages([{ id: "old", client_id: "c1" }], { id: "new", client_id: "c1" }).length, 1);
console.log("messages checks passed");
