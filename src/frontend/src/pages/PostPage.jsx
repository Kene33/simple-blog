import { useEffect, useState } from "react";
import { ArrowLeft, Flag, Pencil, Send, Trash2 } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { Avatar } from "../components/Avatar";
import { LinkifiedText } from "../components/LinkifiedText";
import { PostCard } from "../components/PostCard";
import { ReportModal } from "../components/ReportModal";
import { ModerationActionModal } from "../components/ModerationActionModal";
import { api } from "../lib/api";
import { groupComments, mergeComments } from "../lib/commentTree";
import { sharePost } from "../lib/sharePost";
import { Link, useRouter } from "../lib/router";
import { useSession } from "../session";
import "../styles/post.css";
import "../styles/comment-author.css";

function Comment({ comment, replies, replyState, currentUser, onReply, onUpdate, onDelete, onReport, onLogin, onLoadReplies, onToggleReplies }) {
  const [reply, setReply] = useState(false);
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(comment.body);
  const own = comment.author.id === currentUser?.id;
  const loaded = replyState.loaded[comment.id];
  const expanded = replyState.expanded[comment.id];
  const loading = replyState.loading[comment.id];
  const nextCursor = replyState.cursors[comment.id];
  const edited = comment.updated_at && comment.created_at && new Date(comment.updated_at).getTime() > new Date(comment.created_at).getTime() + 1000;
  const author = comment.author;
  const authorPath = author?.username && author.status !== "deleted" ? `/users/${author.username}` : null;

  function submitReply(event) {
    event.preventDefault();
    onReply(comment.id, event.currentTarget.body.value);
    event.currentTarget.reset();
    setReply(false);
  }

  function submitEdit(event) {
    event.preventDefault();
    onUpdate(comment.id, text);
    setEditing(false);
  }

  return <article className={`comment ${comment.is_deleted ? "deleted" : ""}`}>
    {authorPath ? <Link className="comment-author-avatar" to={authorPath}><Avatar user={author} /></Link> : <Avatar user={author} />}
    <div>
      <b>{authorPath ? <Link className="comment-author" to={authorPath}>{author.display_name || author.username}</Link> : author?.display_name || author?.username || "Удалённый аккаунт"}</b>
      {comment.is_deleted ? <small>Комментарий удалён автором</small> : editing ? <form className="comment-inline-form" onSubmit={submitEdit}><textarea value={text} onChange={(event) => setText(event.target.value)} maxLength="2000" autoFocus /><button>Сохранить</button><button type="button" onClick={() => setEditing(false)}>Отмена</button></form> : <small><LinkifiedText>{comment.body}</LinkifiedText>{edited && <em className="comment-edited">изменено</em>}</small>}
      {!comment.is_deleted && <div className="comment-actions"><button onClick={() => currentUser ? setReply(!reply) : onLogin()}>Ответить</button>{own && <><button onClick={() => setEditing(true)}>Изменить</button><button onClick={() => onDelete(comment.id)}>Удалить</button></>}<button onClick={() => onReport(comment.id)}>Пожаловаться</button></div>}
      {reply && <form className="comment-inline-form" onSubmit={submitReply}><textarea name="body" placeholder="Написать ответ" maxLength="2000" autoFocus /><button>Ответить</button><button type="button" onClick={() => setReply(false)}>Отмена</button></form>}
      <div className="comment-thread-actions">
        {comment.reply_count > 0 && (!loaded ? <button disabled={loading} onClick={() => onLoadReplies(comment.id)}>{loading ? "Загружаем ответы…" : "Показать ответы"}</button> : replies.length > 0 ? <button aria-expanded={expanded} onClick={() => onToggleReplies(comment.id)}>{expanded ? "Скрыть ответы" : "Показать ответы"}</button> : null)}
      </div>
      {loaded && expanded && replies.length > 0 && <div className="comment-replies">
        {replies.map((item) => <Comment key={item.id} comment={item} replies={replyState.groups.get(item.id) || []} replyState={replyState} currentUser={currentUser} onReply={onReply} onUpdate={onUpdate} onDelete={onDelete} onReport={onReport} onLogin={onLogin} onLoadReplies={onLoadReplies} onToggleReplies={onToggleReplies} />)}
        {nextCursor && <button className="comment-more" disabled={loading} onClick={() => onLoadReplies(comment.id, true)}>{loading ? "Загружаем…" : "Показать ещё ответы"}</button>}
      </div>}
    </div>
  </article>;
}

