import { useEffect, useState } from "react";
import { FileText, Pencil, Trash2 } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { PostCard } from "../components/PostCard";
import { api } from "../lib/api";
import { sharePost } from "../lib/sharePost";
import { useRouter } from "../lib/router";
import { useSession } from "../session";
import "../styles/list-pages.css";

function LoginPrompt({ title, text }) {
  const { navigate } = useRouter();
  return <AppShell title={title}><section className="list-page"><h1>{title}</h1><div className="card-state"><b>{text}</b><button className="outline-button" onClick={() => navigate("/login")}>Войти</button></div></section></AppShell>;
}

export function BookmarksPage() {
  const { user } = useSession();
  const [posts, setPosts] = useState([]);
  const [state, setState] = useState("loading");

  useEffect(() => {
    if (!user) return;
    setState("loading");
    api.bookmarks().then((page) => {
      setPosts(page.items);
      setState(page.items.length ? "ready" : "empty");
    }).catch(() => { setPosts([]); setState("error"); });
  }, [user]);
  const toggleLike = async (post) => { const before = { ...post }; const next = { ...post, liked_by_me: !post.liked_by_me, like_count: Math.max(0, post.like_count + (post.liked_by_me ? -1 : 1)) }; setPosts((items) => items.map((item) => item.id === post.id ? next : item)); try { post.liked_by_me ? await api.unlike(post.id) : await api.like(post.id); } catch { setPosts((items) => items.map((item) => item.id === post.id ? before : item)); } };
  const removeBookmark = async (post) => { const before = posts; setPosts((items) => items.filter((item) => item.id !== post.id)); try { await api.unbookmark(post.id); } catch { setPosts(before); } };
  const share = async (post) => { try { const result = await sharePost(post); setPosts((items) => items.map((item) => item.id === post.id ? { ...item, share_count: result.share_count } : item)); } catch { } };

  if (!user) return <LoginPrompt title="Закладки" text="Войдите, чтобы открыть закладки" />;
  return <AppShell title="Закладки"><section className="list-page"><h1>Закладки</h1>{state === "loading" ? <div className="card-state">Загружаем закладки…</div> : state === "empty" ? <div className="card-state"><b>Закладок пока нет</b><span>Сохраняйте интересные публикации, чтобы вернуться к ним позже.</span></div> : state === "error" ? <div className="card-state">Не удалось загрузить закладки</div> : posts.map((post) => <PostCard key={post.id} post={post} onLike={toggleLike} onBookmark={removeBookmark} onShare={share} />)}</section></AppShell>;
}

export function DraftsPage() {
  const { user } = useSession();
  const [drafts, setDrafts] = useState([]);
  const [state, setState] = useState("loading");
  const [busyDraft, setBusyDraft] = useState("");
  const [error, setError] = useState("");
  const { navigate } = useRouter();

  const load = () => { setState("loading"); return api.drafts().then((page) => {
    setDrafts(page.items);
    setState(page.items.length ? "ready" : "empty");
  }).catch(() => { setDrafts([]); setState("error"); }); };

  useEffect(() => { if (user) load(); }, [user]);
  const remove = async (id) => { setBusyDraft(id); setError(""); try { await api.deleteDraft(id); await load(); } catch (cause) { setError(cause.message || "Не удалось удалить черновик"); } finally { setBusyDraft(""); } };
  const publish = async (id) => { setBusyDraft(id); setError(""); try { const post = await api.publishDraft(id); navigate(`/posts/${post.id}`); } catch (cause) { setError(cause.message || "Не удалось опубликовать черновик"); setBusyDraft(""); } };

  if (!user) return <LoginPrompt title="Черновики" text="Войдите, чтобы открыть черновики" />;
  return <AppShell title="Черновики"><section className="list-page"><h1>Черновики</h1>{error && <div className="form-error" role="alert">{error}</div>}{state === "loading" ? <div className="card-state">Загружаем черновики…</div> : state === "empty" ? <div className="card-state"><b>Черновиков пока нет</b><span>Сохраните публикацию, чтобы закончить её позже.</span></div> : state === "error" ? <div className="card-state">Не удалось загрузить черновики</div> : <div className="draft-list">{drafts.map((draft) => <article className="draft-card" key={draft.id}><span className="draft-icon"><FileText size={20} /></span><div><b>{draft.title || "Без названия"}</b><p>{draft.content || "Черновик без текста"}</p><small>Изменён {new Date(draft.updated_at).toLocaleDateString("ru-RU")}</small></div><footer><button className="outline-button" disabled={busyDraft === draft.id} onClick={() => navigate(`/drafts/${draft.id}/edit`)} aria-label="Редактировать черновик"><Pencil size={16} /></button><button className="outline-button" disabled={busyDraft === draft.id} onClick={() => remove(draft.id)} aria-label="Удалить черновик"><Trash2 size={16} /></button><button className="primary" disabled={busyDraft === draft.id} onClick={() => publish(draft.id)}>{busyDraft === draft.id ? "Сохраняем…" : "Опубликовать"}</button></footer></article>)}</div>}</section></AppShell>;
}
