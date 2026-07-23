import { useState } from "react";
import { X } from "lucide-react";
import "../styles/report-modal.css";

export function ModerationActionModal({ title, description, onClose, onSubmit }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault();
    if (!reason.trim()) return setError("Укажите причину действия.");
    setBusy(true); setError("");
    try { await onSubmit(reason.trim()); onClose(); } catch (cause) { setError(cause.message || "Не удалось выполнить действие."); setBusy(false); }
  }
  return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section className="report-modal" role="dialog" aria-modal="true" aria-labelledby="moderation-action-title"><button className="modal-close" onClick={onClose} aria-label="Закрыть"><X /></button><form onSubmit={submit}><small>ДЕЙСТВИЕ МОДЕРАТОРА</small><h2 id="moderation-action-title">{title}</h2><p>{description}</p><label className="report-details">Причина<textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Опишите причину действия" maxLength="2000" autoFocus required /></label>{error && <p className="form-error" role="alert">{error}</p>}<footer><button type="button" className="outline-button" onClick={onClose}>Отмена</button><button className="danger-button" disabled={busy}>{busy ? "Выполняем…" : "Подтвердить"}</button></footer></form></section></div>;
}
