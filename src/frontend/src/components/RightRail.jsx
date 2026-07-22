import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { Avatar } from "./Avatar";
import { api } from "../lib/api";
import { useRouter } from "../lib/router";

export function RightRail() {
  const [query, setQuery] = useState("");
  const [authors, setAuthors] = useState([]);
  const [trending, setTrending] = useState({ posts: [], categories: [], tags: [] });
  const { navigate } = useRouter();
  const submit = (event) => {
    event.preventDefault();
    navigate(query.trim() ? `/search?q=${encodeURIComponent(query.trim())}` : "/search");
  };
  useEffect(() => { api.activeAuthors().then(setAuthors).catch(() => setAuthors([])); api.trending().then(setTrending).catch(() => setTrending({ posts: [], categories: [], tags: [] })); }, []);

  return <div className="rail-stack">
    <form className="search-box" onSubmit={submit}><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Поиск в Simple" /></form>
    <section className="rail-card"><h3>Сейчас в тренде</h3>{trending.posts.map((post) => <button className="trend" key={post.id} onClick={() => navigate(`/posts/${post.id}`)}><small>Пост · {post.like_count} лайков</small><b>{post.title}</b></button>)}{trending.categories.map((item) => <div className="trend" key={`category-${item.name}`}><small>Категория</small><b>{item.name} · {item.count} публикаций</b></div>)}{trending.tags.map((item) => <div className="trend" key={`tag-${item.name}`}><small>Тег</small><b>#{item.name} · {item.count} публикаций</b></div>)}{!trending.posts.length && !trending.categories.length && !trending.tags.length && <p className="rail-empty">Пока нет данных.</p>}</section>
    <section className="rail-card"><h3>Активные авторы</h3>{authors.length ? authors.map(({ author, posts_count, likes_count }) => <div className="author-line" key={author.id}><Avatar user={author} /><span><b>{author.username}</b><small>{posts_count} публ. · {likes_count} лайков</small></span><button onClick={() => navigate(`/users/${author.username}`)}>Профиль</button></div>) : <p className="rail-empty">Активных авторов пока нет.</p>}</section>
  </div>;
}
