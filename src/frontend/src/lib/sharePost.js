import { api } from "./api";

export async function sharePost(post) {
  const url = `${window.location.origin}/posts/${post.id}`;
  const channel = navigator.share ? "native" : "copy";
  if (channel === "native") await navigator.share({ title: post.title, text: post.content, url });
  else await navigator.clipboard.writeText(url);
  if (!document.cookie.split("; ").some((item) => item.startsWith("csrf_token="))) return { share_count: post.share_count };
  return api.share(post.id, channel);
}
