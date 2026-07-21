import { useEffect, useState } from "react";
import { Folder, Plus } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { LinkCard } from "../components/LinkCard";
import { api } from "../lib/api";
import { useSession } from "../session";
import "../styles/list-pages.css";
import "../styles/links.css";

export function BookmarksPage() {
  const { user } = useSession();
  const [folders, setFolders] = useState([]);
  const [state, setState] = useState("loading");
  const [name, setName] = useState("");
  const load = () => api.folders().then((items) => { setFolders(items); setState(items.length ? "ready" : "empty"); }).catch(() => setState("error"));
  useEffect(() => { if (!user) return setState("guest"); load(); }, [user]);
  const create = async (event) => {
    event.preventDefault();
    if (!name.trim()) return;
    await api.createFolder({ name: name.trim(), color: "violet" });
    setName("");
    load();
  };
  return <AppShell title="Папки"><section className="list-page"><h1>Папки</h1>{user && <form className="search-panel" onSubmit={create}><Folder size={19} /><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Новая папка" maxLength="80" /><button className="primary"><Plus size={16} /> Создать</button></form>}{state === "guest" ? <div className="card-state"><b>Войдите, чтобы открыть папки</b><span>Папки доступны для сохранённых ссылок аккаунта.</span></div> : state === "loading" ? <div className="card-state">Загружаем папки...</div> : state === "empty" ? <div className="card-state"><b>Папок пока нет</b><span>Создайте папку, чтобы раскладывать ссылки.</span></div> : state === "error" ? <div className="card-state">Не удалось загрузить папки</div> : <div className="draft-list">{folders.map((folder) => <article className="draft-card" key={folder.id}><span className="draft-icon"><Folder size={20} /></span><div><b>{folder.name}</b><p>{folder.link_count} ссылок</p><small>Создана {new Date(folder.created_at).toLocaleDateString("ru-RU")}</small></div></article>)}</div>}</section></AppShell>;
}

export function DraftsPage() {
  const { user } = useSession();
  const [links, setLinks] = useState([]);
  const [state, setState] = useState("loading");
  useEffect(() => { if (!user) return setState("guest"); api.myLinks().then((page) => { setLinks(page.items); setState(page.items.length ? "ready" : "empty"); }).catch(() => setState("error")); }, [user]);
  const copy = (item) => navigator.clipboard.writeText(item.short_url);
  return <AppShell title="Ссылки"><section className="list-page"><h1>Все ссылки</h1>{state === "guest" ? <div className="card-state"><b>Войдите, чтобы открыть ссылки</b><span>Список ссылок доступен после входа.</span></div> : state === "loading" ? <div className="card-state">Загружаем ссылки...</div> : state === "empty" ? <div className="card-state"><b>Ссылок пока нет</b><span>Создайте первую короткую ссылку.</span></div> : state === "error" ? <div className="card-state">Не удалось загрузить ссылки</div> : links.map((link) => <LinkCard key={link.shortcode} item={link} onCopy={copy} />)}</section></AppShell>;
}
