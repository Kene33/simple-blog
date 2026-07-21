export function Avatar({ user }) {
  const initials = user?.username?.slice(0, 2).toUpperCase() || "?";
  return <span className="avatar">{user?.avatar_url ? <img src={user.avatar_url} alt="" /> : initials}</span>;
}
