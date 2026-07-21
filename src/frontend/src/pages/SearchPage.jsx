import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { PostCard } from "../components/PostCard";
import { api } from "../lib/api";
import { useRouter } from "../lib/router";
import { useSession } from "../session";
import "../styles/list-pages.css";

export function SearchPage() {
  const { location, navigate } = useRouter();
  const { user } = useSession();
  const [query, setQuery] = useState(() => new URLSearchParams(location.search).get("q") || ""); const [searchIn, setSearchIn] = useState(() => new URLSearchParams(location.search).get("search_in") || "all"); const [posts, setPosts] = useState([]); const [state, setState] = useState("empty");
  useEffect(() => { const params = new URLSearchParams(location.search); setQuery(params.get("q") || ""); setSearchIn(params.get("search_in") || "all"); }, [location.search]);
  useEffect(() => { const delay = setTimeout(() => { if (!query.trim()) { setPosts([]); return setState("empty"); } setState("loading"); api.posts({ query, search_in: searchIn }).then((page) => { setPosts(page.items); setState(page.items.length ? "ready" : "empty"); }).catch(() => { setPosts([]); setState("error"); }); }, 300); return () => clearTimeout(delay); }, [query, searchIn]);
  const requireUser = () => { if (!user) navigate("/login"); };
  return <AppShell title="Поиск"><section className="list-page"><h1>Поиск</h1><div className="search-panel"><Search size={19} /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Поиск в Simple" /><select value={searchIn} onChange={(event) => setSearchIn(event.target.value)}><option value="all">Везде</option><option value="title">В заголовках</option><option value="content">В тексте</option></select></div>{state === "loading" && <div className="card-state">Ищем публикации…</div>}{state === "empty" && <div className="card-state"><b>{query ? "Ничего не найдено" : "Введите запрос"}</b><span>{query ? "Измените запрос или фильтры." : "Искать можно по заголовку и тексту публикаций."}</span></div>}{state === "error" && <div className="card-state">Не удалось выполнить поиск</div>}{posts.map((post) => <PostCard key={post.id} post={post} onLike={requireUser} onBookmark={requireUser} />)}</section></AppShell>;
}
