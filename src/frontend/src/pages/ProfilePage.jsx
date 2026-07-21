import { useEffect, useRef, useState } from "react";
import { CalendarDays, Camera, Settings } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { Avatar, isBannedUser, isDeletedUser } from "../components/Avatar";
import { PostCard } from "../components/PostCard";
import { api } from "../lib/api";
import { sharePost } from "../lib/sharePost";
import { useRouter } from "../lib/router";
import { useSession } from "../session";
import "../styles/profile.css";

export function ProfilePage({ username }) {
  const { user: currentUser, refreshMe } = useSession();
  const { navigate } = useRouter();
  const own = !username || username === currentUser?.username;
  const target = username || currentUser?.username;
  const avatarInput = useRef(null);
  const coverInput = useRef(null);
  const [profile, setProfile] = useState(own ? currentUser : null);
  const [posts, setPosts] = useState([]);
  const [answers, setAnswers] = useState([]);
  const [postCursor, setPostCursor] = useState(null);
  const [answerCursor, setAnswerCursor] = useState(null);
  const [tab, setTab] = useState("posts");
  const [state, setState] = useState("loading");
  const [loadingMore, setLoadingMore] = useState(false);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ username: "", email: "", display_name: "", bio: "", profile_visibility: "public", posts_visibility: "public", comments_visibility: "public", current_password: "", new_password: "" });
  const [uploading, setUploading] = useState("");
  const [profileError, setProfileError] = useState("");

  useEffect(() => {
    if (!target) return;
    let cancelled = false;
    setState("loading");
    setPosts([]);
    setAnswers([]);
    setPostCursor(null);
    setAnswerCursor(null);
    setProfileError("");
    (own ? api.me() : api.user(target))
      .then(async (data) => {
        const [postResult, commentResult] = await Promise.allSettled([api.posts({ author: target }), api.userComments(target)]);
        if (cancelled) return;
        const postPage = postResult.status === "fulfilled" ? postResult.value : { items: [], next_cursor: null };
        const commentPage = commentResult.status === "fulfilled" ? commentResult.value : { items: [], next_cursor: null };
        setProfile(data);
        setForm({ username: data.username || "", email: data.email || "", display_name: data.display_name || "", bio: data.bio || "", profile_visibility: data.profile_visibility || "public", posts_visibility: data.posts_visibility || "public", comments_visibility: data.comments_visibility || "public", current_password: "", new_password: "" });
        setPosts(postPage.items);
        setAnswers(commentPage.items);
        setPostCursor(postPage.next_cursor);
        setAnswerCursor(commentPage.next_cursor);
        setState("ready");
      })
      .catch(() => {
        if (cancelled) return;
        setProfile(null);
        setPosts([]);
        setAnswers([]);
        setPostCursor(null);
        setAnswerCursor(null);
        setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [target, own]);

  const save = async (event) => {
    event.preventDefault();
    setProfileError("");
    try {
      const privacyReady = ["profile_visibility", "posts_visibility", "comments_visibility"].every((key) => key in profile);
      const payload = { username: form.username, email: form.email, display_name: form.display_name, bio: form.bio };
      if (privacyReady) Object.assign(payload, { profile_visibility: form.profile_visibility, posts_visibility: form.posts_visibility, comments_visibility: form.comments_visibility });
      if (form.new_password) Object.assign(payload, { current_password: form.current_password, new_password: form.new_password });
      const updated = await api.updateMe(payload);
      setProfile(updated);
      setForm((value) => ({ ...value, current_password: "", new_password: "" }));
      await refreshMe();
      setEditing(false);
      if (updated.username !== target) navigate("/me");
    } catch (cause) {
      setProfileError(cause.message || "Не удалось сохранить профиль");
    }
  };
  const loadMorePosts = async () => {
    if (!postCursor) return;
    setLoadingMore(true);
    try {
      const page = await api.posts({ author: target, cursor: postCursor });
      setPosts((current) => [...current, ...page.items]);
      setPostCursor(page.next_cursor);
    } finally {
      setLoadingMore(false);
    }
  };
  const loadMoreAnswers = async () => {
    if (!answerCursor) return;
    setLoadingMore(true);
    try {
      const page = await api.userComments(target, { cursor: answerCursor });
      setAnswers((current) => [...current, ...page.items]);
      setAnswerCursor(page.next_cursor);
    } finally {
      setLoadingMore(false);
    }
  };
  const updatePost = (id, next) => setPosts((current) => current.map((post) => (post.id === id ? next(post) : post)));
  const toggleLike = async (post) => {
    if (!currentUser) return navigate("/login");
    updatePost(post.id, (item) => ({ ...item, liked_by_me: !item.liked_by_me, like_count: Math.max(0, item.like_count + (item.liked_by_me ? -1 : 1)) }));
    try { post.liked_by_me ? await api.unlike(post.id) : await api.like(post.id); } catch { updatePost(post.id, () => post); }
  };
  const toggleBookmark = async (post) => {
    if (!currentUser) return navigate("/login");
    updatePost(post.id, (item) => ({ ...item, bookmarked_by_me: !item.bookmarked_by_me }));
    try { post.bookmarked_by_me ? await api.unbookmark(post.id) : await api.bookmark(post.id); } catch { updatePost(post.id, () => post); }
  };
  const share = async (post) => { try { const result = await sharePost(post); updatePost(post.id, (item) => ({ ...item, share_count: result.share_count })); } catch { } };
  const uploadProfileImage = async (event, purpose) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!file.type.startsWith("image/") || file.size > 5 * 1024 * 1024) return setUploading("Нужна картинка до 5 МБ.");
    setUploading("Загружаем…");
    try {
      const media = await api.uploadMedia(file, purpose);
      const updated = await api.updateMe(purpose === "avatar" ? { avatar_media_id: media.id } : { cover_media_id: media.id });
      setProfile(updated);
      await refreshMe();
      setUploading("");
    } catch (cause) {
      setUploading(cause.message || "Не удалось загрузить изображение");
    }
  };

  if (!target) return <AppShell title="Профиль"><div className="card-state"><b>Войдите, чтобы открыть профиль</b><button className="outline-button" onClick={() => navigate("/login")}>Войти</button></div></AppShell>;
  if (state === "loading") return <AppShell title="Профиль"><div className="card-state">Загружаем профиль…</div></AppShell>;
  if (state === "error") return <AppShell title="Профиль"><div className="card-state">Профиль не найден</div></AppShell>;
  const deletedProfile = isDeletedUser(profile);
  const bannedProfile = isBannedUser(profile);

  return <AppShell title="Профиль"><section className="profile-page">
    <section className="profile-hero">
      <div className="profile-cover" style={profile.cover_url ? { backgroundImage: `url(${profile.cover_url})` } : undefined} />
      <div className="profile-info"><span className={`profile-avatar${deletedProfile ? " profile-avatar-deleted" : ""}`}>{!deletedProfile && (profile.avatar_url ? <img src={profile.avatar_url} alt="" /> : profile.username.slice(0, 2).toUpperCase())}</span>{own && !deletedProfile && <button className="outline-button edit-profile" onClick={() => setEditing(!editing)}><Settings size={16} /> Редактировать профиль</button>}<h1>{deletedProfile ? "Удаленный аккаунт" : profile.display_name || profile.username}{bannedProfile && <i className="profile-status">Заблокирован</i>}</h1>{!deletedProfile && <span className="handle">@{profile.username}</span>}<p>{deletedProfile ? "Этот аккаунт удален." : profile.bio || "Расскажите немного о себе в настройках профиля."}</p><div className="profile-meta"><span><CalendarDays size={15} /> С нами с {new Date(profile.created_at).toLocaleDateString("ru-RU", { month: "long", year: "numeric" })}</span><b>{profile.posts_count} публикаций</b></div></div>
    </section>
    {editing && <form className="profile-edit" onSubmit={save}>{profileError && <div className="form-error" role="alert">{profileError}</div>}<label>Username<input value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} minLength="3" maxLength="30" pattern="[A-Za-z0-9_]+" required /></label><label>Email<input value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} type="email" required /><small>Никогда не показывается в публичном профиле.</small></label><label>Отображаемое имя<input value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.target.value })} maxLength="80" /></label><label>О себе<textarea value={form.bio} onChange={(event) => setForm({ ...form, bio: event.target.value })} maxLength="500" /></label><div className="password-settings"><label>Текущий пароль<input value={form.current_password} onChange={(event) => setForm({ ...form, current_password: event.target.value })} type="password" autoComplete="current-password" /></label><label>Новый пароль<input value={form.new_password} onChange={(event) => setForm({ ...form, new_password: event.target.value })} type="password" minLength="10" maxLength="128" autoComplete="new-password" /></label></div><div className="profile-image-controls"><input ref={avatarInput} className="visually-hidden" type="file" accept="image/*" onChange={(event) => uploadProfileImage(event, "avatar")} /><input ref={coverInput} className="visually-hidden" type="file" accept="image/*" onChange={(event) => uploadProfileImage(event, "cover")} /><button type="button" className="outline-button" onClick={() => avatarInput.current?.click()}><Camera size={16} /> Изменить аватар</button><button type="button" className="outline-button" onClick={() => coverInput.current?.click()}>Изменить обложку</button>{uploading && <small>{uploading}</small>}</div><fieldset className="privacy-settings" disabled={!["profile_visibility", "posts_visibility", "comments_visibility"].every((key) => key in profile)}><legend>Приватность</legend><small>{["profile_visibility", "posts_visibility", "comments_visibility"].every((key) => key in profile) ? "Выберите, что видно другим пользователям." : "Станет доступно после обновления backend."}</small>{[["profile_visibility", "Профиль"], ["posts_visibility", "Публикации"], ["comments_visibility", "Комментарии"]].map(([key, label]) => <label className="privacy-row" key={key}>{label}<select value={form[key]} onChange={(event) => setForm({ ...form, [key]: event.target.value })}><option value="public">Видно всем</option><option value="private">Только мне</option></select></label>)}</fieldset><button className="primary">Сохранить</button></form>}
    <nav className="profile-tabs"><button className={tab === "posts" ? "selected" : ""} onClick={() => setTab("posts")}>Публикации</button><button className={tab === "answers" ? "selected" : ""} onClick={() => setTab("answers")}>Ответы</button></nav>
    {tab === "posts" ? <>{posts.length ? posts.map((post) => <PostCard key={post.id} post={post} onLike={toggleLike} onBookmark={toggleBookmark} onShare={share} />) : <div className="card-state">Публикаций пока нет</div>}{postCursor && <button className="outline-button load-more" disabled={loadingMore} onClick={loadMorePosts}>Показать ещё</button>}</> : <>{answers.length ? <section className="answers-list">{answers.map((comment) => <article className="answer" key={comment.id}><Avatar user={profile} /><div><b>Ответ в публикации</b><p>{comment.is_deleted ? "Комментарий удалён автором" : comment.body}</p></div></article>)}</section> : <div className="card-state">Ответов пока нет</div>}{answerCursor && <button className="outline-button load-more" disabled={loadingMore} onClick={loadMoreAnswers}>Показать ещё</button>}</>}
  </section></AppShell>;
}
