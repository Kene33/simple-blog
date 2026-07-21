import { SessionProvider, useSession } from "./session";
import { RouterProvider, useRouter } from "./lib/router";
import { AppShell } from "./components/AppShell";
import { AuthPage } from "./pages/AuthPage";
import { FeedPage } from "./pages/FeedPage";
import { CreateLinkPage } from "./pages/CreateLinkPage";
import { ProfilePage } from "./pages/ProfilePage";
import { ModerationPage } from "./pages/ModerationPage";
import { SearchPage } from "./pages/SearchPage";
import { BookmarksPage, DraftsPage } from "./pages/SavedPages";
import "./styles/app.css";

function AppContent() {
  const { loading } = useSession();
  const { location, navigate } = useRouter();
  if (loading) return <main className="boot">Загружаем Simple…</main>;
  if (location.pathname === "/login") return <AuthPage mode="login" />;
  if (location.pathname === "/register") return <AuthPage mode="register" />;
  if (location.pathname === "/links/new") return <CreateLinkPage />;
  if (location.pathname === "/posts/new") return <AppShell title="Создать"><div className="card-state"><b>Маршрут изменён</b><span>Для текущего backend используйте создание короткой ссылки.</span><button className="outline-button" onClick={() => navigate("/links/new")}>К созданию ссылки</button></div></AppShell>;
  if (location.pathname === "/me") return <ProfilePage />;
  if (location.pathname === "/moderation") return <ModerationPage />;
  if (location.pathname === "/search") return <SearchPage />;
  if (location.pathname === "/bookmarks") return <BookmarksPage />;
  if (location.pathname === "/drafts") return <DraftsPage />;
  const userMatch = location.pathname.match(/^\/users\/([^/]+)$/);
  if (userMatch) return <ProfilePage username={userMatch[1]} />;
  if (location.pathname.startsWith("/posts/")) return <AppShell title="Недоступно"><div className="card-state"><b>Публикации недоступны</b><span>Текущий backend работает с короткими ссылками, а не с постами.</span></div></AppShell>;
  return <FeedPage />;
}

export function App() {
  return <RouterProvider><SessionProvider><AppContent /></SessionProvider></RouterProvider>;
}
