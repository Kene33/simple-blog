import { useEffect, useState } from "react";
import { Bookmark, ChevronLeft, ChevronRight, Flag, Heart, MessageCircle, Paperclip, Send, X } from "lucide-react";
import { Avatar } from "./Avatar";
import { Link } from "../lib/router";

export function formatDate(value) {
  const minutes = Math.floor((Date.now() - new Date(value)) / 60000);
  return minutes < 1 ? "сейчас" : minutes < 60 ? `${minutes} мин` : minutes < 1440 ? `${Math.floor(minutes / 60)} ч` : new Date(value).toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}

function Media({ post, onOpen }) {
  const media = post.media || [];
  if (!media.length) return null;
  const open = () => onOpen(0);
  return <div className={`post-media post-media-${Math.min(media.length, 2)}`} role="button" tabIndex={0} aria-label="Открыть вложения публикации" onClick={open} onKeyDown={(event) => (event.key === "Enter" || event.key === " ") && (event.preventDefault(), open())}>{media.slice(0, 2).map((item) => item.kind === "video" ? <video key={item.id} muted preload="metadata" src={item.url} /> : <img key={item.id} src={item.url} alt="Вложение публикации" />)}<span className="media-count"><Paperclip size={13} /> {media.length} вложения</span></div>;
}

function MediaViewer({ media, currentIndex, onClose, onChange }) {
  const current = media[currentIndex];
  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose();
      if (event.key === "ArrowLeft") onChange(-1);
      if (event.key === "ArrowRight") onChange(1);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onChange, onClose]);
  if (!current) return null;
  return <div className="media-viewer-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
    <section className="media-viewer" role="dialog" aria-modal="true" aria-label="Просмотр вложения">
      <button className="media-viewer-close" onClick={onClose} aria-label="Закрыть просмотр"><X /></button>
      {current.kind === "video" ? <video controls autoPlay src={current.url} /> : <img src={current.url} alt="Вложение публикации" />}
      {media.length > 1 && <><button className="media-viewer-nav media-viewer-prev" onClick={() => onChange(-1)} aria-label="Предыдущее вложение"><ChevronLeft /></button><span className="media-viewer-position">{currentIndex + 1} / {media.length}</span><button className="media-viewer-nav media-viewer-next" onClick={() => onChange(1)} aria-label="Следующее вложение"><ChevronRight /></button></>}
    </section>
  </div>;
}

function categoryName(category) {
  return typeof category === "string" ? category : category?.name || "Без категории";
}

export function PostCard({ post, onLike, onBookmark, onShare, onReport, detail = false }) {
  const author = post.author;
  const detailView = detail || /^\/posts\/[^/]+$/.test(window.location.pathname);
  const [mediaIndex, setMediaIndex] = useState(null);
  const shiftMedia = (step) => setMediaIndex((index) => (index + step + post.media.length) % post.media.length);
  return <article className="post-card">
    <header className="post-head"><Link to={`/users/${author.username}`} className="post-author"><Avatar user={author} /><span><b>{author.display_name || author.username}</b><em>@{author.username} · {formatDate(post.created_at)}</em></span></Link><div className="post-head-actions"><span className="category-pill">{categoryName(post.category)}</span></div></header>
    {detailView ? <div className="post-body-link"><h2>{post.title}</h2><p>{post.content}</p><Media post={post} onOpen={setMediaIndex} /></div> : <><Link to={`/posts/${post.id}`} className="post-body-link"><h2>{post.title}</h2><p>{post.content}</p></Link><div className="post-media-shell"><Media post={post} onOpen={setMediaIndex} /></div></>}
    <div className="tags">{post.tags.map((tag) => <span key={tag}>#{tag}</span>)}</div>
    <footer className={`post-actions ${detailView ? "post-actions-detail" : ""}`}><button className={post.liked_by_me ? "liked" : ""} onClick={() => onLike(post)}><Heart size={19} fill={post.liked_by_me ? "currentColor" : "none"} /> <b>{detailView ? "Нравится" : post.like_count}</b>{detailView && <span>{post.like_count}</span>}</button><Link to={`/posts/${post.id}`}><MessageCircle size={19} /> <b>{detailView ? "Ответить" : post.comment_count}</b>{detailView && <span>{post.comment_count}</span>}</Link><button onClick={() => onShare?.(post)} aria-label="Поделиться публикацией"><Send size={19} /> <b>{detailView ? "Копировать" : post.share_count}</b>{detailView && <span>{post.share_count}</span>}</button>{detailView && onReport && <button onClick={() => onReport()}><Flag size={17} /> <b>Жалоба</b></button>}<button className={`bookmark ${post.bookmarked_by_me ? "bookmarked" : ""}`} onClick={() => onBookmark(post)}><Bookmark size={19} fill={post.bookmarked_by_me ? "currentColor" : "none"} /></button></footer>
    {mediaIndex !== null && <MediaViewer media={post.media} currentIndex={mediaIndex} onClose={() => setMediaIndex(null)} onChange={shiftMedia} />}
  </article>;
}
