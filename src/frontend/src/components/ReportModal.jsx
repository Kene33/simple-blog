import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { api } from "../lib/api";
import "../styles/report-modal.css";

const reasons = [["spam", "Спам"], ["harassment", "Оскорбления"], ["illegal", "Незаконный контент"], ["other", "Другое"]];

export function ReportModal({ postId, commentId, onClose }) {
  const [reason, setReason] = useState("spam");
  const [details, setDetails] = useState("");
  const [state, setState] = useState("ready");
  const closeRef = useRef(null);

  useEffect(() => {
    closeRef.current?.focus();
    const handler = (event) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  async function submit(event) {
    event.preventDefault();
    setState("sending");
    try {
      await api.report({ post_id: postId || null, comment_id: commentId || null, reason, details: details || null });
      setState("sent");
    } catch (cause) {
      setState(cause.status === 409 ? "duplicate" : "error");
    }
  }

  return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section className="report-modal" role="dialog" aria-modal="true" aria-labelledby="report-title"><button ref={closeRef} className="modal-close" onClick={onClose} aria-label="Закрыть"><X /></button>{state === "sent" ? <div className="report-result"><h2>Жалоба отправлена</h2><p>Спасибо, модератор проверит обращение.</p><button className="primary" onClick={onClose}>Готово</button></div> : <form onSubmit={submit}><small>ЖАЛОБА НА ПУБЛИКАЦИЮ</small><h2 id="report-title">Что произошло?</h2><div className="reason-grid">{reasons.map(([value, label]) => <label className={reason === value ? "selected" : ""} key={value}><input type="radio" name="reason" checked={reason === value} onChange={() => setReason(value)} /><b>{label}</b><span>{value}</span></label>)}</div><label className="report-details">Подробности <small>необязательно</small><textarea value={details} onChange={(event) => setDetails(event.target.value)} placeholder="Добавьте контекст для модератора" maxLength="2000" /></label>{state === "duplicate" && <p className="form-error">Жалоба уже открыта.</p>}{state === "error" && <p className="form-error">Не удалось отправить жалобу.</p>}<footer><button type="button" className="outline-button" onClick={onClose}>Отмена</button><button className="danger-button" disabled={state === "sending"}>{state === "sending" ? "Отправляем…" : "Отправить жалобу"}</button></footer></form>}</section></div>;
}
