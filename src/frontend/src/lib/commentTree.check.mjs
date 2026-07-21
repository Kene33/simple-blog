import assert from "node:assert/strict";
import { groupComments, mergeComments } from "./commentTree.js";

const root = { id: "root", parent_id: null };
const reply = { id: "reply", parent_id: "root" };
const nestedReply = { id: "nested", parent_id: "reply" };
const groups = groupComments([root, reply, nestedReply]);

assert.deepEqual(groups.get(null), [root]);
assert.deepEqual(groups.get("root"), [reply]);
assert.deepEqual(groups.get("reply"), [nestedReply]);
assert.deepEqual(mergeComments([root, reply], [reply, nestedReply]).map((comment) => comment.id), ["root", "reply", "nested"]);

console.log("comment tree checks passed");
