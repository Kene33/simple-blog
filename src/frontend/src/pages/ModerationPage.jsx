import { useEffect, useState } from "react";
import { Eye, ShieldAlert, X } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { isDeletedUser } from "../components/Avatar";
import { Link, useRouter } from "../lib/router";
import { api } from "../lib/api";
import { useSession } from "../session";
import "../styles/moderation.css";

const reasonLabels = { spam: "Спам", harassment: "Оскорбления", illegal: "Незаконный контент", other: "Другое" };
const actionLabels = { user_ban: "Пользователь заблокирован", user_unban: "Блокировка пользователя снята", user_mute: "Пользователь получил мут", user_unmute: "Мут пользователя снят", user_delete: "Пользователь удалён", report_resolved: "Жалоба решена", report_rejected: "Жалоба отклонена" };
const tabs = ["reports", "categories", "users", "actions"];

function TabButton({ value, active, children, onClick }) {
  return <button className={active === value ? "selected" : ""} onClick={() => onClick(value)}>{children}</button>;
}

export function ModerationPage() {
  const { user, loading, isAdmin, isStaff } = useSession();
  const { navigate } = useRouter();
  const [tab, setTab] = useState("reports");
  const [status, setStatus] = useState("open");
  const [reports, setReports] = useState([]);
  const [categories, setCategories] = useState([]);
  const [users, setUsers] = useState([]);
  const [actions, setActions] = useState([]);
  const [query, setQuery] = useState("");
  const [userView, setUserView] = useState("all");
  const [openCount, setOpenCount] = useState(null);
  const [selected, setSelected] = useState(null);
  const [selectedAction, setSelectedAction] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [muteDuration, setMuteDuration] = useState("24h");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [state, setState] = useState("loading");

  useEffect(() => {
    if (!isStaff) return;
    setError("");
    setState("loading");
    const load = tab === "reports" ? Promise.all([api.reports({ status }), api.reportCount()]).then(([page, count]) => { setReports(page.items); setOpenCount(count.open_count); })
      : tab === "categories" ? api.adminCategoryRequests({ status: "pending" }).then((page) => setCategories(page.items))
        : tab === "users" ? api.adminUsers({ query, limit: 100 }).then(setUsers)
          : isAdmin ? api.moderationActions().then((page) => setActions(page.items)) : Promise.resolve();
    load.then(() => setState("ready")).catch((cause) => { setError(cause.message || "Не удалось загрузить данные"); setState("error"); });
  }, [tab, status, query, isStaff, isAdmin]);

  const open = async (id) => { setError(""); setReason(""); try { setSelected(await api.reportDetail(id)); } catch (cause) { setError(cause.message || "Не удалось открыть жалобу"); } };
  const resolve = async (value, extra = {}) => {
    const text = reason.trim() || (value === "rejected" ? "Отклонено" : "Обработано");
    try {
      await api.resolveReport(selected.id, { status: value, resolution: text, ...extra });
      setReports((current) => current.filter((report) => report.id !== selected.id));
      setSelected(null);
      setOpenCount((count) => Math.max(0, (count || 1) - 1));
    } catch (cause) {
      setError(cause.message || "Не удалось обработать жалобу");
    }
  };
  const decideCategory = async (item, value) => {
    const text = reason.trim() || (value === "approved" ? "Одобрено" : "Отклонено");
    try {
      await api.resolveCategoryRequest(item.id, { status: value, resolution: text });
      setCategories((current) => current.filter((entry) => entry.id !== item.id));
      setReason("");
    } catch (cause) {
      setError(cause.message || "Не удалось обработать категорию");
    }
  };
  const confirmUserAction = async () => {
    const { item, action, type } = pendingAction;
    const text = reason.trim();
    const needsReason = action === "ban" || action === "mute";
    if (needsReason && !text) return setError("Укажите причину действия.");
    try {
      if (type === "delete") {
        await api.deleteUser(item.id);
        setUsers((current) => current.filter((entry) => entry.id !== item.id));
        setPendingAction(null);
        return;
      }
      const durationMs = { "1h": 3600000, "24h": 86400000, "7d": 604800000, "30d": 2592000000 }[muteDuration];
      const payload = type === "role" ? { role: action, reason: "Изменение роли" } : action === "mute" ? { action, reason: text, muted_until: new Date(Date.now() + durationMs).toISOString() } : { action, ...(text ? { reason: text } : {}) };
      const updated = type === "role" ? await api.setUserRole(item.id, payload) : await api.moderateUser(item.id, payload);
      setUsers((current) => current.map((entry) => entry.id === item.id ? updated : entry));
      setReason("");
      setPendingAction(null);
    } catch (cause) {
      setError(cause.message || "Не удалось изменить пользователя");
    }
  };
  const openUserAction = (item, action, type = "moderation") => { setError(""); setReason(""); setMuteDuration("24h"); setPendingAction({ item, action, type }); };
  const restoreTarget = async () => {
    const text = reason.trim() || "Восстановлено администратором";
    try {
      if (selected.target.kind === "post") await api.restorePost(selected.target.id, { reason: text });
      else await api.restoreComment(selected.target.id, { reason: text });
      setSelected({ ...selected, target: { ...selected.target, is_deleted: false } });
    } catch (cause) {
      setError(cause.message || "Не удалось восстановить объект");
    }
  };

  if (loading) return <AppShell title="Модерация"><div className="card-state">Проверяем доступ…</div></AppShell>;
  if (!user) return <AppShell title="Модерация"><div className="card-state"><b>Войдите, чтобы открыть модерацию</b><button className="outline-button" onClick={() => navigate("/login")}>Войти</button></div></AppShell>;
  if (!isStaff) return <AppShell title="Модерация"><div className="card-state"><b>Нет доступа</b><span>Эта страница доступна модераторам и администраторам.</span></div></AppShell>;

  return <AppShell title="Модерация"><section className="moderation-page">
    <header className="moderation-heading"><div><h1>Модерация</h1><p>{openCount ?? "—"} открытых жалоб</p></div>{tab === "reports" && <select value={status} onChange={(event) => setStatus(event.target.value)}><option value="open">Открытые</option><option value="resolved">Решённые</option><option value="rejected">Отклонённые</option></select>}</header>
    <div className="moderation-tabs">{tabs.filter((item) => isAdmin || item !== "actions").map((item) => <TabButton key={item} value={item} active={tab} onClick={setTab}>{item === "reports" ? "Жалобы" : item === "categories" ? "Категории" : item === "users" ? "Пользователи" : "Аудит"}</TabButton>)}</div>
    {error && <div className="form-error" role="alert">{error}</div>}
    {tab === "users" && <><div className="moderation-tools"><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="username или email" /></div><div className="user-list-tabs"><button className={userView === "all" ? "selected" : ""} onClick={() => setUserView("all")}>Все пользователи</button><button className={userView === "banned" ? "selected" : ""} onClick={() => setUserView("banned")}>Заблокированные</button><button className={userView === "muted" ? "selected" : ""} onClick={() => setUserView("muted")}>Замученные</button></div></>}
    {state === "loading" ? <div className="card-state">Загружаем…</div> : tab === "reports" ? <Reports reports={reports} open={open} /> : tab === "categories" ? <Categories items={categories} decide={decideCategory} /> : tab === "users" ? <Users items={users} view={userView} currentUser={user} isAdmin={isAdmin} openAction={openUserAction} /> : <Actions items={actions} onOpen={setSelectedAction} />}
    {selected && <ReportModal report={selected} reason={reason} setReason={setReason} isAdmin={isAdmin} onClose={() => setSelected(null)} onReject={() => resolve("rejected")} onResolve={() => resolve("resolved")} onHide={() => resolve("resolved", { hide_target: true })} onBan={() => resolve("resolved", { ban_author: true })} onHideBan={() => resolve("resolved", { hide_target: true, ban_author: true })} onRestore={restoreTarget} />}
    {pendingAction && <UserActionModal action={pendingAction} reason={reason} setReason={setReason} muteDuration={muteDuration} setMuteDuration={setMuteDuration} onClose={() => setPendingAction(null)} onConfirm={confirmUserAction} />}
    {selectedAction && <ActionModal action={selectedAction} onClose={() => setSelectedAction(null)} />}
  </section></AppShell>;
}

