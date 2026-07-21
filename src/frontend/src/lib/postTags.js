export function parsePostTags(value) {
  const tags = value.split(",").map((tag) => tag.trim().toLowerCase()).filter(Boolean);
  if (tags.length > 10) return { error: "Можно добавить до 10 тегов.", tags: [] };
  if (tags.some((tag) => tag.length > 30)) return { error: "Тег должен быть до 30 символов.", tags: [] };
  if (new Set(tags).size !== tags.length) return { error: "Теги не должны повторяться.", tags: [] };
  return { error: "", tags };
}
