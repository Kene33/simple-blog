import assert from "node:assert/strict";
import { validatePostFiles } from "./postFiles.js";

const image = { type: "image/png", size: 1024 };
const video = { type: "video/mp4", size: 1024 };

assert.equal(validatePostFiles([{ kind: "image" }], [image, image], [image, image]).error, "К публикации можно добавить до 4 файлов.");
assert.equal(validatePostFiles([{ kind: "video" }], [], [video]).error, "К публикации можно добавить только одно видео.");
assert.equal(validatePostFiles([], [], [{ type: "image/heic", size: 1024 }]).error, "Поддерживаются JPG, PNG, GIF, WebP, MP4 и WebM.");
assert.equal(validatePostFiles([], [], [image]).files.length, 1);
