import { useEffect, useState } from "react";
import { ChevronDown, ImagePlus, RefreshCw, SlidersHorizontal } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { PostCard } from "../components/PostCard";
import { RightRail } from "../components/RightRail";
import { useRouter } from "../lib/router";
import { api } from "../lib/api";
import { sharePost } from "../lib/sharePost";
import { useSession } from "../session";

const tabs = ["Для вас", "Новое", "Технологии", "Дизайн", "Культура"];

export function FeedPage() {
  const [posts, setPosts] = useState([]); const [cursor, setCursor] = useState(null); const [state, setState] = useState("loading"); const [tab, setTab] = useState("Для вас"); const [filtersOpen, setFiltersOpen] = useState(false); const [filters, setFilters] = useState({ query: "", tag: "", author: "", sort: "newest" });
  const { user } = useSession(); const { navigate } = useRouter();
  const category = ["Технологии", "Дизайн", "Культура"].includes(tab) ? tab.toLowerCase() : undefined;
  const activeCount = [category, filters.query, filters.tag, filters.author, filters.sort !== "newest" ? filters.sort : ""].filter(Boolean).length;
  async function load(more = false) { setState(more ? "loading-more" : "loading"); try { const page = await api.posts({ category, query: filters.query.trim(), tag: filters.tag.trim(), author: filters.author.trim(), sort: tab === "Новое" ? "newest" : filters.sort, cursor: more ? cursor : undefined, limit: 10 }); setPosts((old) => more ? [...old, ...page.items] : page.items); setCursor(page.next_cursor); setState(page.items.length || more ? "ready" : "empty"); } catch { if (!more) { setPosts([]); setCursor(null); } setState("error"); } }
  useEffect(() => { let cancelled = false; setState("loading"); api.posts({ category, query: filters.query.trim(), tag: filters.tag.trim(), author: filters.author.trim(), sort: tab === "Новое" ? "newest" : filters.sort, limit: 10 }).then((page) => { if (cancelled) return; setPosts(page.items); setCursor(page.next_cursor); setState(page.items.length ? "ready" : "empty"); }).catch(() => { if (cancelled) return; setPosts([]); setCursor(null); setState("error"); }); return () => { cancelled = true; }; }, [tab, filters]);
  const updateFilter = (key) => (event) => setFilters((value) => ({ ...value, [key]: event.target.value }));
  const resetFilters = () => setFilters({ query: "", tag: "", author: "", sort: "newest" });
  const toggle = async (post, kind) => { if (!user) return navigate("/login"); const before = { ...post }; const next = kind === "like" ? { ...post, liked_by_me: !post.liked_by_me, like_count: post.like_count + (post.liked_by_me ? -1 : 1) } : { ...post, bookmarked_by_me: !post.bookmarked_by_me }; setPosts((items) => items.map((item) => item.id === post.id ? next : item)); try { if (kind === "like") post.liked_by_me ? await api.unlike(post.id) : await api.like(post.id); else post.bookmarked_by_me ? await api.unbookmark(post.id) : await api.bookmark(post.id); } catch { setPosts((items) => items.map((item) => item.id === post.id ? before : item)); } };
  const share = async (post) => { try { const result = await sharePost(post); setPosts((items) => items.map((item) => item.id === post.id ? { ...item, share_count: result.share_count } : item)); } catch (cause) { if (cause.name !== "AbortError") console.error("Не удалось поделиться публикацией", cause); } };
  return <AppShell title="Лента" right={<RightRail />}><section className="feed-page"><header className="page-title"><div><h1>Лента</h1><p>Идеи и обсуждения сообщества</p></div><button className="round-button" onClick={() => load()} aria-label="Обновить ленту"><RefreshCw size={20} /></button></header>
    {user && <button className="composer" onClick={() => navigate("/posts/new")}><span className="avatar">{user.username.slice(0, 2).toUpperCase()}</span><span>О чём вы думаете?</span><i><ImagePlus size={20} /></i></button>}
    <div className="filter-tabs">{tabs.map((name) => <button className={tab === name ? "selected" : ""} onClick={() => setTab(name)} key={name}>{name}</button>)}</div><button className="filter-toggle" onClick={() => setFiltersOpen(!filtersOpen)}><SlidersHorizontal size={18} /> Поиск и фильтры {activeCount > 0 && <b>{activeCount} активных</b>}<ChevronDown size={17} /></button>
    {filtersOpen && <div className="feed-filters"><input value={filters.query} onChange={updateFilter("query")} placeholder="Поиск по публикациям" /><input value={filters.tag} onChange={updateFilter("tag")} placeholder="Тег без #" /><input value={filters.author} onChange={updateFilter("author")} placeholder="Автор username" /><select value={filters.sort} onChange={updateFilter("sort")}><option value="newest">Сначала новые</option><option value="oldest">Сначала старые</option></select><button className="outline-button" onClick={resetFilters}>Сбросить</button></div>}
    {state === "loading" && <div className="card-state">Загружаем публикации…</div>}{state === "error" && <div className="card-state"><b>Не удалось загрузить</b><button className="outline-button" onClick={() => load()}>Повторить</button></div>}{state === "empty" && <div className="card-state"><b>Публикаций пока нет</b><span>{category ? "В этой категории ещё нет публикаций." : "Когда пользователи добавят посты, они появятся здесь."}</span></div>}
    {posts.map((post) => <PostCard key={post.id} post={post} onLike={(post) => toggle(post, "like")} onBookmark={(post) => toggle(post, "bookmark")} onShare={share} />)}{cursor && <button className="outline-button load-more" disabled={state === "loading-more"} onClick={() => load(true)}>{state === "loading-more" ? "Загружаем…" : "Показать ещё"}</button>}
  </section></AppShell>;
}
