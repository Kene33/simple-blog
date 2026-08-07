const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const configuredApiBase = import.meta.env.VITE_API_BASE_URL?.trim();
const API_BASE = (() => {
  if (!configuredApiBase) return "/api/v1";
  if (configuredApiBase.startsWith("/")) return configuredApiBase.replace(/\/$/, "");
  try {
    const url = new URL(configuredApiBase, window.location.origin);
    return import.meta.env.PROD && url.origin !== window.location.origin ? "/api/v1" : `${url.origin}${url.pathname}`.replace(/\/$/, "");
  } catch {
    return "/api/v1";
  }
})();
const SAME_ORIGIN_API = new URL(API_BASE, window.location.origin).origin === window.location.origin;
const mutationInFlight = new Map();

export class ApiError extends Error {
  constructor(message, status, payload = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function cookie(name) {
  return document.cookie
    .split("; ")
    .find((item) => item.startsWith(`${name}=`))
    ?.split("=")
    .slice(1)
    .join("=");
}

function readableValidationMessage(field) {
  if (field.code === "MISSING") return "обязательное поле";
  if (field.code === "STRING_TOO_SHORT") return `минимум ${field.message.match(/at least (\d+)/i)?.[1] || "несколько"} символа`;
  if (field.code === "STRING_TOO_LONG") return `максимум ${field.message.match(/at most (\d+)/i)?.[1] || "допустимое количество"} символов`;
  if (field.field === "email" && field.code === "VALUE_ERROR") return "укажите корректный email";
  return field.message;
}

async function parse(response) {
  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await response.json() : null;

  if (!response.ok) {
    const fields = payload?.error?.fields;
    const fieldLabels = { username: "Username", email: "Email", password: "Пароль", identifier: "Username или email" };
    const message = fields?.length
      ? `Проверьте: ${fields.map((field) => { const name = field.field.split(".").pop(); return `${fieldLabels[name] || name}: ${readableValidationMessage({ ...field, field: name })}`; }).join("; ")}`
      : payload?.error?.message || payload?.message || payload?.detail || "Не удалось выполнить запрос";
    throw new ApiError(message, response.status, payload);
  }

  return payload;
}

async function send(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers);
  const bodyIsForm = options.body instanceof FormData;

  if (options.body && !bodyIsForm && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (MUTATING_METHODS.has(method)) {
    const csrf = cookie("csrf_token");
    if (csrf) headers.set("X-CSRF-Token", decodeURIComponent(csrf));
  }

  return fetch(`${API_BASE}${path}`, {
    ...options,
    method,
    headers,
    credentials: "include"
  });
}

function requestId() {
  return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function bodyFingerprint(body) {
  if (!body) return "";
  if (typeof body === "string") return body;
  if (body instanceof FormData) return [...body.entries()].map(([key, value]) => `${key}:${value instanceof File ? `${value.name}:${value.size}:${value.lastModified}` : value}`).join("|");
  return String(body);
}

async function requestOnce(path, options, retry) {
  const response = await send(path, options);
  if (response.status === 401 && retry && path !== "/auth/refresh") {
    const refresh = await send("/auth/refresh", { method: "POST" });
    if (refresh.ok) return requestOnce(path, options, false);
    window.dispatchEvent(new Event("simple:auth-lost"));
  }
  return parse(response);
}

export function request(path, options = {}, retry = true) {
  const method = (options.method || "GET").toUpperCase();
  if (!MUTATING_METHODS.has(method)) return requestOnce(path, options, retry);
  const headers = new Headers(options.headers);
  const key = options.idempotencyKey || requestId();
  if (SAME_ORIGIN_API) headers.set("Idempotency-Key", key);
  const prepared = { ...options, headers };
  delete prepared.idempotencyKey;
  const fingerprint = `${method}:${path}:${bodyFingerprint(options.body)}`;
  const existing = mutationInFlight.get(fingerprint);
  if (existing) return existing;
  const pending = requestOnce(path, prepared, retry);
  mutationInFlight.set(fingerprint, pending);
  pending.then(() => mutationInFlight.delete(fingerprint), () => mutationInFlight.delete(fingerprint));
  return pending;
}

export const api = {
  me: () => request("/users/me"),
  login: (data) => request("/auth/login", { method: "POST", body: JSON.stringify(data) }),
  register: (data) => request("/auth/register", { method: "POST", body: JSON.stringify(data) }),
  resendEmailVerification: () => request("/auth/email-verification/resend", { method: "POST" }),
  verifyEmail: (token) => request(`/auth/verify-email/${encodeURIComponent(token)}`),
  requestPasswordReset: (data) => request("/auth/password-reset/request", { method: "POST", body: JSON.stringify(data) }),
  confirmPasswordReset: (data) => request("/auth/password-reset/confirm", { method: "POST", body: JSON.stringify(data) }),
  logout: () => request("/auth/logout", { method: "POST" }),
  posts: (params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== "" && value != null));
    return request(`/posts${query.size ? `?${query}` : ""}`);
  },
  trending: () => request("/posts/trending"),
  post: (id) => request(`/posts/${id}`),
  like: (id) => request(`/posts/${id}/like`, { method: "PUT" }),
  unlike: (id) => request(`/posts/${id}/like`, { method: "DELETE" }),
  bookmark: (id) => request(`/posts/${id}/bookmark`, { method: "PUT" }),
  unbookmark: (id) => request(`/posts/${id}/bookmark`, { method: "DELETE" }),
  share: (id, channel) => request(`/posts/${id}/shares`, { method: "POST", body: JSON.stringify({ channel }) }),
  createPost: (data) => request("/posts", { method: "POST", body: JSON.stringify(data) }),
  updatePost: (id, data) => request(`/posts/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deletePost: (id) => request(`/posts/${id}`, { method: "DELETE" }),
  createDraft: (data) => request("/drafts", { method: "POST", body: JSON.stringify(data) }),
  uploadMedia: (file, purpose = "post") => {
    const body = new FormData(); body.append("file", file); body.append("purpose", purpose);
    return request("/media", { method: "POST", body });
  },
  user: (username) => request(`/users/${username}`),
  activeAuthors: (limit = 3) => request(`/users/active-authors?limit=${limit}`),
  updateMe: (data) => request("/users/me", { method: "PATCH", body: JSON.stringify(data) }),
  userComments: (username, params = {}) => { const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value != null)); return request(`/users/${username}/comments${query.size ? `?${query}` : ""}`); },
  comments: (postId, params = {}) => { const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value != null)); return request(`/posts/${postId}/comments${query.size ? `?${query}` : ""}`); },
  createComment: (postId, data) => request(`/posts/${postId}/comments`, { method: "POST", body: JSON.stringify(data) }),
  updateComment: (id, data) => request(`/comments/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteComment: (id) => request(`/comments/${id}`, { method: "DELETE" }),
  report: (data) => request("/reports", { method: "POST", body: JSON.stringify(data) }),
  reportCount: () => request("/admin/reports/count"),
  reports: (params = {}) => { const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value != null)); return request(`/admin/reports${query.size ? `?${query}` : ""}`); },
  reportDetail: (id) => request(`/admin/reports/${id}`),
  resolveReport: (id, data) => request(`/admin/reports/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  adminUsers: (params = {}) => { const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value != null && value !== "")); return request(`/admin/users${query.size ? `?${query}` : ""}`); },
  moderateUser: (id, data) => request(`/admin/users/${id}/moderation`, { method: "PATCH", body: JSON.stringify(data) }),
  hidePost: (id, reason) => request(`/admin/posts/${id}/hide`, { method: "PATCH", body: JSON.stringify({ reason }) }),
  deleteUser: (id) => request(`/admin/users/${id}`, { method: "DELETE" }),
  setUserRole: (id, data) => request(`/admin/users/${id}/role`, { method: "PATCH", body: JSON.stringify(data) }),
  moderationActions: (params = {}) => { const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value != null && value !== "")); return request(`/admin/moderation-actions${query.size ? `?${query}` : ""}`); },
  adminCategoryRequests: (params = {}) => { const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value != null)); return request(`/admin/category-requests${query.size ? `?${query}` : ""}`); },
  resolveCategoryRequest: (id, data) => request(`/admin/category-requests/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  restorePost: (id, data) => request(`/admin/posts/${id}/restore`, { method: "PATCH", body: JSON.stringify(data) }),
  restoreComment: (id, data) => request(`/admin/comments/${id}/restore`, { method: "PATCH", body: JSON.stringify(data) }),
  bookmarks: (params = {}) => { const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value != null)); return request(`/bookmarks${query.size ? `?${query}` : ""}`); },
  drafts: () => request("/drafts"),
  categories: () => request("/categories"),
  requestCategory: (data) => request("/category-requests", { method: "POST", body: JSON.stringify(data) }),
  draft: (id) => request(`/drafts/${id}`),
  updateDraft: (id, data) => request(`/drafts/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteDraft: (id) => request(`/drafts/${id}`, { method: "DELETE" }),
  publishDraft: (id) => request(`/drafts/${id}/publish`, { method: "POST" })
  ,conversations: (params = {}) => { const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value != null && value !== "")); return request(`/conversations${query.size ? `?${query}` : ""}`); }
  ,messageDevices: () => request("/messaging/devices")
  ,registerMessageDevice: (data) => request("/messaging/devices", { method: "POST", body: JSON.stringify(data) })
  ,revokeMessageDevice: (id) => request(`/messaging/devices/${id}`, { method: "DELETE" })
  ,conversationDevices: (id) => request(`/conversations/${id}/devices`)
  ,createConversation: (userId) => request(`/conversations/direct/${userId}`, { method: "POST" })
  ,createGroup: (data) => request("/conversations/groups", { method: "POST", body: JSON.stringify(data) })
  ,conversationMessages: (id, params = {}) => { const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value != null && value !== "")); return request(`/conversations/${id}/messages${query.size ? `?${query}` : ""}`); }
  ,sendMessage: (id, data) => request(`/conversations/${id}/messages`, { method: "POST", body: JSON.stringify(data) })
  ,updateMessage: (id, data) => request(`/messages/${id}`, { method: "PATCH", body: JSON.stringify(data) })
  ,deleteMessage: (id) => request(`/messages/${id}`, { method: "DELETE" })
  ,markConversationRead: (id, messageId) => request(`/conversations/${id}/read`, { method: "PATCH", body: JSON.stringify({ message_id: messageId }) })
  ,muteConversation: (id, muted = true) => request(`/conversations/${id}/mute`, { method: "POST", body: JSON.stringify({ muted }) })
  ,blockUser: (id) => request(`/users/${id}/block`, { method: "POST" })
  ,unblockUser: (id) => request(`/users/${id}/block`, { method: "DELETE" })
  ,reportMessage: (id, reason) => request("/reports", { method: "POST", body: JSON.stringify({ message_id: id, reason }) })
  ,subscribePush: (data) => request("/push/subscriptions", { method: "POST", body: JSON.stringify(data) })
  ,unsubscribePush: (data) => request("/push/subscriptions", { method: "DELETE", body: JSON.stringify(data) })
};
