# Cursor pagination

All potentially growing collections use cursor pagination. The API does not
expose offset/page-number pagination for feeds, search results, comments, or
moderation queues.

## Request

```text
GET /api/v1/posts?sort=newest&limit=20&cursor=eyJ2IjoxLCJjcmVhdGVkX2F0Ijoi...
```

- `limit` defaults to `20` and accepts values from `1` to `100`.
- `cursor` is optional on the first request.
- The cursor is opaque. Clients must store it and send it back unchanged.
- A cursor belongs to its endpoint, sort order, and filter set.

## Response

```json
{
  "items": [],
  "next_cursor": "eyJ2IjoxLCJjcmVhdGVkX2F0Ijoi..."
}
```

`next_cursor` is `null` when no more items are available.

## Ordering

Every paginated query has a deterministic two-column ordering:

```text
(created_at, id)
```

For `sort=newest`, the API returns descending order and loads the next page
with:

```sql
WHERE (created_at, id) < (:cursor_created_at, :cursor_id)
ORDER BY created_at DESC, id DESC
```

For `sort=oldest`, the comparison and ordering are ascending. The unique UUID
tie-breaker prevents duplicate or missing rows when timestamps match.

## Cursor contents

The server encodes a versioned payload containing:

- cursor version;
- endpoint/resource name;
- last `created_at` value;
- last resource `id`;
- sort direction;
- a hash of filter parameters.

The payload is base64url-encoded and authenticated with a server-side signing
key. The API may change its internal representation without changing the
client contract.

## Invalid cursors

The API returns `400 INVALID_CURSOR` when the cursor is malformed, expired,
signed with an old key, belongs to another endpoint, or does not match the
current filters and sort direction.

The client should discard the cursor and restart from the first page. It should
not attempt to repair or decode the value.

## Consistency behavior

- New rows inserted after the first request may appear only on a new feed
  request; they are not inserted into an already traversed cursor sequence.
- Soft-deleted rows are skipped from normal collections.
- A row deleted between two requests may reduce the number of returned items;
  the API does not fill pages with offset compensation.
- A row updated without changing `created_at` keeps its feed position.
- Filters and sort direction must remain unchanged while consuming a cursor.

## Resource-specific use

- Posts use `(created_at, id)` and support search, tag, category, author, and
  sort filters.
- Comments use `(created_at, id)` within one `post_id` and `parent_id`.
- Reports use `(created_at, id)` with a status filter for the admin queue.
- Media cleanup uses an internal time-window query and does not expose a public
  pagination contract.
