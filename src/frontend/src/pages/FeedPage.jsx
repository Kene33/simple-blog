import { useEffect, useState } from "react";
import { Check, Copy, RefreshCw, SlidersHorizontal } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { LinkCard } from "../components/LinkCard";
import { RightRail } from "../components/RightRail";
import { useRouter } from "../lib/router";
import { api } from "../lib/api";
import { useSession } from "../session";
import "../styles/links.css";

const sorts = [["created_at_desc", "Новые"], ["access_count_desc", "Популярные"], ["created_at_asc", "Старые"]];

export function FeedPage() {
  const { user } = useSession();
  const { navigate } = useRouter();
  const [links, setLinks] = useState([]);
  const [offset, setOffset] = useState(0);
  const [nextOffset, setNextOffset] = useState(null);
  const [sort, setSort] = useState("created_at_desc");
  const [state, setState] = useState(user ? "loading" : "guest");
  const [form, setForm] = useState({ url: "", label: "" });
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function load(more = false) {
    if (!user) return;
    setState(more ? "loading-more" : "loading");
    try {
      const page = await api.myLinks({ sort, offset: more ? offset : 0, limit: 10 });
      const loaded = (more ? offset : 0) + page.items.length;
      setLinks((current) => (more ? [...current, ...page.items] : page.items));
      setOffset(loaded);
      setNextOffset(loaded < page.total ? loaded : null);
      setState(page.items.length || more ? "ready" : "empty");
    } catch {
      setState("error");
    }
  }
  useEffect(() => { load(false); }, [user, sort]);

  const create = async (event) => {
    event.preventDefault();
    setError("");
    try {
      const created = await api.createLink({ url: form.url, label: form.label || null, mode: "reuse" });
      setResult(created);
      setForm({ url: "", label: "" });
      if (user) load(false);
    } catch (cause) {
      setError(cause.message || "Не удалось создать ссылку");
    }
  };
  const copy = async (item) => {
    await navigator.clipboard.writeText(item.short_url);
    setResult(item);
  };

  return <AppShell title="Лента" right={<RightRail />}><section className="feed-page"><header className="page-title"><div><h1>Лента</h1><p>Короткие ссылки и аналитика Simple</p></div><button className="round-button" onClick={() => load()} aria-label="Обновить"><RefreshCw size={20} /></button></header>
    <form className="composer link-composer" onSubmit={create}><span className="avatar">{user ? (user.display_name || user.email).slice(0, 2).toUpperCase() : "S"}</span><input value={form.url} onChange={(event) => setForm({ ...form, url: event.target.value })} placeholder="Вставьте длинную ссылку" required /><input value={form.label} onChange={(event) => setForm({ ...form, label: event.target.value })} placeholder="Название" maxLength="120" /><button className="primary">Сократить</button></form>
    {result && <div className="filter-toggle"><Check size={18} /> Готово <b>{result.short_url}</b><button onClick={() => copy(result)}><Copy size={16} /></button></div>}
    {error && <div className="form-error" role="alert">{error}</div>}
    <div className="filter-tabs">{sorts.map(([value, label]) => <button type="button" className={sort === value ? "selected" : ""} onClick={() => setSort(value)} key={value}>{label}</button>)}</div><button className="filter-toggle" onClick={() => navigate("/search")}><SlidersHorizontal size={18} /> Поиск и фильтры <b>{user ? "по ссылкам" : "после входа"}</b></button>
    {!user && <div className="card-state"><b>Войдите, чтобы видеть свои ссылки</b><span>Гостевая ссылка создаётся сразу, но список и аналитика доступны аккаунту.</span></div>}
    {user && state === "loading" && <div className="card-state">Загружаем ссылки...</div>}{user && state === "error" && <div className="card-state"><b>Не удалось загрузить</b><button className="outline-button" onClick={() => load()}>Повторить</button></div>}{user && state === "empty" && <div className="card-state"><b>Ссылок пока нет</b><span>Создайте первую короткую ссылку выше.</span></div>}
    {links.map((link) => <LinkCard key={link.shortcode} item={link} onCopy={copy} />)}{nextOffset != null && <button className="outline-button load-more" disabled={state === "loading-more"} onClick={() => load(true)}>{state === "loading-more" ? "Загружаем..." : "Показать ещё"}</button>}
  </section></AppShell>;
}
