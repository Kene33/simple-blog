import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { api } from "../lib/api";
import "../styles/report-modal.css";

const reasons = [["spam", "Спам"], ["harassment", "Оскорбления"], ["illegal", "Незаконный контент"], ["other", "Другое"]];

export function ReportModal({ postId, commentId, onClose }) {
  const [reason, setReason] = useState("spam");
  const [details, setDetails] = useState("");
  const [state, setState] = useState("ready");
  const [error, setError] = useState("");
  const closeRef = useRef(null);

  useEffect(() => {
    closeRef.current?.focus();
    const handler = (event) => {
      if (event.key === "Escape") return onClose();
      if (event.key !== "Tab") return;
      const items = [...document.querySelectorAll(".report-modal button,.report-modal textarea,.report-modal input")].filter((item) => !item.disabled);
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  async function submit(event) {
    event.preventDefault();
    setState("sending");
    setError("");
    try {
      await api.report({ post_id: postId || null, comment_id: commentId || null, reason, details: details || null });
      setState("sent");
    } catch (cause) {
      setError(cause.message || "Не удалось отправить жалобу.");
      setState(cause.status === 409 ? "duplicate" : "error");
    }
  }

  return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section className="report-modal" role="dialog" aria-modal="true" aria-labelledby="report-title"><button ref={closeRef} className="modal-close" onClick={onClose} aria-label="Закрыть"><X /></button>{state === "sent" ? <div className="report-result"><h2>Жалоба отправлена</h2><p>Спасибо, модератор проверит обращение.</p><button className="primary" onClick={onClose}>Готово</button></div> : <form onSubmit={submit}><small>ЖАЛОБА НА {commentId ? "КОММЕНТАРИЙ" : "ПУБЛИКАЦИЮ"}</small><h2 id="report-title">Что произошло?</h2><div className="reason-grid">{reasons.map(([value, label]) => <label className={reason === value ? "selected" : ""} key={value}><input type="radio" name="reason" checked={reason === value} onChange={() => setReason(value)} /><b>{label}</b><span>{value}</span></label>)}</div><label className="report-details">Подробности <small>необязательно</small><textarea value={details} onChange={(event) => setDetails(event.target.value)} placeholder="Добавьте контекст для модератора" maxLength="2000" /></label>{state === "duplicate" && <p className="form-error" role="alert">Жалоба уже открыта.</p>}{state === "error" && <p className="form-error" role="alert">{error}</p>}<footer><button type="button" className="outline-button" onClick={onClose}>Отмена</button><button className="danger-button" disabled={state === "sending"}>{state === "sending" ? "Отправляем…" : "Отправить жалобу"}</button></footer></form>}</section></div>;
}
