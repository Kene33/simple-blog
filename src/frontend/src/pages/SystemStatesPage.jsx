import { AlertCircle, FileQuestion, Flag, KeyRound, LoaderCircle, RefreshCw, Search } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { useRouter } from "../lib/router";
import "../styles/system-states.css";

const states = [
  ["LOADING", "Загружаем публикации", "Карточки-скелетоны сохраняют структуру ленты.", LoaderCircle, "К ленте"],
  ["EMPTY", "Ничего не найдено", "Измените запрос или сбросьте активные фильтры.", Search, "К ленте"],
  ["403", "Нет доступа", "Эта страница доступна только администраторам.", KeyRound, "К ленте"],
  ["404", "Публикация не найдена", "Возможно, автор удалил её или ссылка устарела.", AlertCircle, "К ленте"],
  ["API ERROR", "Не удалось загрузить", "Проверьте соединение и попробуйте ещё раз.", RefreshCw, "Повторить"],
  ["409", "Жалоба уже открыта", "Обращение принято и находится на рассмотрении.", Flag, "К ленте"]
];

export function SystemStatesPage() {
  const { navigate } = useRouter();
  return <AppShell title="Системные состояния"><section className="states-page"><header><h1>Системные состояния</h1><p>Общий язык обратной связи во всём интерфейсе</p></header><div className="states-grid">{states.map(([code, title, description, Icon, action]) => <article className="state-card" key={code}><span className="state-icon"><Icon size={22} /></span><small>{code}</small><h2>{title}</h2><p>{description}</p><button className="outline-button" onClick={() => action === "Повторить" ? window.location.reload() : navigate("/")}>{action}</button></article>)}</div></section></AppShell>;
}
