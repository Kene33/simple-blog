export function mergeUniqueMessages(items, incoming) {
  const index = items.findIndex((item) => item.id === incoming.id || (incoming.client_id && item.client_id === incoming.client_id));
  if (index < 0) return [...items, incoming];
  return items.map((item, itemIndex) => itemIndex === index ? { ...item, ...incoming } : item);
}

export function normalizeMessageEvent(event) {
  if (!event || typeof event !== "object") return null;
  const data = event.data && typeof event.data === "object" ? event.data : event;
  if (event.type === "message.created" || event.type === "message.updated") {
    const message = event.message || data.message || data;
    return { ...event, conversation_id: event.conversation_id || message.conversation_id, message };
  }
  return { ...event, conversation_id: event.conversation_id || data.conversation_id, message_id: event.message_id || data.message_id, reader_id: event.reader_id || data.reader_id, user_id: event.user_id || data.user_id, is_typing: event.is_typing ?? data.is_typing };
}

export function createMessagesSocket({ onEvent, onState }) {
  let socket;
  let stopped = false;
  let retry = 0;
  let timer;
  let heartbeat;
  const connect = () => {
    if (stopped || !navigator.onLine) { onState("offline"); return; }
    onState(retry ? "reconnecting" : "connecting");
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    socket = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/messages`);
    socket.onopen = () => { retry = 0; onState("connected"); heartbeat = setInterval(() => { if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "ping" })); }, 25000); };
    socket.onmessage = (event) => { try { const normalized = normalizeMessageEvent(JSON.parse(event.data)); if (normalized) onEvent(normalized); } catch { } };
    socket.onerror = () => socket.close();
    socket.onclose = () => { clearInterval(heartbeat); if (stopped) return; onState(navigator.onLine ? "reconnecting" : "offline"); retry += 1; timer = setTimeout(connect, Math.min(30000, 1000 * 2 ** Math.min(retry, 5))); };
  };
  const online = () => { retry = 0; connect(); };
  const offline = () => { onState("offline"); socket?.close(); };
  window.addEventListener("online", online); window.addEventListener("offline", offline); connect();
  return { send(event) { if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(event)); }, close() { stopped = true; clearTimeout(timer); clearInterval(heartbeat); window.removeEventListener("online", online); window.removeEventListener("offline", offline); socket?.close(); } };
}
