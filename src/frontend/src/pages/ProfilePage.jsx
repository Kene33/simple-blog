import { useEffect, useRef, useState } from "react";
import { CalendarDays, Camera, Settings } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { PostCard } from "../components/PostCard";
import { api } from "../lib/api";
import { useSession } from "../session";
import "../styles/profile.css";

export function ProfilePage({ username }) {
  const { user: currentUser } = useSession();
  const own = !username || username === currentUser?.email;
  const target = username || currentUser?.email;
  const avatarInput = useRef(null);
  const [profile, setProfile] = useState(own ? currentUser : null);
  const [posts, setPosts] = useState([]);
  const [answers, setAnswers] = useState([]);
  const [postCursor, setPostCursor] = useState(null);
  const [answerCursor, setAnswerCursor] = useState(null);
  const [tab, setTab] = useState("posts");
  const [state, setState] = useState("loading");
  const [loadingMore, setLoadingMore] = useState(false);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ display_name: "", bio: "" });
  const [uploading, setUploading] = useState("");

  useEffect(() => {
    if (!target) return;
    setState("loading");
    Promise.all([own ? api.me() : api.user(target).catch(() => null), api.posts({ author: target }).catch(() => ({ items: [], next_cursor: null })), api.userComments(target).catch(() => ({ items: [], next_cursor: null }))])
      .then(([data, postPage, commentPage]) => {
        if (!data) throw new Error("Profile not found");
        setProfile(data);
        setForm({ display_name: data.display_name || "", bio: "" });
        setPosts(postPage.items);
        setAnswers(commentPage.items);
        setPostCursor(postPage.next_cursor);
        setAnswerCursor(commentPage.next_cursor);
        setState("ready");
      })
      .catch(() => setState("error"));
  }, [target, own]);

  const save = async (event) => {
    event.preventDefault();
    const updated = await api.updateMe({ display_name: form.display_name });
    setProfile(updated);
    setEditing(false);
  };
  const loadMorePosts = async () => {
    if (!postCursor) return;
    setLoadingMore(true);
    const page = await api.posts({ author: target, cursor: postCursor });
    setPosts((current) => [...current, ...page.items]);
    setPostCursor(page.next_cursor);
    setLoadingMore(false);
  };
  const loadMoreAnswers = async () => {
    if (!answerCursor) return;
    setLoadingMore(true);
    const page = await api.userComments(target, { cursor: answerCursor });
    setAnswers((current) => [...current, ...page.items]);
    setAnswerCursor(page.next_cursor);
    setLoadingMore(false);
  };
  const updatePost = (id, next) => setPosts((current) => current.map((post) => (post.id === id ? next(post) : post)));
  const toggleLike = async (post) => {
    if (post.liked_by_me) {
      await api.unlike(post.id);
      updatePost(post.id, (item) => ({ ...item, liked_by_me: false, like_count: Math.max(0, item.like_count - 1) }));
    } else {
      const result = await api.like(post.id);
      updatePost(post.id, (item) => ({ ...item, liked_by_me: true, like_count: result.like_count }));
    }
  };
  const toggleBookmark = async (post) => {
    if (post.bookmarked_by_me) {
      await api.unbookmark(post.id);
      updatePost(post.id, (item) => ({ ...item, bookmarked_by_me: false }));
    } else {
      await api.bookmark(post.id);
      updatePost(post.id, (item) => ({ ...item, bookmarked_by_me: true }));
    }
  };
  const uploadProfileImage = async (event, purpose) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!file.type.startsWith("image/") || file.size > 2 * 1024 * 1024) return setUploading("Нужна картинка до 2 МБ.");
    setUploading("Загружаем…");
    try {
      const media = await api.uploadMedia(file, purpose);
      setProfile(media);
      setUploading("");
    } catch (cause) {
      setUploading(cause.message || "Не удалось загрузить изображение");
    }
  };

  if (state === "loading") return <AppShell title="Профиль"><div className="card-state">Загружаем профиль…</div></AppShell>;
  if (state === "error") return <AppShell title="Профиль"><div className="card-state">Профиль не найден</div></AppShell>;

  const profileName = profile.display_name || profile.email || "";
  const initials = profileName.slice(0, 2).toUpperCase();

  return <AppShell title="Профиль"><section className="profile-page">
    <section className="profile-hero">
      <div className="profile-cover" />
      <div className="profile-info"><span className="profile-avatar">{profile.avatar_url ? <img src={profile.avatar_url} alt="" /> : initials}</span>{own && <button className="outline-button edit-profile" onClick={() => setEditing(!editing)}><Settings size={16} /> Редактировать профиль</button>}<h1>{profileName}</h1><span className="handle">{profile.email}</span><p>{profile.email_verified ? "Email подтверждён" : "Email ожидает подтверждения"}</p><div className="profile-meta"><span><CalendarDays size={15} /> С нами с {new Date(profile.created_at).toLocaleDateString("ru-RU", { month: "long", year: "numeric" })}</span><b>{profile.posts_count || 0} публикаций</b></div></div>
    </section>
    {editing && <form className="profile-edit" onSubmit={save}><label>Отображаемое имя<input value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.target.value })} maxLength="120" /></label><button className="primary">Сохранить</button></form>}
    {own && <section className="profile-private"><span>Email <b>{profile.email}</b>{uploading && <small>{uploading}</small>}</span><input ref={avatarInput} className="visually-hidden" type="file" accept="image/*" onChange={(event) => uploadProfileImage(event, "avatar")} /><button className="outline-button" onClick={() => avatarInput.current?.click()}><Camera size={16} /> Изменить avatar</button></section>}
    <nav className="profile-tabs"><button className={tab === "posts" ? "selected" : ""} onClick={() => setTab("posts")}>Публикации</button><button className={tab === "answers" ? "selected" : ""} onClick={() => setTab("answers")}>Ответы</button></nav>
    {tab === "posts" ? <>{posts.map((post) => <PostCard key={post.id} post={post} onLike={toggleLike} onBookmark={toggleBookmark} />)}{postCursor && <button className="outline-button load-more" disabled={loadingMore} onClick={loadMorePosts}>Показать ещё</button>}</> : <><section className="answers-list">{answers.map((comment) => <article className="answer" key={comment.id}><span className="avatar">{initials}</span><div><b>Ответ в публикации</b><p>{comment.is_deleted ? "Комментарий удалён автором" : comment.body}</p></div></article>)}</section>{answerCursor && <button className="outline-button load-more" disabled={loadingMore} onClick={loadMoreAnswers}>Показать ещё</button>}</>}
  </section></AppShell>;
}
