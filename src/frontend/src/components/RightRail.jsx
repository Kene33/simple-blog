import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { Avatar } from "./Avatar";
import { api } from "../lib/api";
import { useRouter } from "../lib/router";

export function RightRail() {
  const [query, setQuery] = useState("");
  const [authors, setAuthors] = useState([]);
  const { navigate } = useRouter();
  const submit = (event) => {
    event.preventDefault();
    navigate(query.trim() ? `/search?q=${encodeURIComponent(query.trim())}` : "/search");
  };
  useEffect(() => { api.activeAuthors().then(setAuthors).catch(() => setAuthors([])); }, []);

  return <div className="rail-stack">
    <form className="search-box" onSubmit={submit}><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Поиск в Simple" /></form>
    <section className="rail-card"><h3>Сейчас в тренде</h3><p className="rail-empty">Пока нет данных.</p></section>
    <section className="rail-card"><h3>Активные авторы</h3>{authors.length ? authors.map(({ author, posts_count, likes_count }) => <div className="author-line" key={author.id}><Avatar user={author} /><span><b>{author.username}</b><small>{posts_count} публ. · {likes_count} лайков</small></span><button onClick={() => navigate(`/users/${author.username}`)}>Профиль</button></div>) : <p className="rail-empty">Активных авторов пока нет.</p>}</section>
  </div>;
}