function Reports({ reports, open }) {
  return <div className="reports-table"><div className="report-row report-titles"><span>Жалоба</span><span>Репортёр</span><span>Объект</span><span>Причина</span><span>Создана</span></div>{reports.map((report) => <div className="report-row" key={report.id}><span><i className={`report-status ${report.status}`}>{report.status}</i><b>#{report.id.slice(0, 8)}</b></span><span>@{report.reporter.username}</span><span>{report.target?.kind === "post" ? <Link to={`/posts/${report.post_id}`}>Пост</Link> : report.target ? "Комментарий" : "Недоступен"}<small>{report.target?.is_deleted ? "Удалён" : report.target ? "Открыть объект" : "Объект не найден"}</small></span><span><b>{reasonLabels[report.reason] || report.reason}</b><small>{report.details || report.resolution || "Без деталей"}</small></span><span>{new Date(report.created_at).toLocaleDateString("ru-RU")}</span><button className="outline-button" onClick={() => open(report.id)}><Eye size={15} /> Рассмотреть</button></div>)}{!reports.length && <div className="empty-row">Очередь пуста</div>}</div>;
}

function Categories({ items, decide }) {
  return <div className="reports-table">{items.map((item) => <div className="simple-row" key={item.id}><span><b>{item.name}</b><small>#{item.id.slice(0, 8)}</small></span><button className="outline-button" onClick={() => decide(item, "rejected")}>Отклонить</button><button className="primary compact" onClick={() => decide(item, "approved")}>Одобрить</button></div>)}{!items.length && <div className="empty-row">Нет новых категорий</div>}</div>;
}

function Users({ items, view, currentUser, isAdmin, openAction }) {
  const activeItems = items.filter((item) => !isDeletedUser(item));
  const visible = view === "banned" ? activeItems.filter((item) => item.disabled_at) : view === "muted" ? activeItems.filter((item) => item.muted_until && new Date(item.muted_until) > new Date()) : activeItems;
  return <div className="reports-table">{visible.map((item) => { const muted = item.muted_until && new Date(item.muted_until) > new Date(); return <div className="user-row" key={item.id}><span><b>@{item.username}</b><small><b>Роль:</b> {item.role}</small><small><b>Почта:</b> {item.email}</small>{view === "banned" && <small><b>Причина:</b> {item.moderation_reason || "не указана"}</small>}{view === "muted" && <small><b>До:</b> {new Date(item.muted_until).toLocaleString("ru-RU")}</small>}</span>{item.id === currentUser?.id ? <small className="user-self-label">Это вы</small> : <details className="user-action-menu"><summary>Действия</summary><div className="user-action-list">{view === "banned" ? isAdmin && <button onClick={() => openAction(item, "unban")}>Разбан</button> : view === "muted" ? isAdmin && <button onClick={() => openAction(item, "unmute")}>Снять мут</button> : <>{item.id !== currentUser?.id && <button className="danger-text" onClick={() => openAction(item, "ban")}>Бан</button>}{isAdmin && <button onClick={() => openAction(item, "unban")}>Разбан</button>}{isAdmin && (muted ? <button onClick={() => openAction(item, "unmute")}>Снять мут</button> : <button onClick={() => openAction(item, "mute")}>Дать мут</button>)}{isAdmin && <button onClick={() => openAction(item, item.role === "moderator" ? "user" : "moderator", "role")}>{item.role === "moderator" ? "Снять модера" : "Сделать модером"}</button>}{isAdmin && item.id !== currentUser?.id && <button className="danger-text" onClick={() => openAction(item, "delete", "delete")}>Удалить пользователя</button>}</>}</div></details>}</div>; })}{!visible.length && <div className="empty-row">{view === "banned" ? "Заблокированных пользователей нет" : view === "muted" ? "Замученных пользователей нет" : "Пользователи не найдены"}</div>}</div>;
}

function Actions({ items, onOpen }) {
  return <div className="reports-table">{items.map((item) => <button className="simple-row audit-row" key={item.id} onClick={() => onOpen(item)}><span><b>{actionLabels[item.action] || item.action}</b><small>@{item.actor.username} · {item.target_type} #{item.target_id.slice(0, 8)}</small></span><span>{item.reason || "Без причины"}</span><span>{new Date(item.created_at).toLocaleString("ru-RU")}</span></button>)}{!items.length && <div className="empty-row">Аудит пуст</div>}</div>;
}

function ActionModal({ action, onClose }) {
  return <div className="modal-backdrop" role="presentation"><section className="moderation-modal" role="dialog" aria-modal="true" aria-label="Детали действия модерации"><button className="modal-close" onClick={onClose} aria-label="Закрыть"><X /></button><small>ДЕТАЛИ АУДИТА</small><h2>{actionLabels[action.action] || action.action}</h2><dl className="action-details"><dt>Кто выполнил</dt><dd>@{action.actor?.username || "неизвестно"}</dd><dt>По отношению к кому</dt><dd>{action.target_username ? `@${action.target_username}` : `${action.target_type} #${action.target_id.slice(0, 8)}`}</dd><dt>Когда</dt><dd>{new Date(action.created_at).toLocaleString("ru-RU")}</dd><dt>Причина</dt><dd>{action.reason || "Не указана"}</dd></dl><footer><button className="outline-button" onClick={onClose}>Закрыть</button></footer></section></div>;
}

function ReportModal({ report, reason, setReason, isAdmin, onClose, onReject, onResolve, onHide, onBan, onHideBan, onRestore }) {
  return <div className="modal-backdrop" role="presentation"><section className="moderation-modal" role="dialog" aria-modal="true"><button className="modal-close" onClick={onClose} aria-label="Закрыть"><X /></button><small>ЖАЛОБА НА {(report.target?.kind || "объект").toUpperCase()}</small><h2>#{report.id.slice(0, 8)}</h2><p><b>{reasonLabels[report.reason] || report.reason}</b> · @{report.reporter.username}</p><blockquote>{report.target?.title || report.target?.body || "Объект жалобы недоступен"}</blockquote><label className="report-reason"><ShieldAlert size={16} /> Причина<input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Что сделал модератор" /></label><footer><button className="outline-button" onClick={onReject}>Отклонить</button>{isAdmin && report.target?.is_deleted && <button className="outline-button" onClick={onRestore}>Восстановить</button>}<button className="outline-button" onClick={onResolve}>Решить</button><button className="danger-button" onClick={onHide}>Скрыть</button><button className="danger-button" onClick={onBan}>Бан автора</button><button className="danger-button" onClick={onHideBan}>Скрыть + бан</button></footer></section></div>;
}

function UserActionModal({ action, reason, setReason, muteDuration, setMuteDuration, onClose, onConfirm }) {
  const labels = { ban: "Заблокировать", unban: "Разблокировать", mute: "Ограничить пользователя", unmute: "Снять ограничение", user: "Снять модератора", moderator: "Сделать модератором", delete: "Удалить пользователя" };
  const needsReason = action.action === "ban" || action.action === "mute";
  return <div className="modal-backdrop" role="presentation"><section className="moderation-modal" role="dialog" aria-modal="true" aria-label="Подтверждение действия"><button className="modal-close" onClick={onClose} aria-label="Закрыть"><X /></button><small>ДЕЙСТВИЕ С ПОЛЬЗОВАТЕЛЕМ</small><h2>{labels[action.action]}</h2><p>Пользователь: <b>@{action.item.username}</b></p>{action.action === "delete" && <p className="form-error">Это действие необратимо.</p>}{action.action === "mute" && <label className="report-reason">Срок<select value={muteDuration} onChange={(event) => setMuteDuration(event.target.value)}><option value="1h">1 час</option><option value="24h">24 часа</option><option value="7d">7 дней</option><option value="30d">30 дней</option></select></label>}{needsReason && <label className="report-reason"><ShieldAlert size={16} /> Причина<input autoFocus value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Опишите причину" /></label>}<footer><button className="outline-button" onClick={onClose}>Отмена</button><button className={action.action === "ban" || action.action === "delete" ? "danger-button" : "primary compact"} onClick={onConfirm}>Подтвердить</button></footer></section></div>;
}
