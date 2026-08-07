import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  Check,
  CheckCheck,
  LoaderCircle,
  MessageCircle,
  MoreHorizontal,
  Search,
  Send,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";
import { AppShell } from "../components/AppShell";
import { Avatar } from "../components/Avatar";
import { api } from "../lib/api";
import {
  createMessagesSocket,
  mergeUniqueMessages,
} from "../lib/messagesSocket";
import { enablePushNotifications } from "../lib/pushNotifications";
import { useRouter } from "../lib/router";
import { useSession } from "../session";
import "../styles/messages.css";

const errorStatus = (error) => error?.status;
const participantOf = (conversation) =>
  conversation?.participant ||
  conversation?.user ||
  conversation?.recipient ||
  {};
const conversationLabel = (conversation) =>
  conversation?.kind === "group"
    ? conversation.title || "Группа"
    : participantOf(conversation).display_name ||
      participantOf(conversation).username ||
      "Пользователь";

function SoonState() {
  return (
    <div className="messages-soon">
      <MessageCircle size={28} />
      <b>Личные сообщения скоро появятся</b>
      <span>Backend API диалогов ещё подключается. Интерфейс уже готов.</span>
    </div>
  );
}

function MessageBubble({ message, own, onEdit, onDelete, onReport }) {
  const [menu, setMenu] = useState(false);
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(message.body || "");
  const deleted = message.is_deleted || message.deleted;
  const edited =
    message.updated_at &&
    message.created_at &&
    new Date(message.updated_at) > new Date(message.created_at);
  const save = (event) => {
    event.preventDefault();
    if (text.trim()) onEdit(message.id, text.trim());
    setEditing(false);
  };
  return (
    <div className={`message-row ${own ? "own" : ""}`}>
      <div className={`message-bubble ${deleted ? "deleted" : ""}`}>
        {deleted ? (
          <span>Сообщение удалено</span>
        ) : editing ? (
          <form onSubmit={save}>
            <textarea
              value={text}
              onChange={(event) => setText(event.target.value)}
              maxLength={4000}
              autoFocus
            />
            <button type="submit">Сохранить</button>
          </form>
        ) : (
          <>
            <p>{message.body}</p>
            {edited && <small>изменено</small>}
          </>
        )}
        <footer>
          <time>
            {message.created_at
              ? new Date(message.created_at).toLocaleTimeString("ru-RU", {
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : ""}
          </time>
          {own && !deleted && (
            <span className="read-state">
              {message.read_by_recipient ? (
                <CheckCheck size={14} />
              ) : (
                <Check size={14} />
              )}
            </span>
          )}
          {own && !deleted && (
            <button
              className="message-menu-trigger"
              onClick={() => setMenu((value) => !value)}
              aria-label="Действия сообщения"
            >
              <MoreHorizontal size={15} />
            </button>
          )}
        </footer>
        {menu && (
          <div className="message-menu">
            <button
              onClick={() => {
                setEditing(true);
                setMenu(false);
              }}
            >
              Изменить
            </button>
            <button
              onClick={() => {
                onDelete(message.id);
                setMenu(false);
              }}
            >
              Удалить
            </button>
            <button
              onClick={() => {
                onReport(message.id);
                setMenu(false);
              }}
            >
              Пожаловаться
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function ConversationView({ conversation, currentUser, onBack, onChanged }) {
  const [messages, setMessages] = useState([]);
  const [cursor, setCursor] = useState(null);
  const [body, setBody] = useState("");
  const [state, setState] = useState("loading");
  const [busy, setBusy] = useState(false);
  const [socketState, setSocketState] = useState("connecting");
  const [typing, setTyping] = useState(false);
  const [notice, setNotice] = useState("");
  const [actionMenu, setActionMenu] = useState(false);
  const endRef = useRef(null);
  const socketRef = useRef(null);
  const typingTimer = useRef(null);
  const other = participantOf(conversation);
  useEffect(() => {
    let cancelled = false;
    setMessages([]);
    setCursor(null);
    setState("loading");
    api
      .conversationMessages(conversation.id, { limit: 30 })
      .then((page) => {
        if (cancelled) return;
        setMessages(page.items || []);
        setCursor(page.next_cursor);
        setState("ready");
        const last = page.items?.at(-1);
        if (last)
          api.markConversationRead(conversation.id, last.id).catch(() => {});
      })
      .catch((error) =>
        setState(errorStatus(error) === 404 ? "soon" : "error"),
      );
    const socket = createMessagesSocket({
      onState: setSocketState,
      onEvent: (event) => {
        if (event.conversation_id !== conversation.id) return;
        if (event.type === "typing") {
          setTyping(Boolean(event.is_typing));
          setNotice(event.is_typing ? "Собеседник печатает…" : "");
          if (event.is_typing) {
            clearTimeout(typingTimer.current);
            typingTimer.current = setTimeout(() => {
              setTyping(false);
              setNotice("");
            }, 2000);
          }
          return;
        }
        if (event.type === "message.read") {
          setMessages((items) =>
            items.map((item) =>
              item.id === event.message_id
                ? { ...item, read_by_recipient: true }
                : item,
            ),
          );
          return;
        }
        if (event.type === "message.deleted") {
          setMessages((items) =>
            items.map((item) =>
              item.id === event.message_id
                ? { ...item, is_deleted: true, body: "" }
                : item,
            ),
          );
          return;
        }
        if (!event.message) return;
        setMessages((items) => mergeUniqueMessages(items, event.message));
        onChanged?.(event);
      },
    });
    socketRef.current = socket;
    return () => {
      cancelled = true;
      clearTimeout(typingTimer.current);
      socketRef.current = null;
      socket.close();
    };
  }, [conversation.id]);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);
  useEffect(() => {
    if (socketState !== "connected" || state === "loading") return;
    api
      .conversationMessages(conversation.id, { limit: 30 })
      .then((page) =>
        setMessages((items) =>
          [...(page.items || []), ...items].filter(
            (item, index, all) =>
              all.findIndex((candidate) => candidate.id === item.id) === index,
          ),
        ),
      )
      .catch(() => {});
  }, [socketState, state, conversation.id]);
  const send = async (event) => {
    event.preventDefault();
    const value = body.trim();
    if (!value || busy) return;
    socketRef.current?.send({
      type: "typing",
      conversation_id: conversation.id,
      is_typing: false,
    });
    setBusy(true);
    try {
      const message = await api.sendMessage(conversation.id, { body: value });
      setMessages((items) => mergeUniqueMessages(items, message));
      setBody("");
    } catch (error) {
      setNotice(
        errorStatus(error) === 403
          ? "Отправка сообщений запрещена"
          : errorStatus(error) === 429
            ? "Слишком много сообщений. Попробуйте позже."
            : "Не удалось отправить сообщение",
      );
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    socketRef.current?.send({
      type: "typing",
      conversation_id: conversation.id,
      is_typing: Boolean(body.trim()),
    });
    clearTimeout(typingTimer.current);
    if (body.trim())
      typingTimer.current = setTimeout(
        () =>
          socketRef.current?.send({
            type: "typing",
            conversation_id: conversation.id,
            is_typing: false,
          }),
        900,
      );
  }, [body, conversation.id]);
  const loadOlder = async () => {
    if (!cursor || busy) return;
    setBusy(true);
    try {
      const page = await api.conversationMessages(conversation.id, {
        cursor,
        limit: 30,
      });
      setMessages((items) => [...(page.items || []), ...items]);
      setCursor(page.next_cursor);
    } finally {
      setBusy(false);
    }
  };
  const edit = async (id, value) => {
    try {
      const updated = await api.updateMessage(id, { body: value });
      setMessages((items) =>
        items.map((item) => (item.id === id ? updated : item)),
      );
    } catch (error) {
      setNotice(
        errorStatus(error) === 403
          ? "Нельзя изменить это сообщение"
          : "Не удалось изменить сообщение",
      );
    }
  };
  const remove = async (id) => {
    if (!window.confirm("Удалить сообщение?")) return;
    try {
      const updated = await api.deleteMessage(id);
      setMessages((items) =>
        items.map((item) =>
          item.id === id
            ? updated || { ...item, is_deleted: true, body: "" }
            : item,
        ),
      );
    } catch {
      setNotice("Не удалось удалить сообщение");
    }
  };
  const report = async (id) => {
    try {
      await api.reportMessage(
        id,
        window.prompt("Причина жалобы", "Нарушение правил") ||
          "Нарушение правил",
      );
      setNotice("Жалоба отправлена");
    } catch {
      setNotice("Не удалось отправить жалобу");
    }
  };
  const toggleMute = async () => {
    try {
      await api.muteConversation(conversation.id, !conversation.muted);
      conversation.muted = !conversation.muted;
      setNotice(
        conversation.muted ? "Диалог заглушён" : "Звук диалога включён",
      );
    } catch {
      setNotice("Действие пока недоступно");
    }
    setActionMenu(false);
  };
  const toggleBlock = async () => {
    try {
      if (conversation.blocked) await api.unblockUser(other.id);
      else await api.blockUser(other.id);
      conversation.blocked = !conversation.blocked;
      setNotice(
        conversation.blocked
          ? "Пользователь заблокирован"
          : "Пользователь разблокирован",
      );
    } catch {
      setNotice("Действие пока недоступно");
    }
    setActionMenu(false);
  };
  const addMember = async () => {
    const username = window.prompt("Username нового участника");
    if (!username) return;
    try {
      const person = await api.user(username.replace(/^@/, "").trim());
      await api.addGroupMember(conversation.id, person.id);
      setNotice("Участник добавлен");
    } catch {
      setNotice("Не удалось добавить участника");
    }
    setActionMenu(false);
  };
  return (
    <section className="conversation-view">
      <header>
        <button
          className="messages-back"
          onClick={onBack}
          aria-label="Назад к диалогам"
        >
          <ArrowLeft size={18} />
        </button>
        <Avatar user={other} />
        <div>
          <b>{conversationLabel(conversation)}</b>
          <small>
            {typing
              ? "печатает…"
              : conversation.kind === "group"
              ? `${(conversation.participants || []).length + 1} участника`
              : `@${other.username || ""}`}
          </small>
        </div>
        <span className="socket-state">
          {socketState === "connected" ? (
            <Wifi size={14} />
          ) : (
            <WifiOff size={14} />
          )}
          {socketState === "connected"
            ? "В сети"
            : socketState === "offline"
              ? "Офлайн"
              : "Переподключение…"}
        </span>
        <div className="conversation-actions">
          <button
            onClick={() => setActionMenu((value) => !value)}
            aria-label="Действия диалога"
          >
            <MoreHorizontal size={19} />
          </button>
          {actionMenu && (
            <div className="message-menu">
              <button onClick={toggleMute}>
                {conversation.muted ? "Включить звук" : "Заглушить"}
              </button>
              {conversation.kind === "group" ? (
                <button onClick={addMember}>Добавить участника</button>
              ) : (
                <button onClick={toggleBlock}>
                  {conversation.blocked ? "Разблокировать" : "Заблокировать"}
                </button>
              )}
            </div>
          )}
        </div>
      </header>
      {notice && (
        <div className="messages-notice" role="status">
          {notice}
          <button
            onClick={() => setNotice("")}
            aria-label="Закрыть уведомление"
          >
            <X size={14} />
          </button>
        </div>
      )}
      {state === "soon" ? (
        <SoonState />
      ) : state === "error" ? (
        <div className="messages-state">Не удалось загрузить сообщения</div>
      ) : state === "loading" ? (
        <div className="messages-state">
          <LoaderCircle className="spin" size={19} /> Загружаем…
        </div>
      ) : (
        <>
          <div className="message-history">
            {cursor && (
              <button className="load-older" onClick={loadOlder}>
                Загрузить предыдущие
              </button>
            )}
            {messages.map((message) => (
              <MessageBubble
                key={message.id || message.client_id}
                message={message}
                own={message.sender?.id === currentUser?.id}
                onEdit={edit}
                onDelete={remove}
                onReport={report}
              />
            ))}
            {!messages.length && (
              <div className="messages-empty">Начните разговор</div>
            )}
            <span ref={endRef} />
          </div>
          <form className="message-composer" onSubmit={send}>
            <textarea
              value={body}
              onChange={(event) => setBody(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form.requestSubmit();
                }
              }}
              maxLength={4000}
              placeholder="Напишите сообщение…"
              aria-label="Сообщение"
            />
            <button
              className="primary"
              disabled={busy || !body.trim()}
              aria-label="Отправить сообщение"
            >
              <Send size={17} />
            </button>
          </form>
        </>
      )}
    </section>
  );
}

export function MessagesPage() {
  const { user } = useSession();
  const { navigate } = useRouter();
  const [conversations, setConversations] = useState([]);
  const [selected, setSelected] = useState(null);
  const [cursor, setCursor] = useState(null);
  const [query, setQuery] = useState("");
  const [state, setState] = useState("loading");
  const [searchError, setSearchError] = useState("");
  const [searching, setSearching] = useState(false);
  const filtered = useMemo(
    () =>
      conversations.filter((item) => {
        const other = participantOf(item);
        return (
          !query.trim() ||
          `${other.username} ${other.display_name}`
            .toLowerCase()
            .includes(query.trim().toLowerCase())
        );
      }),
    [conversations, query],
  );
  useEffect(() => {
    if (!user) return;
    api
      .conversations({ limit: 30 })
      .then((page) => {
        setConversations(page.items || []);
        setCursor(page.next_cursor);
        setState("ready");
      })
      .catch((error) =>
        setState(errorStatus(error) === 404 ? "soon" : "error"),
      );
  }, [user]);
  if (!user)
    return (
      <AppShell title="Сообщения">
        <div className="card-state">
          <b>Войдите, чтобы открыть сообщения</b>
          <button className="outline-button" onClick={() => navigate("/login")}>
            Войти
          </button>
        </div>
      </AppShell>
    );
  if (state === "soon")
    return (
      <AppShell title="Сообщения">
        <SoonState />
      </AppShell>
    );
  const findUser = async (event) => {
    event.preventDefault();
    const username = query.trim().replace(/^@/, "");
    if (!username) return;
    setSearching(true);
    setSearchError("");
    try {
      const person = await api.user(username);
      const existing = conversations.find(
        (item) =>
          item.kind !== "group" &&
          participantOf(item).username === person.username,
      );
      if (existing) setSelected(existing);
      else {
        const conversation = await api.createConversation(person.id);
        setConversations((items) => [conversation, ...items]);
        setSelected(conversation);
      }
    } catch (error) {
      setSearchError(
        errorStatus(error) === 404
          ? "Пользователь не найден"
          : "Не удалось открыть диалог",
      );
    } finally {
      setSearching(false);
    }
  };
  const createGroup = async () => {
    const title = window.prompt("Название группы");
    const usernames = window.prompt("Username участников через запятую");
    if (!title || !usernames) return;
    setSearching(true);
    try {
      const people = await Promise.all(
        usernames
          .split(",")
          .map((name) => api.user(name.trim().replace(/^@/, ""))),
      );
      const conversation = await api.createGroup({
        title,
        member_ids: people.map((person) => person.id),
      });
      setConversations((items) => [conversation, ...items]);
      setSelected(conversation);
    } catch {
      setSearchError("Не удалось создать группу");
    } finally {
      setSearching(false);
    }
  };
  const enablePush = async () => {
    try {
      const enabled = await enablePushNotifications();
      setSearchError(enabled ? "Push-уведомления включены" : "Push-уведомления недоступны или запрещены");
    } catch {
      setSearchError("Не удалось включить push-уведомления");
    }
  };
  return (
    <AppShell title="Сообщения">
      <section className={`messages-page ${selected ? "has-selected" : ""}`}>
        <aside className="conversation-list">
          <header>
            <div>
              <h1>Сообщения</h1>
              <small>Личные разговоры</small>
            </div>
            <div>
              <button onClick={enablePush} aria-label="Включить push-уведомления">🔔</button>
              <button onClick={createGroup} aria-label="Создать группу">
                <MessageCircle size={22} />
              </button>
            </div>
          </header>
          <form className="conversation-search" onSubmit={findUser}>
            <Search size={17} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Найти пользователя или @username"
              aria-label="Найти пользователя"
            />
            <button
              type="submit"
              disabled={searching}
              aria-label="Открыть диалог"
            >
              <Search size={15} />
            </button>
          </form>
          {searchError && (
            <small className="messages-error">{searchError}</small>
          )}
          {state === "error" ? (
            <div className="messages-state">Не удалось загрузить диалоги</div>
          ) : (
            <div className="conversation-items">
              {filtered.map((item) => {
                const other = participantOf(item);
                return (
                  <button
                    key={item.id}
                    className={`conversation-item ${selected?.id === item.id ? "selected" : ""}`}
                    onClick={() => setSelected(item)}
                  >
                    <Avatar user={other} />
                    <span>
                      <b>{conversationLabel(item)}</b>
                      <small>
                        {item.last_message?.body ||
                          item.last_message ||
                          "Новый разговор"}
                      </small>
                    </span>
                    <time>
                      {item.last_message_at
                        ? new Date(item.last_message_at).toLocaleDateString(
                            "ru-RU",
                            { day: "2-digit", month: "2-digit" },
                          )
                        : ""}
                    </time>
                    {item.unread_count > 0 && (
                      <strong>{item.unread_count}</strong>
                    )}
                  </button>
                );
              })}
              {!filtered.length && (
                <div className="messages-empty">Диалогов пока нет</div>
              )}
              {cursor && (
                <button
                  className="load-older"
                  onClick={() =>
                    api.conversations({ cursor }).then((page) => {
                      setConversations((items) => [
                        ...items,
                        ...(page.items || []),
                      ]);
                      setCursor(page.next_cursor);
                    })
                  }
                >
                  Показать ещё
                </button>
              )}
            </div>
          )}
        </aside>
        {selected ? (
          <ConversationView
            conversation={selected}
            currentUser={user}
            onBack={() => setSelected(null)}
            onChanged={(event) =>
              setConversations((items) =>
                items.map((item) =>
                  item.id === selected.id
                    ? {
                        ...item,
                        last_message: event.message,
                        last_message_at: event.message.created_at,
                      }
                    : item,
                ),
              )
            }
          />
        ) : (
          <div className="messages-placeholder">
            <MessageCircle size={34} />
            <b>Выберите диалог</b>
            <span>Или найдите пользователя, чтобы начать разговор.</span>
          </div>
        )}
      </section>
    </AppShell>
  );
}
