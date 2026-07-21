const ALLOWED_TYPES = new Set(["image/jpeg", "image/png", "image/gif", "image/webp", "video/mp4", "video/webm"]);

export function validatePostFiles(existingMedia, currentFiles, selectedFiles) {
  const next = [...currentFiles, ...Array.from(selectedFiles)];
  const total = existingMedia.length + next.length;
  if (total > 4) return { error: "К публикации можно добавить до 4 файлов.", files: currentFiles };
  if (next.some((file) => !ALLOWED_TYPES.has(file.type))) return { error: "Поддерживаются JPG, PNG, GIF, WebP, MP4 и WebM.", files: currentFiles };
  if (existingMedia.filter((media) => media.kind === "video").length + next.filter((file) => file.type.startsWith("video/")).length > 1) return { error: "К публикации можно добавить только одно видео.", files: currentFiles };
  if (next.some((file) => file.size > (file.type.startsWith("video/") ? 100 : 10) * 1024 * 1024)) return { error: "Один из файлов превышает допустимый размер.", files: currentFiles };
  return { error: "", files: next };
}
