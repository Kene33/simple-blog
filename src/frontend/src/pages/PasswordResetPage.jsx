import { useState } from "react";
import { Brand } from "../components/Brand";
import { api } from "../lib/api";
import { Link, useRouter } from "../lib/router";

export function PasswordResetPage() {
  const { location, navigate } = useRouter();
  const [token, setToken] = useState(new URLSearchParams(location.search).get("token") || "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const confirm = Boolean(token);

  async function submit(event) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      if (confirm) { await api.confirmPasswordReset({ token, password }); setMessage("Пароль изменён. Теперь можно войти."); }
      else { const result = await api.requestPasswordReset({ email }); if (result.reset_token) { setToken(result.reset_token); setMessage("Ссылка создана для локальной разработки. Укажите новый пароль."); } else setMessage("Если email зарегистрирован, ссылка для восстановления отправлена."); }
    } catch (cause) { setError(cause.message || "Не удалось восстановить пароль"); } finally { setBusy(false); }
  }

  return <div className="auth-page"><div className="auth-aside"><Brand compact /><div><h1>Восстановление пароля</h1><p>Получите одноразовую ссылку и задайте новый пароль.</p></div></div><section className="auth-card"><Link to="/login" className="back-link">К входу</Link><h2>{confirm ? "Новый пароль" : "Забыли пароль?"}</h2><form onSubmit={submit}>{confirm ? <label>Новый пароль<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength="10" autoComplete="new-password" required /></label> : <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required /></label>}{error && <div className="form-error" role="alert">{error}</div>}{message && <div className="card-state">{message}{confirm && <button type="button" className="outline-button" onClick={() => navigate("/login")}>Войти</button>}</div>}{!message && <button className="primary auth-submit" disabled={busy}>{busy ? "Подождите…" : confirm ? "Сохранить пароль" : "Получить ссылку"}</button>}</form></section></div>;
}
