import { useEffect, useState } from "react";
import { ChevronDown, ImagePlus, RefreshCw, SlidersHorizontal } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { PostCard } from "../components/PostCard";
import { RightRail } from "../components/RightRail";
import { useRouter } from "../lib/router";
import { api } from "../lib/api";
import { useSession } from "../session";

const tabs = ["Для вас", "Новое", "Технологии", "Дизайн", "Культура"];

export function FeedPage() {
  const [posts, setPosts] = useState([]); const [cursor, setCursor] = useState(null); const [state, setState] = useState("loading"); const [tab, setTab] = useState("Для вас");
  const { user } = useSession(); const { navigate } = useRouter();
  const category = ["Технологии", "Дизайн", "Культура"].includes(tab) ? tab.toLowerCase() : undefined;
  async function load(more = false) { setState(more ? "loading-more" : "loading"); try { const page = await api.posts({ category, sort: tab === "Новое" ? "newest" : undefined, cursor: more ? cursor : undefined, limit: 10 }); setPosts((old) => more ? [...old, ...page.items] : page.items); setCursor(page.next_cursor); setState(page.items.length || more ? "ready" : "empty"); } catch { setState("error"); } }
  useEffect(() => { load(); }, [tab]);
  const toggle = async (post, kind) => { if (!user) return navigate("/login"); const before = { ...post }; const next = kind === "like" ? { ...post, liked_by_me: !post.liked_by_me, like_count: post.like_count + (post.liked_by_me ? -1 : 1) } : { ...post, bookmarked_by_me: !post.bookmarked_by_me }; setPosts((items) => items.map((item) => item.id === post.id ? next : item)); try { if (kind === "like") post.liked_by_me ? await api.unlike(post.id) : await api.like(post.id); else post.bookmarked_by_me ? await api.unbookmark(post.id) : await api.bookmark(post.id); } catch { setPosts((items) => items.map((item) => item.id === post.id ? before : item)); } };
  const share = async (post) => { const url = `${window.location.origin}/posts/${post.id}`; const channel = navigator.share ? "native" : "copy"; try { if (channel === "native") await navigator.share({ title: post.title, text: post.content, url }); else await navigator.clipboard.writeText(url); const result = await api.share(post.id, channel); setPosts((items) => items.map((item) => item.id === post.id ? { ...item, share_count: result.share_count } : item)); } catch (cause) { if (cause.name !== "AbortError") console.error("Не удалось поделиться публикацией", cause); } };
  return <AppShell title="Лента" right={<RightRail />}><section className="feed-page"><header className="page-title"><div><h1>Лента</h1><p>Идеи и обсуждения сообщества</p></div><button className="round-button" onClick={() => load()} aria-label="Обновить ленту"><RefreshCw size={20} /></button></header>
    {user && <button className="composer" onClick={() => navigate("/posts/new")}><span className="avatar">{user.username.slice(0, 2).toUpperCase()}</span><span>О чём вы думаете?</span><i><ImagePlus size={20} /></i></button>}
    <div className="filter-tabs">{tabs.map((name) => <button className={tab === name ? "selected" : ""} onClick={() => setTab(name)} key={name}>{name}</button>)}</div><button className="filter-toggle"><SlidersHorizontal size={18} /> Поиск и фильтры <b>2 активных</b><ChevronDown size={17} /></button>
    {state === "loading" && <div className="card-state">Загружаем публикации…</div>}{state === "error" && <div className="card-state"><b>Не удалось загрузить</b><button className="outline-button" onClick={() => load()}>Повторить</button></div>}{state === "empty" && <div className="card-state"><b>Ничего не найдено</b><span>Измените запрос или сбросьте активные фильтры.</span></div>}
    {posts.map((post) => <PostCard key={post.id} post={post} onLike={(post) => toggle(post, "like")} onBookmark={(post) => toggle(post, "bookmark")} onShare={share} />)}{cursor && <button className="outline-button load-more" disabled={state === "loading-more"} onClick={() => load(true)}>{state === "loading-more" ? "Загружаем…" : "Показать ещё"}</button>}
  </section></AppShell>;
}
