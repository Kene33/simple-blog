import { useEffect, useState } from "react";
import { Flame, Hash, Heart, Layers, Search } from "lucide-react";
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
    <section className="rail-card trending-card"><header className="trending-header"><h3><Flame size={17} /> Сейчас в тренде</h3><small>30 дней</small></header>{trending.posts.length > 0 && <div className="trend-posts">{trending.posts.map((post, index) => <button className="trend-post" key={post.id} onClick={() => navigate(`/posts/${post.id}`)} title={post.title}><span className="trend-rank">{String(index + 1).padStart(2, "0")}</span><span className="trend-post-copy"><b>{post.title}</b><small><Heart size={12} fill="currentColor" /> {post.like_count} лайков</small></span></button>)}</div>}{trending.categories.length > 0 && <div className="trend-topic-group"><div className="trend-topic-heading"><Layers size={14} /> Категории</div>{trending.categories.map((item) => <div className="trend-topic" key={`category-${item.name}`}><b>{item.name}</b><span>{item.count} публикаций</span></div>)}</div>}{trending.tags.length > 0 && <div className="trend-topic-group"><div className="trend-topic-heading"><Hash size={14} /> Теги</div>{trending.tags.map((item) => <div className="trend-topic" key={`tag-${item.name}`}><b>#{item.name}</b><span>{item.count} публикаций</span></div>)}</div>}{!trending.posts.length && !trending.categories.length && !trending.tags.length && <p className="rail-empty">Пока нет данных.</p>}</section>
    <section className="rail-card"><h3>Активные авторы</h3>{authors.length ? authors.map(({ author, posts_count, likes_count }) => <div className="author-line" key={author.id}><Avatar user={author} /><span><b>{author.username}</b><small>{posts_count} публ. · {likes_count} лайков</small></span><button onClick={() => navigate(`/users/${author.username}`)}>Профиль</button></div>) : <p className="rail-empty">Активных авторов пока нет.</p>}</section>
  </div>;
}
