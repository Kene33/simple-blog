import { useEffect, useState } from "react";
import { Eye, X } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { api } from "../lib/api";
import { useSession } from "../session";
import "../styles/moderation.css";

export function ModerationPage() {
  const { isAdmin } = useSession(); const [reports, setReports] = useState([]); const [status, setStatus] = useState("open"); const [selected, setSelected] = useState(null); const [state, setState] = useState("loading");
  const load = () => { setState("loading"); api.reports({ status }).then((page) => { setReports(page.items); setState("ready"); }).catch(() => setState("error")); };
  useEffect(load, [status]);
  const open = async (id) => { try { setSelected(await api.reportDetail(id)); } catch { } };
  const resolve = async (value) => { await api.resolveReport(selected.id, { status: value, resolution: "Обработано модератором" }); setSelected(null); load(); };
  if (!isAdmin) return <AppShell title="Модерация"><div className="card-state"><b>Нет доступа</b><span>Эта страница доступна только администраторам.</span></div></AppShell>;
  return <AppShell title="Модерация"><section className="moderation-page"><header className="moderation-heading"><div><h1>Очередь жалоб</h1><p>Обращения, требующие проверки</p></div><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="open">Открытые</option><option value="resolved">Решённые</option><option value="rejected">Отклонённые</option></select></header>{state === "loading" ? <div className="card-state">Загружаем обращения…</div> : state === "error" ? <div className="card-state">Не удалось загрузить очередь</div> : <div className="reports-table"><div className="report-row report-titles"><span>Жалоба</span><span>Репортёр</span><span>Объект</span><span>Причина</span><span>Создана</span></div>{reports.map((report) => <div className="report-row" key={report.id}><span><i className={`report-status ${report.status}`}>{report.status}</i><b>#{report.id.slice(0, 8)}</b></span><span>@{report.reporter.username}</span><span>{report.target?.kind === "comment" ? "Комментарий" : "Пост"}</span><span><b>{report.reason}</b><small>{report.details}</small></span><span>{new Date(report.created_at).toLocaleDateString("ru-RU")}</span><button className="outline-button" onClick={() => open(report.id)}><Eye size={15} /> Рассмотреть</button></div>)}</div>}{selected && <div className="modal-backdrop" role="presentation"><section className="moderation-modal" role="dialog" aria-modal="true"><button className="modal-close" onClick={() => setSelected(null)} aria-label="Закрыть"><X /></button><small>ЖАЛОБА НА {selected.target.kind.toUpperCase()}</small><h2>#{selected.id.slice(0, 8)}</h2><p><b>{selected.reason}</b> · @{selected.reporter.username}</p><blockquote>{selected.target.title || selected.target.body}</blockquote><footer><button className="outline-button" onClick={() => resolve("rejected")}>Отклонить</button><button className="danger-button" onClick={() => resolve("resolved")}>Решить жалобу</button></footer></section></div>}</section></AppShell>;
}
