import { SessionProvider, useSession } from "./session";
import { RouterProvider, useRouter } from "./lib/router";
import { AppShell } from "./components/AppShell";
import { AuthPage } from "./pages/AuthPage";
import { FeedPage } from "./pages/FeedPage";
import { CreatePostPage } from "./pages/CreatePostPage";
import { PostPage } from "./pages/PostPage";
import { ProfilePage } from "./pages/ProfilePage";
import { ModerationPage } from "./pages/ModerationPage";
import { SearchPage } from "./pages/SearchPage";
import { BookmarksPage, DraftsPage } from "./pages/SavedPages";
import { SystemStatesPage } from "./pages/SystemStatesPage";
import "./styles/app.css";

function AppContent() {
  const { loading } = useSession();
  const { location, navigate } = useRouter();
  if (loading) return <main className="boot">Загружаем Simple…</main>;
  if (location.pathname === "/login") return <AuthPage mode="login" />;
  if (location.pathname === "/register") return <AuthPage mode="register" />;
  if (location.pathname === "/posts/new") return <CreatePostPage />;
  const draftEditMatch = location.pathname.match(/^\/drafts\/([^/]+)\/edit$/);
  if (draftEditMatch) return <CreatePostPage draftId={draftEditMatch[1]} />;
  const editMatch = location.pathname.match(/^\/posts\/([^/]+)\/edit$/);
  if (editMatch) return <CreatePostPage postId={editMatch[1]} />;
  if (location.pathname === "/me") return <ProfilePage />;
  if (location.pathname === "/moderation") return <ModerationPage />;
  if (location.pathname === "/search") return <SearchPage />;
  if (location.pathname === "/bookmarks") return <BookmarksPage />;
  if (location.pathname === "/drafts") return <DraftsPage />;
  if (location.pathname === "/system-states") return <SystemStatesPage />;
  const userMatch = location.pathname.match(/^\/users\/([^/]+)$/);
  if (userMatch) return <ProfilePage username={userMatch[1]} />;
  const postMatch = location.pathname.match(/^\/posts\/([^/]+)$/);
  if (postMatch) return <PostPage postId={postMatch[1]} />;
  if (location.pathname === "/") return <FeedPage />;
  return <AppShell title="Не найдено"><div className="card-state"><b>Страница не найдена</b><span>Ссылка устарела или такого раздела нет.</span><button className="outline-button" onClick={() => navigate("/")}>К ленте</button></div></AppShell>;
}

export function App() {
  return <RouterProvider><SessionProvider><AppContent /></SessionProvider></RouterProvider>;
}
