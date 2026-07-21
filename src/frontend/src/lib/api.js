const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const ACCESS_TOKEN_KEY = "simple_access_token";

function accessToken() {
  return sessionStorage.getItem(ACCESS_TOKEN_KEY);
}

function saveAccessToken(payload) {
  if (payload?.access_token) sessionStorage.setItem(ACCESS_TOKEN_KEY, payload.access_token);
  return payload;
}

export function clearAccessToken() {
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
}

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

async function parse(response) {
  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await response.json() : null;

  if (!response.ok) {
    const message = payload?.message || payload?.detail || "Не удалось выполнить запрос";
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
  const token = accessToken();
  if (token && !headers.has("Authorization")) headers.set("Authorization", `Bearer ${token}`);

  return fetch(`/api/v1${path}`, {
    ...options,
    method,
    headers,
    credentials: "include"
  });
}

export async function request(path, options = {}, retry = true) {
  const response = await send(path, options);
  if (response.status === 401 && retry && path !== "/auth/refresh") {
    const refresh = await send("/auth/refresh", { method: "POST" });
    if (refresh.ok) {
      saveAccessToken(await parse(refresh));
      return request(path, options, false);
    }
  }
  return parse(response);
}

export const api = {
  me: () => request("/me"),
  login: async (data) => saveAccessToken(await request("/auth/login", { method: "POST", body: JSON.stringify(data) })),
  register: (data) => request("/auth/register", { method: "POST", body: JSON.stringify(data) }),
  verifyEmail: (token) => request("/auth/verify-email", { method: "POST", body: JSON.stringify({ token }) }),
  logout: async () => { try { await request("/auth/logout", { method: "POST" }); } finally { clearAccessToken(); } },
  posts: (params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== "" && value != null));
    return request(`/posts${query.size ? `?${query}` : ""}`);
  },
  post: (id) => request(`/posts/${id}`),
  createLink: (data) => request("/links", { method: "POST", body: JSON.stringify(data) }),
  myLinks: (params = {}) => { const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== "" && value != null)); return request(`/me/links${query.size ? `?${query}` : ""}`); },
  folders: () => request("/me/folders"),
  createFolder: (data) => request("/me/folders", { method: "POST", body: JSON.stringify(data) }),
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
    if (purpose === "avatar") {
      const body = new FormData(); body.append("file", file);
      return request("/me/avatar", { method: "POST", body });
    }
    const body = new FormData(); body.append("file", file); body.append("purpose", purpose);
    return request("/media", { method: "POST", body });
  },
  user: (username) => request(`/users/${username}`),
  updateMe: (data) => request("/me/profile", { method: "PATCH", body: JSON.stringify(data) }),
  userComments: (username, params = {}) => { const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value != null)); return request(`/users/${username}/comments${query.size ? `?${query}` : ""}`); },
  comments: (postId, params = {}) => { const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value != null)); return request(`/posts/${postId}/comments${query.size ? `?${query}` : ""}`); },
  createComment: (postId, data) => request(`/posts/${postId}/comments`, { method: "POST", body: JSON.stringify(data) }),
  updateComment: (id, data) => request(`/comments/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteComment: (id) => request(`/comments/${id}`, { method: "DELETE" }),
  report: (data) => request("/reports", { method: "POST", body: JSON.stringify(data) }),
  reportCount: async () => ({ open_count: (await api.reports({ status_filter: "open", limit: 1 })).total || 0 }),
  reports: (params = {}) => {
    const normalized = { ...params };
    if (normalized.status) { normalized.status_filter = normalized.status; delete normalized.status; }
    if (normalized.cursor) { normalized.offset = normalized.cursor; delete normalized.cursor; }
    const query = new URLSearchParams(Object.entries(normalized).filter(([, value]) => value != null));
    return request(`/admin/reports${query.size ? `?${query}` : ""}`);
  },
  reportDetail: (id) => request(`/admin/reports/${id}`),
  resolveReport: (id, data) => request(`/admin/reports/${id}`, { method: "PATCH", body: JSON.stringify({ password_confirmation: data.password_confirmation, status: data.status, comment: data.resolution || data.comment }) }),
  bookmarks: (params = {}) => { const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value != null)); return request(`/bookmarks${query.size ? `?${query}` : ""}`); },
  drafts: () => request("/drafts"),
  deleteDraft: (id) => request(`/drafts/${id}`, { method: "DELETE" }),
  publishDraft: (id) => request(`/drafts/${id}/publish`, { method: "POST" })
};
