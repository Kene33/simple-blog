import { useEffect, useState } from "react";
import { Bookmark, CircleUserRound, House, LogIn, Menu, PenLine, Plus, Search, ShieldCheck, X } from "lucide-react";
import { Brand } from "./Brand";
import { api } from "../lib/api";
import { Link, useRouter } from "../lib/router";
import { useSession } from "../session";

const links = [
  ["/", "Лента", House],
  ["/search", "Поиск", Search],
  ["/posts/new", "Создать", PenLine]
];

function NavLink({ to, label, Icon, badge }) {
  const { location } = useRouter();
  return <Link to={to} className={`nav-link ${location.pathname === to ? "active" : ""}`}>
    <Icon size={22} strokeWidth={2} /> <span>{label}</span>{badge ? <b className="nav-badge">{badge}</b> : null}
  </Link>;
}

function Sidebar() {
  const { user, isAdmin } = useSession();
  const [reportCount, setReportCount] = useState(0);
  useEffect(() => { if (isAdmin) api.reportCount().then((data) => setReportCount(data.open_count)).catch(() => setReportCount(0)); }, [isAdmin]);
  return <aside className="sidebar">
    <Brand />
    <nav className="sidebar-nav">
      {links.map(([to, label, Icon]) => <NavLink key={to} to={to} label={label} Icon={Icon} />)}
      {user && <NavLink to="/me" label="Профиль" Icon={CircleUserRound} />}
      {user && <NavLink to="/bookmarks" label="Закладки" Icon={Bookmark} />}
      {isAdmin && <NavLink to="/moderation" label="Модерация" Icon={ShieldCheck} badge={reportCount} />}
    </nav>
    <Link to={user ? "/posts/new" : "/login"} className="primary create-button"><Plus size={21} /> {user ? "Новый пост" : "Войти"}</Link>
    <div className="sidebar-account">
      <small>Режим прототипа</small>
      {user ? <Link to="/me" className="account-row"><span className="avatar">{user.username.slice(0, 2).toUpperCase()}</span><span><b>{user.display_name || user.username}</b><em>@{user.username}</em></span></Link> : <Link to="/login" className="account-row"><span className="account-login"><LogIn size={21} /></span><span><b>Войти</b><em>или создать аккаунт</em></span></Link>}
    </div>
  </aside>;
}

export function AppShell({ children, title = "Лента", right }) {
  const { user, isAdmin } = useSession();
  const { navigate } = useRouter();
  const [mobileMenu, setMobileMenu] = useState(false);
  const go = (to) => { setMobileMenu(false); navigate(to); };
  return <div className="app-shell">
    <Sidebar />
    <header className="mobile-header"><Brand compact /><b>{title}</b><button className="icon-button" onClick={() => setMobileMenu(!mobileMenu)} aria-label={mobileMenu ? "Закрыть меню" : "Открыть меню"}>{mobileMenu ? <X /> : <Menu />}</button></header>
    {mobileMenu && <div className="mobile-menu"><button onClick={() => go("/")}>Лента</button><button onClick={() => go("/search")}>Поиск</button><button onClick={() => go(user ? "/posts/new" : "/login")}>{user ? "Создать" : "Войти"}</button><button onClick={() => go(user ? "/me" : "/login")}>Профиль</button>{user && <button onClick={() => go("/bookmarks")}>Закладки</button>}{isAdmin && <button onClick={() => go("/moderation")}>Модерация</button>}</div>}
    <main className="main-content">{children}</main>
    {right && <aside className="right-rail">{right}</aside>}
    <nav className="mobile-nav">
      <button onClick={() => navigate("/")} aria-label="Лента"><House /></button>
      <button className="mobile-create" onClick={() => navigate("/posts/new")} aria-label="Новый пост"><Plus /></button>
      <button onClick={() => navigate("/me")} aria-label="Профиль"><CircleUserRound /></button>
    </nav>
  </div>;
}
