import assert from "node:assert/strict";
import { parsePostTags } from "./postTags.js";

assert.deepEqual(parsePostTags("Design, product").tags, ["design", "product"]);
assert.equal(parsePostTags("one, one").error, "Теги не должны повторяться.");
assert.equal(parsePostTags("a,b,c,d,e,f,g,h,i,j,k").error, "Можно добавить до 10 тегов.");
assert.equal(parsePostTags("abcdefghijklmnopqrstuvwxyzabcde").error, "Тег должен быть до 30 символов.");
