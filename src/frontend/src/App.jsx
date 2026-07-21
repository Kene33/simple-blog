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
import "./styles/app.css";

function AppContent() {
  const { loading } = useSession();
  const { location } = useRouter();
  if (loading) return <main className="boot">Загружаем Simple…</main>;
  if (location.pathname === "/login") return <AuthPage mode="login" />;
  if (location.pathname === "/register") return <AuthPage mode="register" />;
  if (location.pathname === "/posts/new") return <CreatePostPage />;
  if (location.pathname === "/me") return <ProfilePage />;
  if (location.pathname === "/moderation") return <ModerationPage />;
  if (location.pathname === "/search") return <SearchPage />;
  if (location.pathname === "/bookmarks") return <BookmarksPage />;
  if (location.pathname === "/drafts") return <DraftsPage />;
  const userMatch = location.pathname.match(/^\/users\/([^/]+)$/);
  if (userMatch) return <ProfilePage username={userMatch[1]} />;
  const postMatch = location.pathname.match(/^\/posts\/([^/]+)$/);
  if (postMatch) return <PostPage postId={postMatch[1]} />;
  return <FeedPage />;
}

export function App() {
  return <RouterProvider><SessionProvider><AppContent /></SessionProvider></RouterProvider>;
}
