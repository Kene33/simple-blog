import { useEffect, useState } from "react";
import { Eye, X } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { Link, useRouter } from "../lib/router";
import { api } from "../lib/api";
import { useSession } from "../session";
import "../styles/moderation.css";

const reasonLabels = { spam: "Спам", harassment: "Оскорбления", illegal: "Незаконный контент", other: "Другое" };

export function ModerationPage() {
  const { user, loading, isAdmin } = useSession();
  const { navigate } = useRouter();
  const [reports, setReports] = useState([]);
  const [status, setStatus] = useState("open");
  const [cursor, setCursor] = useState(null);
  const [nextCursor, setNextCursor] = useState(null);
  const [openCount, setOpenCount] = useState(null);
  const [selected, setSelected] = useState(null);
  const [state, setState] = useState("loading");

  useEffect(() => {
    if (!isAdmin) return;
    let cancelled = false;
    setState("loading");
    Promise.all([api.reports({ status, cursor }), api.reportCount()])
      .then(([page, count]) => {
        if (cancelled) return;
        setReports((current) => (cursor ? [...current, ...page.items] : page.items));
        setNextCursor(page.next_cursor);
        setOpenCount(count.open_count);
        setState("ready");
      })
      .catch(() => !cancelled && setState("error"));
    return () => { cancelled = true; };
  }, [status, cursor, isAdmin]);

  const changeStatus = (event) => {
    setReports([]);
    setCursor(null);
    setStatus(event.target.value);
  };
  const open = async (id) => { try { setSelected(await api.reportDetail(id)); } catch { } };
  const resolve = async (value) => {
    await api.resolveReport(selected.id, { status: value, resolution: "Обработано модератором" });
    setReports((current) => current.filter((report) => report.id !== selected.id));
    setSelected(null);
    const count = await api.reportCount();
    setOpenCount(count.open_count);
  };

  if (loading) return <AppShell title="Модерация"><div className="card-state">Проверяем доступ…</div></AppShell>;
  if (!user) return <AppShell title="Модерация"><div className="card-state"><b>Войдите, чтобы открыть модерацию</b><button className="outline-button" onClick={() => navigate("/login")}>Войти</button></div></AppShell>;
  if (!isAdmin) return <AppShell title="Модерация"><div className="card-state"><b>Нет доступа</b><span>Эта страница доступна только администраторам.</span></div></AppShell>;

  return <AppShell title="Модерация"><section className="moderation-page">
    <header className="moderation-heading"><div><h1>Очередь жалоб</h1><p>{openCount ?? "—"} открытых обращений требуют проверки</p></div><select value={status} onChange={changeStatus}><option value="open">Открытые</option><option value="resolved">Решённые</option><option value="rejected">Отклонённые</option></select></header>
    {state === "loading" && !reports.length ? <div className="card-state">Загружаем обращения…</div> : state === "error" ? <div className="card-state">Не удалось загрузить очередь</div> : <><div className="reports-table"><div className="report-row report-titles"><span>Жалоба</span><span>Репортёр</span><span>Объект</span><span>Причина</span><span>Создана</span></div>{reports.map((report) => <div className="report-row" key={report.id}><span><i className={`report-status ${report.status}`}>{report.status}</i><b>#{report.id.slice(0, 8)}</b></span><span>@{report.reporter.username}</span><span>{report.target?.kind === "post" ? <Link to={`/posts/${report.post_id}`}>Пост</Link> : report.target ? "Комментарий" : "Недоступен"}<small>{report.target?.is_deleted ? "Удалён" : report.target ? "Открыть объект" : "Объект не найден"}</small></span><span><b>{reasonLabels[report.reason] || report.reason}</b><small>{report.details || report.resolution || "Без деталей"}</small></span><span>{new Date(report.created_at).toLocaleDateString("ru-RU")}</span><button className="outline-button" onClick={() => open(report.id)}><Eye size={15} /> Рассмотреть</button></div>)}{!reports.length && <div className="empty-row">Очередь пуста</div>}</div>{nextCursor && <button className="outline-button next-page" onClick={() => setCursor(nextCursor)}>Следующая страница</button>}</>}
    {selected && <div className="modal-backdrop" role="presentation"><section className="moderation-modal" role="dialog" aria-modal="true"><button className="modal-close" onClick={() => setSelected(null)} aria-label="Закрыть"><X /></button><small>ЖАЛОБА НА {(selected.target?.kind || "объект").toUpperCase()}</small><h2>#{selected.id.slice(0, 8)}</h2><p><b>{reasonLabels[selected.reason] || selected.reason}</b> · @{selected.reporter.username}</p><blockquote>{selected.target?.title || selected.target?.body || "Объект жалобы недоступен"}</blockquote><footer><button className="outline-button" onClick={() => resolve("rejected")}>Отклонить</button><button className="danger-button" onClick={() => resolve("resolved")}>Решить жалобу</button></footer></section></div>}
  </section></AppShell>;
}
