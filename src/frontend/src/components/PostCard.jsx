import { Bookmark, Flag, Heart, MessageCircle, Paperclip, Send } from "lucide-react";
import { Link } from "../lib/router";

export function formatDate(value) {
  const minutes = Math.floor((Date.now() - new Date(value)) / 60000);
  return minutes < 1 ? "сейчас" : minutes < 60 ? `${minutes} мин` : minutes < 1440 ? `${Math.floor(minutes / 60)} ч` : new Date(value).toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}

function Media({ post }) {
  return post.media?.length > 0 && <div className={`post-media post-media-${Math.min(post.media.length, 2)}`}>{post.media.slice(0, 2).map((media) => media.kind === "video" ? <video key={media.id} controls src={media.url} /> : <img key={media.id} src={media.url} alt="Вложение публикации" />)}<span className="media-count"><Paperclip size={13} /> {post.media.length} вложения</span></div>;
}

export function PostCard({ post, onLike, onBookmark, onShare, onReport, detail = false }) {
  const author = post.author;
  const detailView = detail || /^\/posts\/[^/]+$/.test(window.location.pathname);
  return <article className="post-card">
    <header className="post-head"><Link to={`/users/${author.username}`} className="post-author"><span className="avatar">{author.username.slice(0, 2).toUpperCase()}</span><span><b>{author.display_name || author.username}</b><em>@{author.username} · {formatDate(post.created_at)}</em></span></Link><div className="post-head-actions"><span className="category-pill">{post.category}</span></div></header>
    {detailView ? <div className="post-body-link"><h2>{post.title}</h2><p>{post.content}</p><Media post={post} /></div> : <Link to={`/posts/${post.id}`} className="post-body-link"><h2>{post.title}</h2><p>{post.content}</p><Media post={post} /></Link>}
    <div className="tags">{post.tags.map((tag) => <span key={tag}>#{tag}</span>)}</div>
    <footer className={`post-actions ${detailView ? "post-actions-detail" : ""}`}><button className={post.liked_by_me ? "liked" : ""} onClick={() => onLike(post)}><Heart size={19} fill={post.liked_by_me ? "currentColor" : "none"} /> <b>{detailView ? "Нравится" : post.like_count}</b>{detailView && <span>{post.like_count}</span>}</button><Link to={`/posts/${post.id}`}><MessageCircle size={19} /> <b>{detailView ? "Ответить" : post.comment_count}</b>{detailView && <span>{post.comment_count}</span>}</Link><button onClick={() => onShare?.(post)} aria-label="Поделиться публикацией"><Send size={19} /> <b>{detailView ? "Копировать" : post.share_count}</b>{detailView && <span>{post.share_count}</span>}</button>{detailView && onReport && <button onClick={() => onReport()}><Flag size={17} /> <b>Жалоба</b></button>}<button className={`bookmark ${post.bookmarked_by_me ? "bookmarked" : ""}`} onClick={() => onBookmark(post)}><Bookmark size={19} fill={post.bookmarked_by_me ? "currentColor" : "none"} /></button></footer>
  </article>;
}
