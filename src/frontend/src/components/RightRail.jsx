import { Search } from "lucide-react";

export function RightRail() {
  return <div className="rail-stack">
    <label className="search-box"><Search size={17} /><input placeholder="Поиск в Simple" /></label>
    <section className="rail-card"><h3>Сейчас в тренде</h3><p className="rail-empty">Появится, когда backend отдаст тренды.</p></section>
    <section className="rail-card"><h3>Активные авторы</h3><p className="rail-empty">Появятся, когда backend отдаст авторов.</p></section>
  </div>;
}
