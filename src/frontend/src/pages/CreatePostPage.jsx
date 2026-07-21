import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Paperclip, X } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { api } from "../lib/api";
import { validatePostFiles } from "../lib/postFiles";
import { parsePostTags } from "../lib/postTags";
import { useRouter } from "../lib/router";
import { useSession } from "../session";
import "../styles/create-post.css";

const blank = { title: "", content: "", category: "", tags: "" };

export function CreatePostPage({ postId, draftId }) {
  const { user } = useSession();
  const { navigate } = useRouter();
  const fileInput = useRef(null);
  const [form, setForm] = useState(blank);
  const [files, setFiles] = useState([]);
  const [existingMedia, setExistingMedia] = useState([]);
  const [categories, setCategories] = useState(null);
  const [proposedCategory, setProposedCategory] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.categories().then((page) => {
      if (!cancelled) setCategories(Array.isArray(page) ? page : page.items || []);
    }).catch(() => {
      if (!cancelled) setCategories(null);
    });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!postId || !user) return;
    setBusy(true);
    api.post(postId).then((post) => {
      if (post.author.id !== user.id) throw new Error("Нет доступа к редактированию публикации");
      setForm({ title: post.title, content: post.content, category: post.category?.id || post.category, tags: post.tags.join(", ") });
      setExistingMedia(post.media);
    }).catch((cause) => setError(cause.message || "Публикация не найдена")).finally(() => setBusy(false));
  }, [postId, user?.id]);

  useEffect(() => {
    if (!draftId || !user) return;
    setBusy(true);
    api.draft(draftId).then((draft) => {
      setForm({ title: draft.title, content: draft.content, category: draft.category?.id || draft.category || "", tags: draft.tags.join(", ") });
      setExistingMedia(draft.media);
    }).catch((cause) => setError(cause.message || "Черновик не найден")).finally(() => setBusy(false));
  }, [draftId, user?.id]);

  const update = (key) => (event) => setForm((value) => ({ ...value, [key]: event.target.value }));
  const addFiles = (selected) => {
    const result = validatePostFiles(existingMedia, files, selected);
    setError(result.error);
    setFiles(result.files);
  };

  async function payload() {
    const parsed = parsePostTags(form.tags);
    if (parsed.error) throw new Error(parsed.error);
    const media = await Promise.all(files.map((file) => api.uploadMedia(file)));
    const data = { title: form.title.trim(), content: form.content.trim(), tags: parsed.tags, media_ids: [...existingMedia.map((item) => item.id), ...media.map((item) => item.id)] };

    if (!categories) return { ...data, category: form.category.trim() };
    if (form.category === "__new__") {
      const request = await api.requestCategory({ name: proposedCategory.trim() });
      return { ...data, category_request_id: request.id };
    }
    return { ...data, category_id: form.category };
  }

  async function submit(draft) {
    setBusy(true);
    setError("");
    try {
      const data = await payload();
      let result;
      if (postId) result = await api.updatePost(postId, data);
      else if (draftId) result = await api.updateDraft(draftId, data);
      else if (draft) result = await api.createDraft(data);
      else result = await api.createPost(data);
      navigate(draft || draftId || data.category_request_id ? "/drafts" : `/posts/${result.id}`);
    } catch (cause) {
      setError(cause.message || "Не удалось сохранить публикацию");
    } finally {
      setBusy(false);
    }
  }

  if (!user) return <AppShell title="Создать"><section className="guest-create"><div className="card-state"><b>Войдите, чтобы создать публикацию</b><button className="outline-button" onClick={() => navigate("/login")}>Войти</button></div></section></AppShell>;

  const usesCategoryCatalog = Array.isArray(categories);
  return <AppShell title={postId || draftId ? "Редактировать" : "Создать"}>
    <section className="create-page">
      <button className="back-link button-link" onClick={() => navigate(postId ? `/posts/${postId}` : draftId ? "/drafts" : "/")}><ArrowLeft size={17} /> Отмена</button>
      <h1>{postId || draftId ? "Редактирование публикации" : "Новая публикация"}</h1>
      <p>{postId || draftId ? "Обновите текст и вложения" : "Поделитесь идеей с сообществом"}</p>
      <form className="create-form" onSubmit={(event) => { event.preventDefault(); submit(false); }}>
        <label>Заголовок <small>обязательно</small><input value={form.title} onChange={update("title")} maxLength="200" required placeholder="О чём ваша публикация?" /></label>
        <label>Текст <small>обязательно</small><textarea value={form.content} onChange={update("content")} maxLength="10000" required placeholder="Расскажите больше…" /></label>
        <div className="create-grid">
          {usesCategoryCatalog ? <label>Категория<select value={form.category} onChange={update("category")} required><option value="">Выберите категорию</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}<option value="__new__">Предложить новую категорию</option></select></label> : <label>Категория<input value={form.category} onChange={update("category")} maxLength="50" required placeholder="Например, технологии" /><small>Справочник категорий появится после обновления backend.</small></label>}
          <label>Теги <small>через запятую</small><input value={form.tags} onChange={update("tags")} maxLength="300" placeholder="design, product" /></label>
        </div>
        {usesCategoryCatalog && form.category === "__new__" && <label className="proposed-category">Новая категория <small>Пост станет доступен после одобрения модератором.</small><input value={proposedCategory} onChange={(event) => setProposedCategory(event.target.value)} maxLength="50" required placeholder="Название категории" /></label>}
        <div className="attachments"><header><div><b>Вложения</b><small>До 4 файлов, максимум одно видео</small></div><button type="button" className="outline-button" onClick={() => fileInput.current.click()}><Paperclip size={18} /> Добавить файл</button></header><input ref={fileInput} className="visually-hidden" type="file" accept="image/*,video/*" multiple onChange={(event) => addFiles(event.target.files)} />{[...existingMedia, ...files].length > 0 && <div className="file-list">{existingMedia.map((media) => <div className="file-chip" key={media.id}><span>{media.kind === "video" ? "Видео" : "Фото"}</span><b>Текущее вложение</b><button type="button" onClick={() => setExistingMedia((items) => items.filter((item) => item.id !== media.id))} aria-label="Удалить файл"><X size={17} /></button></div>)}{files.map((file, index) => <div className="file-chip" key={`${file.name}-${index}`}><span>{file.type.startsWith("video/") ? "Видео" : "Фото"}</span><b>{file.name}</b><button type="button" onClick={() => setFiles((items) => items.filter((_, fileIndex) => fileIndex !== index))} aria-label="Удалить файл"><X size={17} /></button></div>)}</div>}</div>
        {error && <div className="form-error" role="alert">{error}</div>}
        <footer>{!postId && <button type="button" className="outline-button" disabled={busy} onClick={() => submit(true)}>Сохранить черновик</button>}<button className="primary" disabled={busy}>{busy ? "Сохраняем…" : postId || draftId ? "Сохранить изменения" : "Опубликовать"}</button></footer>
      </form>
    </section>
  </AppShell>;
}
