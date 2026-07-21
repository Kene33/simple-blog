import { useState } from "react";
import { Search } from "lucide-react";
import { useRouter } from "../lib/router";

export function RightRail() {
  const [query, setQuery] = useState("");
  const { navigate } = useRouter();
  const submit = (event) => {
    event.preventDefault();
    navigate(query.trim() ? `/search?q=${encodeURIComponent(query.trim())}` : "/search");
  };

  return <div className="rail-stack">
    <form className="search-box" onSubmit={submit}><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Поиск в Simple" /></form>
    <section className="rail-card"><h3>Сейчас в тренде</h3><p className="rail-empty">Пока нет данных.</p></section>
    <section className="rail-card"><h3>Активные авторы</h3><p className="rail-empty">Активных авторов пока нет.</p></section>
  </div>;
}
