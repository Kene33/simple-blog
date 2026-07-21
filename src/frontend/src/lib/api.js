const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

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
    if (refresh.ok) return request(path, options, false);
  }
  return parse(response);
}

export const api = {
  me: () => request("/users/me"),
  login: (data) => request("/auth/login", { method: "POST", body: JSON.stringify(data) }),
  register: (data) => request("/auth/register", { method: "POST", body: JSON.stringify(data) }),
  logout: () => request("/auth/logout", { method: "POST" }),
  posts: (params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== "" && value != null));
    return request(`/posts${query.size ? `?${query}` : ""}`);
  },
  post: (id) => request(`/posts/${id}`),
  like: (id) => request(`/posts/${id}/like`, { method: "PUT" }),
  unlike: (id) => request(`/posts/${id}/like`, { method: "DELETE" }),
  bookmark: (id) => request(`/posts/${id}/bookmark`, { method: "PUT" }),
  unbookmark: (id) => request(`/posts/${id}/bookmark`, { method: "DELETE" }),
  share: (id, channel) => request(`/posts/${id}/shares`, { method: "POST", body: JSON.stringify({ channel }) }),
  createPost: (data) => request("/posts", { method: "POST", body: JSON.stringify(data) }),
  createDraft: (data) => request("/drafts", { method: "POST", body: JSON.stringify(data) }),
  uploadMedia: (file, purpose = "post") => {
    const body = new FormData(); body.append("file", file); body.append("purpose", purpose);
    return request("/media", { method: "POST", body });
  },
  user: (username) => request(`/users/${username}`),
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
  bookmarks: (params = {}) => { const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value != null)); return request(`/bookmarks${query.size ? `?${query}` : ""}`); },
  drafts: () => request("/drafts"),
  deleteDraft: (id) => request(`/drafts/${id}`, { method: "DELETE" }),
  publishDraft: (id) => request(`/drafts/${id}/publish`, { method: "POST" })
};
