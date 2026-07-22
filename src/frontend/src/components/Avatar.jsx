export const isDeletedUser = (user) => user?.is_deleted || user?.status === "deleted" || user?.username === "Deleted user" || user?.email?.endsWith("@deleted.invalid") || !user?.username;
export const isBannedUser = (user) => user?.is_banned || user?.status === "banned" || Boolean(user?.disabled_at);

export function Avatar({ user }) {
  const deleted = isDeletedUser(user);
  const initials = user?.username?.slice(0, 2).toUpperCase() || "";
  const name = user?.display_name || user?.username || "Пользователь";
  return <span className={`avatar${deleted ? " avatar-deleted" : ""}`}>{!deleted && (user?.avatar_url ? <img src={user.avatar_url} alt={`Аватар пользователя ${name}`} loading="lazy" decoding="async" /> : initials)}</span>;
}
