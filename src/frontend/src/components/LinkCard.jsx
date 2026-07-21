import { BarChart3, Copy, ExternalLink, Folder, Link as LinkIcon } from "lucide-react";

export function LinkCard({ item, onCopy }) {
  const title = item.label || item.url;
  return <article className="post-card link-card">
    <header className="post-head"><div className="post-author"><span className="avatar"><LinkIcon size={18} /></span><span><b>{title}</b><em>{new Date(item.created_at).toLocaleDateString("ru-RU")}</em></span></div><div className="post-head-actions"><span className={`category-pill ${item.is_active ? "" : "muted-pill"}`}>{item.is_active ? "Активна" : "Отключена"}</span></div></header>
    <div className="post-body-link"><h2>{item.short_url}</h2><p>{item.url}</p></div>
    <div className="tags"><span>#{item.shortcode}</span>{item.folder_id && <span><Folder size={12} /> folder {item.folder_id}</span>}</div>
    <footer className="post-actions"><button onClick={() => onCopy(item)}><Copy size={18} /> <b>Копировать</b></button><a href={item.short_url} target="_blank" rel="noreferrer"><ExternalLink size={18} /> <b>Открыть</b></a><span className="link-stat"><BarChart3 size={18} /> <b>{item.access_count}</b></span></footer>
  </article>;
}
