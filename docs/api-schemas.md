# API request and response schemas

These wire schemas are transport contracts. Database rows and internal ORM
models must not be exposed directly from the API.

## Common values

- `UUID`: lowercase canonical UUID string.
- `Timestamp`: UTC ISO 8601 string, for example `2026-07-19T12:30:00Z`.
- `Cursor`: opaque URL-safe string. Clients must not parse or construct it.
- `Page<T>`: `{ "items": T[], "next_cursor": Cursor | null }`.

## User schemas

### `RegisterRequest`

```json
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "a-strong-password"
}
```

- `username`: required string, 3–30 characters, normalized for uniqueness.
- `email`: required valid email, normalized for uniqueness.
- `password`: required string, minimum 10 characters; never returned.

### `LoginRequest`

```json
{
  "identifier": "alice@example.com",
  "password": "a-strong-password"
}
```

`identifier` accepts either the normalized username or email.

### `UserSummary`

```json
{
  "id": "uuid",
  "username": "alice",
  "avatar_url": null
}
```

### `UserProfile`

```json
{
  "id": "uuid",
  "username": "alice",
  "email": "alice@example.com",
  "avatar_url": null,
  "role": "user",
  "posts_count": 0,
  "created_at": "2026-07-19T12:30:00Z",
  "updated_at": "2026-07-19T12:30:00Z"
}
```

The email and role fields are returned only by `GET /users/me`; public profile
responses omit them.

## Post schemas

### `PostCreateRequest`

```json
{
  "title": "First post",
  "content": "Post content",
  "category": "technology",
  "tags": ["python", "fastapi"],
  "media_ids": []
}
```

- `title`: required, 1–200 characters.
- `content`: required, 1–10,000 characters.
- `category`: required, 1–50 characters.
- `tags`: required array, at most 10 normalized tags, each 1–30 characters.
- `media_ids`: required array, at most 4 IDs and at most one video.
- `author_id`, `username`, timestamps and counters are server-owned and are not
  accepted in the request.

### `PostUpdateRequest`

All fields from `PostCreateRequest` are optional, but at least one field must be
provided. Ownership is checked from the authenticated principal.

### `PostRead`

```json
{
  "id": "uuid",
  "author": {
    "id": "uuid",
    "username": "alice",
    "avatar_url": null
  },
  "title": "First post",
  "content": "Post content",
  "category": "technology",
  "tags": ["python", "fastapi"],
  "media": [],
  "like_count": 0,
  "comment_count": 0,
  "share_count": 0,
  "liked_by_me": false,
  "created_at": "2026-07-19T12:30:00Z",
  "updated_at": "2026-07-19T12:30:00Z"
}
```

`liked_by_me` is computed from the authenticated user and is `false` for an
anonymous request. It is not persisted in the `posts` table.

## Media schemas

### Upload request

`POST /media` uses `multipart/form-data` with:

- `file`: required binary file;
- `purpose`: required enum `avatar|post`.

The server determines the media kind from the validated MIME type and does not
trust the original filename.

### `MediaRead`

```json
{
  "id": "uuid",
  "kind": "image",
  "mime_type": "image/jpeg",
  "size_bytes": 123456,
  "url": "/api/v1/media/uuid",
  "status": "uploaded",
  "created_at": "2026-07-19T12:30:00Z"
}
```

`status` is `uploaded`, `attached`, or `deleted`. Storage keys and internal
object-store credentials are never returned.

## Comment schemas

### `CommentCreateRequest`

```json
{
  "body": "Useful comment",
  "parent_id": null
}
```

- `body`: required, 1–2,000 characters.
- `parent_id`: nullable UUID. When set, it must reference a comment on the
  same post.

### `CommentRead`

```json
{
  "id": "uuid",
  "post_id": "uuid",
  "author": {
    "id": "uuid",
    "username": "alice",
    "avatar_url": null
  },
  "parent_id": null,
  "body": "Useful comment",
  "is_deleted": false,
  "created_at": "2026-07-19T12:30:00Z",
  "updated_at": "2026-07-19T12:30:00Z"
}
```

Deleted comments keep their ID and location in the tree but return a tombstone
body and `is_deleted: true` so replies remain addressable.

## Interaction schemas

### `LikeRead`

```json
{
  "post_id": "uuid",
  "like_count": 1,
  "liked_by_me": true
}
```

### `ShareCreateRequest`

```json
{
  "channel": "copy"
}
```

`channel` is one of `copy` or `native`.

### `ShareRead`

```json
{
  "post_id": "uuid",
  "canonical_url": "https://example.com/posts/uuid",
  "share_count": 1
}
```

## Moderation schemas

### `ReportCreateRequest`

```json
{
  "post_id": "uuid",
  "comment_id": null,
  "reason": "spam",
  "details": "Optional explanation"
}
```

Exactly one of `post_id` and `comment_id` is required. `reason` is a bounded
enum such as `spam`, `harassment`, `illegal`, or `other`; `details` is optional
and limited to 2,000 characters.

### `ReportRead`

```json
{
  "id": "uuid",
  "reporter": {
    "id": "uuid",
    "username": "alice",
    "avatar_url": null
  },
  "post_id": "uuid",
  "comment_id": null,
  "reason": "spam",
  "details": "Optional explanation",
  "status": "open",
  "resolution": null,
  "created_at": "2026-07-19T12:30:00Z",
  "resolved_at": null
}
```

## Compatibility rules

- New fields should be optional for existing response consumers unless the
  `/api/v2` contract is introduced.
- Removing or changing the meaning of a field requires a versioned contract
  decision.
- Sensitive fields are intentionally omitted rather than returned as null.
- Pydantic response models define the public shape; ORM serialization is not a
  public compatibility mechanism.
