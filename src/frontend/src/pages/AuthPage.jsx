import { useEffect, useState } from "react";
import { ArrowLeft, Eye, EyeOff } from "lucide-react";
import { Brand } from "../components/Brand";
import { Link, useRouter } from "../lib/router";
import { ApiError } from "../lib/api";
import { useSession } from "../session";

export function AuthPage({ mode }) {
  const isLogin = mode === "login";
  const { user, login, register } = useSession();
  const { navigate } = useRouter();
  const [form, setForm] = useState({ username: "", email: "", identifier: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => { if (user) navigate("/"); }, [user, navigate]);

  async function submit(event) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      if (isLogin) await login({ identifier: form.identifier, password: form.password });
      else await register({ username: form.username, email: form.email, password: form.password });
      navigate("/");
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Проверьте подключение и попробуйте ещё раз");
    } finally { setBusy(false); }
  }

  const set = (key) => (event) => setForm((value) => ({ ...value, [key]: event.target.value }));
  return <div className="auth-page">
    <div className="auth-aside"><Brand compact /><div><h1>{isLogin ? "С возвращением" : "Создайте свой профиль"}</h1><p>{isLogin ? "Продолжайте обсуждения там, где остановились." : "Публикуйте мысли и находите людей со схожими интересами."}</p></div></div>
    <section className="auth-card">
      <Link to="/" className="back-link"><ArrowLeft size={17} /> К ленте</Link>
      <h2>{isLogin ? "Вход" : "Регистрация"}</h2>
      <p>{isLogin ? "Введите данные аккаунта" : "Это займёт меньше минуты"}</p>
      <form onSubmit={submit} noValidate>
        {!isLogin && <label>Username<input value={form.username} onChange={set("username")} minLength="5" maxLength="30" required autoComplete="username" /></label>}
        {!isLogin && <label>Email<input type="email" value={form.email} onChange={set("email")} required autoComplete="email" /></label>}
        {isLogin && <label>Username или email<input value={form.identifier} onChange={set("identifier")} required autoComplete="username" /></label>}
        <label>Пароль<span className="password-input"><input type={showPassword ? "text" : "password"} value={form.password} onChange={set("password")} minLength="10" required autoComplete={isLogin ? "current-password" : "new-password"} /><button type="button" onClick={() => setShowPassword(!showPassword)} aria-label="Показать пароль">{showPassword ? <EyeOff size={18} /> : <Eye size={18} />}</button></span></label>
        {error && <div className="form-error" role="alert">{error}</div>}
        <button className="primary auth-submit" disabled={busy}>{busy ? "Подождите…" : isLogin ? "Войти" : "Создать аккаунт"}</button>
      </form>
      {isLogin && <p className="auth-switch"><Link to="/password-reset">Забыли пароль?</Link></p>}
      <p className="auth-switch">{isLogin ? "Впервые здесь? " : "Уже есть аккаунт? "}<Link to={isLogin ? "/register" : "/login"}>{isLogin ? "Зарегистрироваться" : "Войти"}</Link></p>
    </section>
  </div>;
}