export function PostPage({ postId }) {
  const { user, isAdmin, isStaff } = useSession();
  const { navigate } = useRouter();
  const [post, setPost] = useState(null);
  const [comments, setComments] = useState([]);
  const [commentCursor, setCommentCursor] = useState(null);
  const [loadedReplies, setLoadedReplies] = useState({});
  const [expandedReplies, setExpandedReplies] = useState({});
  const [replyCursors, setReplyCursors] = useState({});
  const [loadingReplies, setLoadingReplies] = useState({});
  const [loadingComments, setLoadingComments] = useState(false);
  const [body, setBody] = useState("");
  const [state, setState] = useState("loading");
  const [error, setError] = useState("");
  const [reportTarget, setReportTarget] = useState(null);
  const [moderationTarget, setModerationTarget] = useState(null);

  async function load() {
    const [postValue, page] = await Promise.all([api.post(postId), api.comments(postId)]);
    const replies = await loadRootReplies(page.items);
    return { postValue, page: { ...page, items: mergeComments(page.items, replies.items) }, replies };
  }

  async function loadRootReplies(roots) {
    const pages = await Promise.all(roots.map((comment) => api.comments(postId, { parent_id: comment.id, limit: 3 })));
    return {
      items: pages.flatMap((page) => page.items),
      loaded: Object.fromEntries(roots.map((comment) => [comment.id, true])),
      expanded: Object.fromEntries(roots.filter((_, index) => pages[index].items.length > 0).map((comment) => [comment.id, true])),
      cursors: Object.fromEntries(roots.map((comment, index) => [comment.id, pages[index].next_cursor]))
    };
  }

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    setLoadedReplies({});
    setExpandedReplies({});
    setReplyCursors({});
    setLoadingReplies({});
    load().then(({ postValue, page, replies }) => {
      if (cancelled) return;
      setPost(postValue);
      setComments(page.items);
      setCommentCursor(page.next_cursor);
      setLoadedReplies(replies.loaded);
      setExpandedReplies(replies.expanded);
      setReplyCursors(replies.cursors);
      setState("ready");
    }).catch(() => {
      if (!cancelled) setState("error");
    });
    return () => { cancelled = true; };
  }, [postId]);

  useEffect(() => {
    if (!post) return;
    const title = `${post.title} — Simple`;
    const description = post.content?.slice(0, 155) || "Публикация и обсуждение в Simple.";
    document.title = title;
    document.querySelector('meta[name="description"]')?.setAttribute("content", description);
    document.querySelector('meta[property="og:title"]')?.setAttribute("content", title);
    document.querySelector('meta[property="og:description"]')?.setAttribute("content", description);
    document.querySelector('meta[property="og:url"]')?.setAttribute("content", `${window.location.origin}/posts/${post.id}`);
  }, [post]);

  async function toggle(item, kind) {
    if (!user) return navigate("/login");
    const next = kind === "like" ? { ...item, liked_by_me: !item.liked_by_me, like_count: item.like_count + (item.liked_by_me ? -1 : 1) } : { ...item, bookmarked_by_me: !item.bookmarked_by_me };
    setPost(next);
    try {
      if (kind === "like") item.liked_by_me ? await api.unlike(item.id) : await api.like(item.id);
      else item.bookmarked_by_me ? await api.unbookmark(item.id) : await api.bookmark(item.id);
    } catch {
      setPost(item);
    }
  }

  async function share(item) {
    try {
      const result = await sharePost(item);
      setPost({ ...item, share_count: result.share_count });
    } catch (cause) {
      if (cause.name !== "AbortError") setError("Не удалось поделиться публикацией");
    }
  }

  async function addComment(parentId, value) {
    if (!user) return navigate("/login");
    if (!value.trim()) return;
    try {
      const comment = await api.createComment(postId, { body: value.trim(), parent_id: parentId });
      setComments((items) => mergeComments([comment, ...items.map((item) => item.id === parentId ? { ...item, reply_count: item.reply_count + 1 } : item)], []));
      if (parentId) {
        setLoadedReplies((items) => ({ ...items, [parentId]: true }));
        setExpandedReplies((items) => ({ ...items, [parentId]: true }));
      }
      setPost((item) => ({ ...item, comment_count: item.comment_count + 1 }));
      setBody("");
    } catch (cause) {
      setError(cause.message);
    }
  }

  async function updateComment(id, value) {
    if (!value.trim()) return;
    try {
      const updated = await api.updateComment(id, { body: value.trim() });
      setComments((items) => items.map((item) => item.id === id ? updated : item));
    } catch (cause) {
      setError(cause.message);
    }
  }

  async function removeComment(id) {
    try {
      await api.deleteComment(id);
      const removed = comments.find((item) => item.id === id);
      setComments((items) => items.map((item) => item.id === id ? { ...item, is_deleted: true, body: "" } : item.id === removed?.parent_id ? { ...item, reply_count: Math.max(0, item.reply_count - 1) } : item));
      setPost((item) => ({ ...item, comment_count: Math.max(0, item.comment_count - 1) }));
    } catch (cause) {
      setError(cause.message);
    }
  }

  async function loadReplies(parentId, more = false) {
    if (loadingReplies[parentId]) return;
    setLoadingReplies((items) => ({ ...items, [parentId]: true }));
    try {
      const page = await api.comments(postId, { parent_id: parentId, limit: 3, cursor: more ? replyCursors[parentId] : undefined });
      setComments((items) => mergeComments(items, page.items));
      setLoadedReplies((items) => ({ ...items, [parentId]: true }));
      setExpandedReplies((items) => ({ ...items, [parentId]: true }));
      setReplyCursors((items) => ({ ...items, [parentId]: page.next_cursor }));
    } catch (cause) {
      setError(cause.message);
    } finally {
      setLoadingReplies((items) => ({ ...items, [parentId]: false }));
    }
  }

  async function loadMoreComments() {
    if (!commentCursor) return;
    setLoadingComments(true);
    try {
      const page = await api.comments(postId, { cursor: commentCursor });
      const replies = await loadRootReplies(page.items);
      setComments((items) => mergeComments(items, mergeComments(page.items, replies.items)));
      setCommentCursor(page.next_cursor);
      setLoadedReplies((items) => ({ ...items, ...replies.loaded }));
      setExpandedReplies((items) => ({ ...items, ...replies.expanded }));
      setReplyCursors((items) => ({ ...items, ...replies.cursors }));
    } catch (cause) {
      setError(cause.message);
    } finally {
      setLoadingComments(false);
    }
  }

  async function removePost() {
    if (!window.confirm("Удалить публикацию?")) return;
    try {
      await api.deletePost(post.id);
      navigate("/");
    } catch (cause) {
      setError(cause.message);
    }
  }

  async function moderatePost(reason) {
    await api.hidePost(post.id, reason);
    navigate("/");
  }

  async function banAuthor(reason) {
    await api.moderateUser(post.author.id, { action: "ban", reason });
    setPost((item) => ({ ...item, author: { ...item.author, status: "banned", is_banned: true } }));
  }

  if (state === "loading") return <AppShell title="Публикация"><div className="card-state">Загружаем публикацию…</div></AppShell>;
  if (state === "error") return <AppShell title="Публикация"><div className="card-state"><b>Публикация не найдена</b><button className="outline-button" onClick={() => navigate("/")}>К ленте</button></div></AppShell>;

  const replyState = { groups: groupComments(comments), loaded: loadedReplies, expanded: expandedReplies, cursors: replyCursors, loading: loadingReplies };
  const rootComments = replyState.groups.get(null) || [];

  return <AppShell title="Публикация">
    <section className="post-page">
      <button className="back-link button-link" onClick={() => navigate("/")}><ArrowLeft size={17} /> Назад к ленте</button>
      <PostCard detail post={post} onReport={() => user ? setReportTarget({ postId: post.id }) : navigate("/login")} onLike={(item) => toggle(item, "like")} onBookmark={(item) => toggle(item, "bookmark")} onShare={share} />
      {(isAdmin || isStaff) && <div className="post-owner-actions">{isAdmin && <button className="danger-button" onClick={() => setModerationTarget("post")}>Удалить пост</button>}<button className="outline-button" onClick={() => setModerationTarget("author")}>Заблокировать автора</button></div>}
      {post.author.id === user?.id && <div className="post-owner-actions"><button className="outline-button" onClick={() => navigate(`/posts/${post.id}/edit`)}><Pencil size={15} /> Редактировать</button><button className="danger-button" onClick={removePost}><Trash2 size={15} /> Удалить</button></div>}
      <section className="comments-card">
        <header><h2>Комментарии <span>{post.comment_count}</span></h2><button className="report-link" onClick={() => user ? setReportTarget({ postId: post.id }) : navigate("/login")}><Flag size={15} /> Жалоба</button></header>
        {user && <form className="comment-form" onSubmit={(event) => { event.preventDefault(); addComment(null, body); }}><Avatar user={user} /><textarea value={body} onChange={(event) => setBody(event.target.value)} placeholder="Добавить комментарий" maxLength="2000" /><button className="primary" aria-label="Отправить комментарий"><Send size={17} /> Отправить</button></form>}
        {error && <div className="form-error">{error}</div>}
        <div className="comment-list">{rootComments.map((comment) => <Comment key={comment.id} comment={comment} replies={replyState.groups.get(comment.id) || []} replyState={replyState} currentUser={user} onReply={addComment} onUpdate={updateComment} onDelete={removeComment} onReport={(commentId) => user ? setReportTarget({ commentId }) : navigate("/login")} onLogin={() => navigate("/login")} onLoadReplies={loadReplies} onToggleReplies={(id) => setExpandedReplies((items) => ({ ...items, [id]: !items[id] }))} />)}</div>
        {commentCursor && <button className="outline-button load-more" disabled={loadingComments} onClick={loadMoreComments}>{loadingComments ? "Загружаем…" : "Показать ещё комментарии"}</button>}
      </section>
    </section>
    {reportTarget && <ReportModal {...reportTarget} onClose={() => setReportTarget(null)} />}
    {moderationTarget === "post" && <ModerationActionModal title="Удалить публикацию?" description="Публикация будет скрыта из ленты." onClose={() => setModerationTarget(null)} onSubmit={moderatePost} />}
    {moderationTarget === "author" && <ModerationActionModal title="Заблокировать автора?" description="Автор останется виден, но получит статус заблокированного пользователя." onClose={() => setModerationTarget(null)} onSubmit={banAuthor} />}
  </AppShell>;
}
