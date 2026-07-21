import { useEffect, useState } from "react";
import { FileText, Trash2 } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { PostCard } from "../components/PostCard";
import { api } from "../lib/api";
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
    api.bookmarks().then((page) => {
      setPosts(page.items);
      setState(page.items.length ? "ready" : "empty");
    }).catch(() => setState("error"));
  }, [user]);

  if (!user) return <LoginPrompt title="Закладки" text="Войдите, чтобы открыть закладки" />;
  return <AppShell title="Закладки"><section className="list-page"><h1>Закладки</h1>{state === "loading" ? <div className="card-state">Загружаем закладки…</div> : state === "empty" ? <div className="card-state"><b>Закладок пока нет</b><span>Сохраняйте интересные публикации, чтобы вернуться к ним позже.</span></div> : state === "error" ? <div className="card-state">Не удалось загрузить закладки</div> : posts.map((post) => <PostCard key={post.id} post={post} onLike={() => {}} onBookmark={() => {}} />)}</section></AppShell>;
}

export function DraftsPage() {
  const { user } = useSession();
  const [drafts, setDrafts] = useState([]);
  const [state, setState] = useState("loading");
  const { navigate } = useRouter();

  const load = () => api.drafts().then((page) => {
    setDrafts(page.items);
    setState(page.items.length ? "ready" : "empty");
  }).catch(() => setState("error"));

  useEffect(() => { if (user) load(); }, [user]);
  const remove = async (id) => { await api.deleteDraft(id); load(); };
  const publish = async (id) => { const post = await api.publishDraft(id); navigate(`/posts/${post.id}`); };

  if (!user) return <LoginPrompt title="Черновики" text="Войдите, чтобы открыть черновики" />;
  return <AppShell title="Черновики"><section className="list-page"><h1>Черновики</h1>{state === "loading" ? <div className="card-state">Загружаем черновики…</div> : state === "empty" ? <div className="card-state"><b>Черновиков пока нет</b><span>Сохраните публикацию, чтобы закончить её позже.</span></div> : state === "error" ? <div className="card-state">Не удалось загрузить черновики</div> : <div className="draft-list">{drafts.map((draft) => <article className="draft-card" key={draft.id}><span className="draft-icon"><FileText size={20} /></span><div><b>{draft.title || "Без названия"}</b><p>{draft.content || "Черновик без текста"}</p><small>Изменён {new Date(draft.updated_at).toLocaleDateString("ru-RU")}</small></div><footer><button className="outline-button" onClick={() => remove(draft.id)} aria-label="Удалить черновик"><Trash2 size={16} /></button><button className="primary" onClick={() => publish(draft.id)}>Опубликовать</button></footer></article>)}</div>}</section></AppShell>;
}
