import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { PostCard } from "../components/PostCard";
import { api } from "../lib/api";
import "../styles/list-pages.css";

export function SearchPage() {
  const [query, setQuery] = useState(""); const [searchIn, setSearchIn] = useState("all"); const [posts, setPosts] = useState([]); const [state, setState] = useState("empty");
  useEffect(() => { const delay = setTimeout(() => { if (!query.trim()) return setState("empty"); setState("loading"); api.posts({ query, search_in: searchIn }).then((page) => { setPosts(page.items); setState(page.items.length ? "ready" : "empty"); }).catch(() => setState("error")); }, 300); return () => clearTimeout(delay); }, [query, searchIn]);
  return <AppShell title="Поиск"><section className="list-page"><h1>Поиск</h1><div className="search-panel"><Search size={19} /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Поиск в Simple" /><select value={searchIn} onChange={(event) => setSearchIn(event.target.value)}><option value="all">Везде</option><option value="title">В заголовках</option><option value="content">В тексте</option></select></div>{state === "loading" && <div className="card-state">Ищем публикации…</div>}{state === "empty" && <div className="card-state"><b>{query ? "Ничего не найдено" : "Введите запрос"}</b><span>{query ? "Измените запрос или фильтры." : "Искать можно по заголовку и тексту публикаций."}</span></div>}{state === "error" && <div className="card-state">Не удалось выполнить поиск</div>}{posts.map((post) => <PostCard key={post.id} post={post} onLike={() => {}} onBookmark={() => {}} />)}</section></AppShell>;
}
