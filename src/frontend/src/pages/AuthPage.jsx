import { useState } from "react";
import { ArrowLeft, Eye, EyeOff } from "lucide-react";
import { Brand } from "../components/Brand";
import { Link, useRouter } from "../lib/router";
import { ApiError } from "../lib/api";
import { useSession } from "../session";

export function AuthPage({ mode }) {
  const isLogin = mode === "login";
  const { login, register } = useSession();
  const { navigate } = useRouter();
  const [form, setForm] = useState({ display_name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      if (isLogin) await login({ email: form.email, password: form.password });
      else await register({ display_name: form.display_name, email: form.email, password: form.password });
      navigate("/");
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Проверьте подключение и попробуйте ещё раз");
    } finally { setBusy(false); }
  }

  const set = (key) => (event) => setForm((value) => ({ ...value, [key]: event.target.value }));
  return <div className="auth-page">
    <div className="auth-aside"><Brand compact /><div><h1>{isLogin ? "С возвращением" : "Создайте свой профиль"}</h1><p>{isLogin ? "Вернитесь к своим ссылкам, папкам и аналитике." : "Сохраняйте ссылки, раскладывайте их по папкам и отслеживайте переходы."}</p></div></div>
    <section className="auth-card">
      <Link to="/" className="back-link"><ArrowLeft size={17} /> К ссылкам</Link>
      <h2>{isLogin ? "Вход" : "Регистрация"}</h2>
      <p>{isLogin ? "Введите данные аккаунта" : "Это займёт меньше минуты"}</p>
      <form onSubmit={submit} noValidate>
        {!isLogin && <label>Имя<input value={form.display_name} onChange={set("display_name")} maxLength="120" autoComplete="name" /></label>}
        {!isLogin && <label>Email<input type="email" value={form.email} onChange={set("email")} required autoComplete="email" /></label>}
        {isLogin && <label>Email<input type="email" value={form.email} onChange={set("email")} required autoComplete="email" /></label>}
        <label>Пароль<span className="password-input"><input type={showPassword ? "text" : "password"} value={form.password} onChange={set("password")} minLength="8" required autoComplete={isLogin ? "current-password" : "new-password"} /><button type="button" onClick={() => setShowPassword(!showPassword)} aria-label="Показать пароль">{showPassword ? <EyeOff size={18} /> : <Eye size={18} />}</button></span></label>
        {error && <div className="form-error" role="alert">{error}</div>}
        <button className="primary auth-submit" disabled={busy}>{busy ? "Подождите…" : isLogin ? "Войти" : "Создать аккаунт"}</button>
      </form>
      <p className="auth-switch">{isLogin ? "Впервые здесь? " : "Уже есть аккаунт? "}<Link to={isLogin ? "/register" : "/login"}>{isLogin ? "Зарегистрироваться" : "Войти"}</Link></p>
    </section>
  </div>;
}
