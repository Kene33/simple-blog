import { useEffect, useState } from "react";
import { Link } from "../lib/router";
import { Search } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { Avatar } from "../components/Avatar";
import { PostCard } from "../components/PostCard";
import { api } from "../lib/api";
import { sharePost } from "../lib/sharePost";
import { useRouter } from "../lib/router";
import { useSession } from "../session";
import "../styles/list-pages.css";

export function SearchPage() {
  const { location, navigate, replace } = useRouter();
  const { user } = useSession();
  const initial = new URLSearchParams(location.search);
  const [query, setQuery] = useState(() => initial.get("q") || "");
  const [searchIn, setSearchIn] = useState(() => initial.get("search_in") || "all");
  const [category, setCategory] = useState(() => initial.get("category") || "");
  const [tag, setTag] = useState(() => initial.get("tag") || "");
  const [posts, setPosts] = useState([]);
  const [account, setAccount] = useState(null);
  const [state, setState] = useState("empty");

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    setQuery(params.get("q") || ""); setSearchIn(params.get("search_in") || "all");
    setCategory(params.get("category") || ""); setTag(params.get("tag") || "");
  }, [location.search]);

  useEffect(() => {
    let cancelled = false;
    const delay = setTimeout(async () => {
      const trimmed = query.trim();
      const author = trimmed.startsWith("@") ? trimmed.slice(1).trim() : "";
      const params = new URLSearchParams();
      if (trimmed) params.set("q", trimmed);
      if (searchIn !== "all") params.set("search_in", searchIn);
      if (category) params.set("category", category); if (tag) params.set("tag", tag);
      replace(`/search${params.size ? `?${params}` : ""}`);
      setAccount(null);
      if (!trimmed && !category && !tag) { setPosts([]); return setState("empty"); }
      setState("loading");
      const [userResult, postResult] = await Promise.allSettled([
        author ? api.user(author) : Promise.resolve(null),
        api.posts({ query: author ? undefined : query, author: author || undefined, search_in: searchIn, category: category || undefined, tag: tag || undefined })
      ]);
      if (cancelled) return;
      setAccount(userResult.status === "fulfilled" ? userResult.value : null);
      if (postResult.status !== "fulfilled") { setPosts([]); return setState("error"); }
      setPosts(postResult.value.items);
      setState(postResult.value.items.length || userResult.status === "fulfilled" ? "ready" : "empty");
    }, 300);
    return () => { cancelled = true; clearTimeout(delay); };
  }, [query, searchIn, category, tag]);

  const toggle = async (post, kind) => {
    if (!user) return navigate("/login");
    const before = { ...post };
    const next = kind === "like" ? { ...post, liked_by_me: !post.liked_by_me, like_count: Math.max(0, post.like_count + (post.liked_by_me ? -1 : 1)) } : { ...post, bookmarked_by_me: !post.bookmarked_by_me };
    setPosts((items) => items.map((item) => item.id === post.id ? next : item));
    try { if (kind === "like") post.liked_by_me ? await api.unlike(post.id) : await api.like(post.id); else post.bookmarked_by_me ? await api.unbookmark(post.id) : await api.bookmark(post.id); }
    catch { setPosts((items) => items.map((item) => item.id === post.id ? before : item)); }
  };
  const share = async (post) => { try { const result = await sharePost(post); setPosts((items) => items.map((item) => item.id === post.id ? { ...item, share_count: result.share_count } : item)); } catch { } };

  return <AppShell title="Поиск"><section className="list-page"><h1>Поиск</h1><div className="search-panel"><Search size={19} /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Посты, теги или @username" aria-describedby="search-hint" /><select value={searchIn} onChange={(event) => setSearchIn(event.target.value)}><option value="all">Везде</option><option value="title">В заголовках</option><option value="content">В тексте</option></select></div><small id="search-hint" className="search-hint">Введите @username, чтобы найти аккаунт и его публикации.</small>{account && <Link className="search-account" to={`/u/${account.username}`}><Avatar user={account} /><span><b>{account.display_name || account.username}</b><small>@{account.username}</small></span><strong>Профиль</strong></Link>}{(category || tag) && <div className="search-filter">{category && <span>Категория: <b>{category}</b><button onClick={() => setCategory("")} aria-label="Убрать фильтр категории">×</button></span>}{tag && <span>Тег: <b>#{tag}</b><button onClick={() => setTag("")} aria-label="Убрать фильтр тега">×</button></span>}</div>}{state === "loading" && <div className="card-state">Ищем публикации…</div>}{state === "empty" && <div className="card-state"><b>{query || category || tag ? "Ничего не найдено" : "Введите запрос"}</b><span>{query || category || tag ? "Измените запрос или фильтры." : "Искать можно по заголовку, тексту, категории и тегу."}</span></div>}{state === "error" && <div className="card-state">Не удалось выполнить поиск</div>}{posts.map((post) => <PostCard key={post.id} post={post} onLike={(post) => toggle(post, "like")} onBookmark={(post) => toggle(post, "bookmark")} onShare={share} />)}</section></AppShell>;
}
