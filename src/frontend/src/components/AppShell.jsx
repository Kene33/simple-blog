import { useEffect, useState } from "react";
import { Bookmark, CircleUserRound, House, LogIn, LogOut, Menu, MessageCircle, Moon, PenLine, Plus, Search, ShieldCheck, Sun, X } from "lucide-react";
import { Brand } from "./Brand";
import { Avatar } from "./Avatar";
import { api } from "../lib/api";
import { Link, useRouter } from "../lib/router";
import { useSession } from "../session";

export function notifyGuest(action) {
  window.dispatchEvent(new CustomEvent("simple:guest-action", { detail: { action } }));
}

const links = [
  ["/", "Лента", House],
  ["/search", "Поиск", Search],
  ["/posts/new", "Создать", PenLine]
  , ["/messages", "Сообщения", MessageCircle]
];

function NavLink({ to, label, Icon, badge }) {
  const { location } = useRouter();
  return <Link to={to} className={`nav-link ${location.pathname === to ? "active" : ""}`}>
    <Icon size={22} strokeWidth={2} /> <span>{label}</span>{badge ? <b className="nav-badge">{badge}</b> : null}
  </Link>;
}

function ThemeButton({ theme, onToggle }) {
  const isDark = theme === "dark";
  return <button className="theme-button" onClick={onToggle} aria-label={isDark ? "Включить светлую тему" : "Включить тёмную тему"}>
    {isDark ? <Sun size={17} /> : <Moon size={17} />} <span>{isDark ? "Светлая тема" : "Тёмная тема"}</span>
  </button>;
}

function Sidebar({ theme, onThemeToggle }) {
  const { user, isStaff, logout } = useSession();
  const { navigate } = useRouter();
  const [reportCount, setReportCount] = useState(0);
  useEffect(() => { if (isStaff) api.reportCount().then((data) => setReportCount(data.open_count)).catch(() => setReportCount(0)); }, [isStaff]);
  const signOut = async () => { await logout(); navigate("/"); };
  return <aside className="sidebar">
    <Link to="/" className="brand-link"><Brand /></Link>
    <nav className="sidebar-nav">
      {links.map(([to, label, Icon]) => <NavLink key={to} to={to} label={label} Icon={Icon} />)}
      {user && <NavLink to="/me" label="Профиль" Icon={CircleUserRound} />}
      {user && <NavLink to="/bookmarks" label="Закладки" Icon={Bookmark} />}
      {isStaff && <NavLink to="/moderation" label="Модерация" Icon={ShieldCheck} badge={reportCount} />}
    </nav>
    <Link to={user ? "/posts/new" : "/login"} className="primary create-button"><Plus size={21} /> {user ? "Новый пост" : "Войти"}</Link>
    <ThemeButton theme={theme} onToggle={onThemeToggle} />
    <div className="sidebar-account">
      {user ? <><Link to="/me" className="account-row"><Avatar user={user} /><span><b>{user.display_name || user.username}</b><em>@{user.username}</em></span></Link><button className="account-logout" onClick={signOut}><LogOut size={15} /> Выйти</button></> : <Link to="/login" className="account-row"><span className="account-login"><LogIn size={21} /></span><span><b>Войти</b><em>или создать аккаунт</em></span></Link>}
    </div>
  </aside>;
}

export function AppShell({ children, title = "Лента", right }) {
  const { user, isStaff, logout } = useSession();
  const { location, navigate } = useRouter();
  const [mobileMenu, setMobileMenu] = useState(false);
  const [guestNotice, setGuestNotice] = useState("");
  const [theme, setTheme] = useState(() => localStorage.getItem("simple-theme") || "light");
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("simple-theme", theme);
  }, [theme]);
  useEffect(() => {
    const pageTitle = title === "Лента" ? "Simple — идеи и обсуждения" : `${title} — Simple`;
    const description = title === "Лента" ? "Идеи и обсуждения сообщества без лишнего шума." : `${title} в Simple — идеи и обсуждения сообщества.`;
    document.title = pageTitle;
    document.querySelector('meta[name="description"]')?.setAttribute("content", description);
    document.querySelector('meta[property="og:title"]')?.setAttribute("content", pageTitle);
    document.querySelector('meta[property="og:description"]')?.setAttribute("content", description);
    document.querySelector('meta[property="og:url"]')?.setAttribute("content", `${window.location.origin}${location.pathname}`);
    const canonical = document.querySelector('link[rel="canonical"]');
    if (canonical) canonical.href = `${window.location.origin}${location.pathname}`;
  }, [title, location.pathname]);
  useEffect(() => {
    const onGuestAction = (event) => setGuestNotice(`Чтобы ${event.detail?.action || "продолжить"}, войдите в аккаунт.`);
    window.addEventListener("simple:guest-action", onGuestAction);
    return () => window.removeEventListener("simple:guest-action", onGuestAction);
  }, []);
  const toggleTheme = () => setTheme((value) => value === "dark" ? "light" : "dark");
  const go = (to) => { setMobileMenu(false); navigate(to); };
  const guestOnly = (action) => { setMobileMenu(false); setGuestNotice(`Чтобы ${action}, войдите в аккаунт.`); };
  const signOut = async () => { setMobileMenu(false); await logout(); navigate("/"); };
  return <div className={`app-shell ${location.pathname === "/messages" ? "messages-shell" : ""}`}>
    <Sidebar theme={theme} onThemeToggle={toggleTheme} />
    <header className="mobile-header"><Link to="/" className="brand-link"><Brand compact /></Link><b>{title}</b><span className="mobile-header-actions"><ThemeButton theme={theme} onToggle={toggleTheme} /><button className="icon-button" onClick={() => setMobileMenu(!mobileMenu)} aria-label={mobileMenu ? "Закрыть меню" : "Открыть меню"}>{mobileMenu ? <X /> : <Menu />}</button></span></header>
    {mobileMenu && <div className="mobile-menu"><button onClick={() => go("/")}>Лента</button><button onClick={() => go("/search")}>Поиск</button>{user && <button onClick={() => go("/messages")}>Сообщения</button>}<button onClick={() => user ? go("/posts/new") : guestOnly("создать публикацию")}>Новый пост</button><button onClick={() => user ? go("/me") : guestOnly("открыть профиль")}>Профиль</button>{user && <button onClick={() => go("/bookmarks")}>Закладки</button>}{isStaff && <button onClick={() => go("/moderation")}>Модерация</button>}{user && <button onClick={signOut}>Выйти</button>}</div>}
    <main className="main-content">{children}</main>
    {right && <aside className="right-rail">{right}</aside>}
    {guestNotice && <div className="guest-notice" role="alert"><span>{guestNotice}</span><button className="guest-login" onClick={() => { setGuestNotice(""); navigate("/login", { allowAuth: true }); }}>Войти</button><button onClick={() => setGuestNotice("")} aria-label="Закрыть уведомление"><X size={16} /></button></div>}
    <nav className="mobile-nav">
      <button onClick={() => navigate("/")} aria-label="Лента"><House /></button>
      <button className="mobile-create" onClick={() => user ? navigate("/posts/new") : guestOnly("создать публикацию")} aria-label="Новый пост"><Plus /></button>
      <button onClick={() => user ? navigate("/me") : guestOnly("открыть профиль")} aria-label="Профиль"><CircleUserRound /></button>
    </nav>
  </div>;
}
