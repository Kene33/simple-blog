import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { LinkCard } from "../components/LinkCard";
import { api } from "../lib/api";
import { useSession } from "../session";
import "../styles/list-pages.css";
import "../styles/links.css";

export function SearchPage() {
  const { user } = useSession();
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("created_at_desc");
  const [links, setLinks] = useState([]);
  const [state, setState] = useState(user ? "empty" : "guest");
  useEffect(() => {
    const delay = setTimeout(() => {
      if (!user) return setState("guest");
      if (!query.trim()) return setState("empty");
      setState("loading");
      api.myLinks({ q: query, sort }).then((page) => { setLinks(page.items); setState(page.items.length ? "ready" : "empty"); }).catch(() => setState("error"));
    }, 300);
    return () => clearTimeout(delay);
  }, [query, sort, user]);
  const copy = (item) => navigator.clipboard.writeText(item.short_url);
  return <AppShell title="Поиск"><section className="list-page"><h1>Поиск</h1><div className="search-panel"><Search size={19} /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Поиск по вашим ссылкам" /><select value={sort} onChange={(event) => setSort(event.target.value)}><option value="created_at_desc">Новые</option><option value="access_count_desc">Популярные</option><option value="created_at_asc">Старые</option></select></div>{state === "guest" && <div className="card-state"><b>Войдите, чтобы искать</b><span>Поиск работает по ссылкам вашего аккаунта.</span></div>}{state === "loading" && <div className="card-state">Ищем ссылки...</div>}{state === "empty" && <div className="card-state"><b>{query ? "Ничего не найдено" : "Введите запрос"}</b><span>{query ? "Измените запрос или сортировку." : "Искать можно по URL и названию ссылки."}</span></div>}{state === "error" && <div className="card-state">Не удалось выполнить поиск</div>}{links.map((link) => <LinkCard key={link.shortcode} item={link} onCopy={copy} />)}</section></AppShell>;
}
