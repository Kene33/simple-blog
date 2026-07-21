import { useEffect, useState } from "react";
import { Eye, X } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { api } from "../lib/api";
import { useSession } from "../session";
import "../styles/moderation.css";

const reasonLabels = { malware: "Вредоносная ссылка", phishing: "Фишинг", spam: "Спам", copyright: "Авторские права", illegal: "Незаконный контент", abuse: "Оскорбления", other: "Другое" };

export function ModerationPage() {
  const { isAdmin } = useSession();
  const [reports, setReports] = useState([]);
  const [status, setStatus] = useState("open");
  const [offset, setOffset] = useState(0);
  const [nextOffset, setNextOffset] = useState(null);
  const [openCount, setOpenCount] = useState(null);
  const [selected, setSelected] = useState(null);
  const [state, setState] = useState("loading");

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    Promise.all([api.reports({ status_filter: status, offset }), api.reportCount()])
      .then(([page, count]) => {
        if (cancelled) return;
        setReports((current) => (offset ? [...current, ...page.items] : page.items));
        const loaded = offset + page.items.length;
        setNextOffset(loaded < page.total ? loaded : null);
        setOpenCount(count.open_count);
        setState("ready");
      })
      .catch(() => !cancelled && setState("error"));
    return () => { cancelled = true; };
  }, [status, offset]);

  const changeStatus = (event) => {
    setReports([]);
    setOffset(0);
    setStatus(event.target.value);
  };
  const open = async (id) => { try { setSelected(await api.reportDetail(id)); } catch { } };
  const resolve = async (value) => {
    const password = window.prompt("Подтвердите действие паролем администратора");
    if (!password) return;
    await api.resolveReport(selected.id, { status: value, password_confirmation: password, resolution: "Обработано модератором" });
    setReports((current) => current.filter((report) => report.id !== selected.id));
    setSelected(null);
    const count = await api.reportCount();
    setOpenCount(count.open_count);
  };

  if (!isAdmin) return <AppShell title="Модерация"><div className="card-state"><b>Нет доступа</b><span>Эта страница доступна только администраторам.</span></div></AppShell>;

  return <AppShell title="Модерация"><section className="moderation-page">
    <header className="moderation-heading"><div><h1>Очередь жалоб</h1><p>{openCount ?? "-"} открытых обращений требуют проверки</p></div><select value={status} onChange={changeStatus}><option value="open">Открытые</option><option value="in_review">В работе</option><option value="resolved">Решённые</option><option value="rejected">Отклонённые</option></select></header>
    {state === "loading" && !reports.length ? <div className="card-state">Загружаем обращения...</div> : state === "error" ? <div className="card-state">Не удалось загрузить очередь</div> : <><div className="reports-table"><div className="report-row report-titles"><span>Жалоба</span><span>Репортёр</span><span>Объект</span><span>Причина</span><span>Создана</span></div>{reports.map((report) => <div className="report-row" key={report.id}><span><i className={`report-status ${report.status}`}>{report.status}</i><b>#{String(report.id).slice(0, 8)}</b></span><span>{report.reporter_email}</span><span><a href={`/${report.shortcode}`} target="_blank" rel="noreferrer">{report.shortcode}</a><small>Открыть ссылку</small></span><span><b>{reasonLabels[report.category] || report.category}</b><small>{report.comment || report.resolution_comment || "Без деталей"}</small></span><span>{new Date(report.created_at).toLocaleDateString("ru-RU")}</span><button className="outline-button" onClick={() => open(report.id)}><Eye size={15} /> Рассмотреть</button></div>)}{!reports.length && <div className="empty-row">Очередь пуста</div>}</div>{nextOffset != null && <button className="outline-button next-page" onClick={() => setOffset(nextOffset)}>Следующая страница</button>}</>}
    {selected && <div className="modal-backdrop" role="presentation"><section className="moderation-modal" role="dialog" aria-modal="true"><button className="modal-close" onClick={() => setSelected(null)} aria-label="Закрыть"><X /></button><small>ЖАЛОБА НА ССЫЛКУ</small><h2>#{String(selected.id).slice(0, 8)}</h2><p><b>{reasonLabels[selected.category] || selected.category}</b> · {selected.reporter_email}</p><blockquote>{selected.comment}</blockquote><footer><button className="outline-button" onClick={() => resolve("rejected")}>Отклонить</button><button className="danger-button" onClick={() => resolve("resolved")}>Решить жалобу</button></footer></section></div>}
  </section></AppShell>;
}
