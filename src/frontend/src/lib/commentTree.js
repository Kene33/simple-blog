export function mergeComments(current, incoming) {
  const comments = new Map(current.map((comment) => [comment.id, comment]));
  incoming.forEach((comment) => comments.set(comment.id, comment));
  return [...comments.values()];
}

export function groupComments(comments) {
  return comments.reduce((groups, comment) => {
    const replies = groups.get(comment.parent_id) || [];
    groups.set(comment.parent_id, [...replies, comment]);
    return groups;
  }, new Map());
}
