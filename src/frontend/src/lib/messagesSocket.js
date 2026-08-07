export function mergeUniqueMessages(items, incoming) {
  return items.some((item) => item.id === incoming.id || (incoming.client_id && item.client_id === incoming.client_id)) ? items : [...items, incoming];
}

export function createMessagesSocket({ onEvent, onState }) {
  let socket;
  let stopped = false;
  let retry = 0;
  let timer;
  const connect = () => {
    if (stopped || !navigator.onLine) { onState("offline"); return; }
    onState(retry ? "reconnecting" : "connecting");
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    socket = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/messages`);
    socket.onopen = () => { retry = 0; onState("connected"); };
    socket.onmessage = (event) => { try { onEvent(JSON.parse(event.data)); } catch { } };
    socket.onerror = () => socket.close();
    socket.onclose = () => { if (stopped) return; onState(navigator.onLine ? "reconnecting" : "offline"); retry += 1; timer = setTimeout(connect, Math.min(30000, 1000 * 2 ** Math.min(retry, 5))); };
  };
  const online = () => { retry = 0; connect(); };
  const offline = () => { onState("offline"); socket?.close(); };
  window.addEventListener("online", online); window.addEventListener("offline", offline); connect();
  return { close() { stopped = true; clearTimeout(timer); window.removeEventListener("online", online); window.removeEventListener("offline", offline); socket?.close(); } };
}
