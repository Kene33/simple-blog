import { useEffect, useState } from "react";
import { ArrowLeft, CheckCircle2, LoaderCircle, MailCheck } from "lucide-react";
import { Brand } from "../components/Brand";
import { api } from "../lib/api";
import { Link, useRouter } from "../lib/router";
import "../styles/email-verification.css";

export function EmailVerificationPage({ token }) {
  const { navigate } = useRouter();
  const [state, setState] = useState("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) { setState("error"); setError("В ссылке нет токена подтверждения."); return; }
    api.verifyEmail(token).then(() => setState("success")).catch((cause) => { setState("error"); setError(cause.message || "Ссылка недействительна или устарела."); });
  }, [token]);

  return <main className="email-verification-page">
    <section className="email-verification-shell">
      <Brand compact />
      <div className={`email-verification-card ${state}`}>
        {state === "loading" && <><span className="verification-icon"><LoaderCircle className="spin" size={28} /></span><h1>Проверяем email</h1><p>Подтверждаем адрес и подготавливаем ваш аккаунт.</p></>}
        {state === "success" && <><span className="verification-icon success"><CheckCircle2 size={28} /></span><h1>Email подтверждён</h1><p>Готово — адрес подтверждён. Теперь можно вернуться в Simple и продолжить.</p><button className="primary" onClick={() => navigate("/", { allowAuth: true })}>Перейти в ленту</button></>}
        {state === "error" && <><span className="verification-icon error"><MailCheck size={28} /></span><h1>Не удалось подтвердить email</h1><p>{error}</p><button className="outline-button" onClick={() => navigate("/login", { allowAuth: true })}>Войти в аккаунт</button></>}
      </div>
      <Link className="verification-back" to="/"><ArrowLeft size={15} /> Вернуться к Simple</Link>
    </section>
  </main>;
}
