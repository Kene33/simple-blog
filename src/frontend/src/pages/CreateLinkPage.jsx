import { useState } from "react";
import { ArrowLeft, Copy, Link as LinkIcon } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { api } from "../lib/api";
import { useRouter } from "../lib/router";
import { useSession } from "../session";
import "../styles/create-post.css";
import "../styles/links.css";

export function CreateLinkPage() {
  const { navigate } = useRouter();
  const { user } = useSession();
  const [form, setForm] = useState({ url: "", label: "", mode: "reuse" });
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const update = (key) => (event) => setForm((value) => ({ ...value, [key]: event.target.value }));
  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setResult(await api.createLink(user ? { url: form.url, label: form.label || null, mode: form.mode } : { url: form.url }));
      setForm({ url: "", label: "", mode: "reuse" });
    } catch (cause) {
      setError(cause.message || "Не удалось создать ссылку");
    } finally {
      setBusy(false);
    }
  };
  const copy = async () => navigator.clipboard.writeText(result.short_url);

  return <AppShell title="Создать"><section className="create-page"><button className="back-link button-link" onClick={() => navigate("/")}><ArrowLeft size={17} /> Отмена</button><h1>Новая ссылка</h1><p>Сократите URL и сохраните его в Simple</p><form className="create-form" onSubmit={submit}><label>Длинная ссылка <small>обязательно</small><input type="url" value={form.url} onChange={update("url")} maxLength="2048" required placeholder="https://example.com/long/path" /></label><label>Название <small>{user ? "необязательно" : "после входа"}</small><input value={form.label} onChange={update("label")} maxLength="120" disabled={!user} placeholder="Документация, лендинг, кампания" /></label><label>Поведение<select value={form.mode} onChange={update("mode")} disabled={!user}><option value="reuse">Переиспользовать существующую</option><option value="new">Создать новую</option></select></label>{error && <div className="form-error" role="alert">{error}</div>}{result && <div className="card-state"><LinkIcon size={20} /><b>{result.short_url}</b><span>{result.created ? "Ссылка создана" : "Найдена существующая ссылка"}</span><button type="button" className="outline-button" onClick={copy}><Copy size={16} /> Копировать</button></div>}<footer><button type="button" className="outline-button" onClick={() => navigate("/")}>К ссылкам</button><button className="primary" disabled={busy}>{busy ? "Создаём..." : "Создать ссылку"}</button></footer></form></section></AppShell>;
}
