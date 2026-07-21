import { api } from "./api";

export async function sharePost(post) {
  const url = `${window.location.origin}/posts/${post.id}`;
  const channel = navigator.share ? "native" : "copy";
  if (channel === "native") await navigator.share({ title: post.title, text: post.content, url });
  else await navigator.clipboard.writeText(url);
  return api.share(post.id, channel);
}
