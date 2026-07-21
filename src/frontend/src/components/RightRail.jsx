import { Ellipsis, Search } from "lucide-react";

export function RightRail() {
  const ideas = [["Команды · сегодня", "Ссылки для кампаний и релизов", "папки и метки"], ["Аналитика · 7 дней", "Отслеживайте переходы без таблиц", "access count"], ["Безопасность", "Жалобы проверяются модераторами", "shortcode reports"]];
  return <div className="rail-stack"><label className="search-box"><Search size={17} /><input placeholder="Поиск по ссылкам" /></label><section className="rail-card"><header><h3>Полезно сейчас</h3><Ellipsis size={19} /></header>{ideas.map(([meta, title, count]) => <div className="trend" key={title}><small>{meta}</small><b>{title}</b><small>{count}</small></div>)}</section><section className="rail-card authors"><h3>Быстрые действия</h3>{["Создать ссылку", "Разложить по папкам", "Проверить жалобы"].map((name) => <div className="author-line" key={name}><span className="avatar">{name.slice(0, 2).toUpperCase()}</span><span><b>{name}</b><small>Simple</small></span></div>)}</section></div>;
}
