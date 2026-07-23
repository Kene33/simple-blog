import { MailCheck, X } from "lucide-react";
import "../styles/email-verification-notice.css";

export function EmailVerificationNotice({ onClose }) {
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section className="email-verification-notice" role="dialog" aria-modal="true" aria-labelledby="email-notice-title"><button className="modal-close" onClick={onClose} aria-label="Закрыть"><X size={20} /></button><span className="email-notice-icon"><MailCheck size={27} /></span><h2 id="email-notice-title">Подтвердите email</h2><p>Аккаунт уже создан. Мы отправили письмо со ссылкой подтверждения на вашу почту.</p><small>Письмо можно открыть позже, а это окно — закрыть.</small><button className="primary" onClick={onClose}>Понятно</button></section></div>;
}
