import { useEffect, useRef, useState } from "react";
import { CalendarDays, Camera, Settings } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { LinkCard } from "../components/LinkCard";
import { api } from "../lib/api";
import { useSession } from "../session";
import "../styles/profile.css";
import "../styles/links.css";

export function ProfilePage({ username }) {
  const { user: currentUser, refreshMe } = useSession();
  const avatarInput = useRef(null);
  const [profile, setProfile] = useState(currentUser);
  const [links, setLinks] = useState([]);
  const [state, setState] = useState("loading");
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ display_name: "" });
  const [uploading, setUploading] = useState("");

  useEffect(() => {
    if (username) { setState("error"); return; }
    Promise.all([api.me(), api.myLinks({ limit: 10 })])
      .then(([data, page]) => {
        setProfile(data);
        setForm({ display_name: data.display_name || "" });
        setLinks(page.items);
        setState("ready");
      })
      .catch(() => setState("error"));
  }, [username]);

  const save = async (event) => {
    event.preventDefault();
    const updated = await api.updateMe({ display_name: form.display_name || null });
    setProfile(updated);
    await refreshMe();
    setEditing(false);
  };
  const uploadAvatar = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!file.type.startsWith("image/") || file.size > 2 * 1024 * 1024) return setUploading("Нужна картинка до 2 МБ.");
    setUploading("Загружаем...");
    try {
      const updated = await api.uploadMedia(file, "avatar");
      setProfile(updated);
      await refreshMe();
      setUploading("");
    } catch (cause) {
      setUploading(cause.message || "Не удалось загрузить изображение");
    }
  };
  const copy = (item) => navigator.clipboard.writeText(item.short_url);

  if (state === "loading") return <AppShell title="Профиль"><div className="card-state">Загружаем профиль...</div></AppShell>;
  if (state === "error") return <AppShell title="Профиль"><div className="card-state"><b>Профиль недоступен</b><span>Публичных профилей в текущем backend нет.</span></div></AppShell>;

  const name = profile.display_name || profile.email;
  return <AppShell title="Профиль"><section className="profile-page"><section className="profile-hero"><div className="profile-cover" /><div className="profile-info"><span className="profile-avatar">{profile.avatar_url ? <img src={profile.avatar_url} alt="" /> : name.slice(0, 2).toUpperCase()}</span><button className="outline-button edit-profile" onClick={() => setEditing(!editing)}><Settings size={16} /> Редактировать профиль</button><h1>{name}</h1><span className="handle">{profile.email}</span><p>{profile.email_verified ? "Email подтверждён" : "Email ожидает подтверждения"}</p><div className="profile-meta"><span><CalendarDays size={15} /> С нами с {new Date(profile.created_at).toLocaleDateString("ru-RU", { month: "long", year: "numeric" })}</span><b>{links.length} ссылок</b></div></div></section>{editing && <form className="profile-edit" onSubmit={save}><label>Отображаемое имя<input value={form.display_name} onChange={(event) => setForm({ display_name: event.target.value })} maxLength="120" /></label><button className="primary">Сохранить</button></form>}<section className="profile-private"><span>Email <b>{profile.email}</b>{uploading && <small>{uploading}</small>}</span><input ref={avatarInput} className="visually-hidden" type="file" accept="image/*" onChange={uploadAvatar} /><button className="outline-button" onClick={() => avatarInput.current?.click()}><Camera size={16} /> Изменить avatar</button></section><nav className="profile-tabs"><button className="selected">Ссылки</button></nav>{links.map((link) => <LinkCard key={link.shortcode} item={link} onCopy={copy} />)}</section></AppShell>;
}
