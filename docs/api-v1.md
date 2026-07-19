# REST API v1

## Contract conventions

- Base path: `/api/v1`.
- JSON request and response bodies use `snake_case`.
- Timestamps are UTC ISO 8601 strings.
- Resource identifiers are UUID strings.
- Authenticated browser requests use Secure HttpOnly cookies and a CSRF header
  for state-changing methods.
- Successful collection responses use `{ "items": [...], "next_cursor": null }`.
- Detailed request and response fields are defined in
  [`api-schemas.md`](api-schemas.md).
- Errors use the stable envelope defined in [`error-format.md`](error-format.md).

## Authentication and users

| Method | Path | Auth | Purpose | Success |
| --- | --- | --- | --- | --- |
| `POST` | `/auth/register` | Public | Create an account | `201` |
| `POST` | `/auth/login` | Public | Create access and refresh cookies | `200` |
| `POST` | `/auth/refresh` | Refresh cookie | Rotate refresh session and issue access cookie | `200` |
| `POST` | `/auth/logout` | Access cookie | Revoke session and clear cookies | `204` |
| `GET` | `/users/me` | Access cookie | Return the current user | `200` |
| `PATCH` | `/users/me` | Access cookie | Update the current profile | `200` |
| `GET` | `/users/{username}` | Public | Return a public profile | `200` |

The authenticated principal comes from the access cookie. A client cannot
choose the owner of a resource by sending a username or user ID.

## Posts and feed

| Method | Path | Auth | Purpose | Success |
| --- | --- | --- | --- | --- |
| `GET` | `/posts` | Public | Feed and filtered search results | `200` |
| `POST` | `/posts` | Access cookie | Create a post | `201` |
| `GET` | `/posts/{post_id}` | Public | Return one post | `200` |
| `PATCH` | `/posts/{post_id}` | Owner | Update a post | `200` |
| `DELETE` | `/posts/{post_id}` | Owner | Soft-delete a post | `204` |

`GET /posts` accepts these filters:

- `query`: full-text search input;
- `search_in`: `all`, `title`, or `content`;
- `tag`: normalized tag filter;
- `category`: category filter;
- `author`: public username filter;
- `sort`: `newest` or `oldest`;
- `cursor`: opaque pagination cursor;
- `limit`: bounded page size.

Posts are returned newest-first by default. Every ordering is deterministic by
using `(created_at, id)` as the tie-breaker.

## Media

| Method | Path | Auth | Purpose | Success |
| --- | --- | --- | --- | --- |
| `POST` | `/media` | Access cookie | Validate and upload an image/video | `201` |
| `GET` | `/media/{media_id}` | Public/owner policy | Read media content | `200` |
| `DELETE` | `/media/{media_id}` | Owner | Delete an unattached media object | `204` |

`GET /media/{media_id}` returns binary content. Unattached uploads are visible
only to their owner; attached post media and selected avatars are public. It
does not return `MediaRead` metadata; upload responses and embedded
post/profile media use that schema.

Post creation and update accept previously uploaded `media_ids`. The media
service verifies ownership and attachment limits before the post transaction
commits.

## Comments

| Method | Path | Auth | Purpose | Success |
| --- | --- | --- | --- | --- |
| `GET` | `/posts/{post_id}/comments` | Public | List comments for a post or parent | `200` |
| `POST` | `/posts/{post_id}/comments` | Access cookie | Create a root comment or reply | `201` |
| `GET` | `/comments/{comment_id}` | Public | Return one comment | `200` |
| `PATCH` | `/comments/{comment_id}` | Owner | Edit a comment | `200` |
| `DELETE` | `/comments/{comment_id}` | Owner | Soft-delete a comment | `204` |

`GET /posts/{post_id}/comments` accepts `parent_id`, `cursor`, and `limit`.
Passing no `parent_id` returns root comments; passing a parent ID returns only
its direct replies. This supports unlimited nesting without returning the
whole tree in one response.

## Likes and sharing

| Method | Path | Auth | Purpose | Success |
| --- | --- | --- | --- | --- |
| `PUT` | `/posts/{post_id}/like` | Access cookie | Add the current user's like | `200` |
| `DELETE` | `/posts/{post_id}/like` | Access cookie | Remove the current user's like | `204` |
| `POST` | `/posts/{post_id}/shares` | Optional access cookie | Record a copy/native share event | `201` |

Like creation is idempotent because the database has one row per user/post
pair. Sharing records an event and returns the canonical URL plus the current
share count.

## Reports and moderation

| Method | Path | Auth | Purpose | Success |
| --- | --- | --- | --- | --- |
| `POST` | `/reports` | Access cookie | Report exactly one post or comment | `201` |
| `GET` | `/admin/reports` | Admin | List the moderation queue | `200` |
| `PATCH` | `/admin/reports/{report_id}` | Admin | Resolve or reject a report | `200` |

Reports are separate resources. Content ownership remains with the posts or
comments module; moderation invokes explicit service methods rather than
writing another module's tables directly.

`GET /admin/reports` accepts `status=open|resolved|rejected`, `cursor`, and
`limit`. A report can be transitioned from `open` to `resolved` or `rejected`.

## Status and compatibility policy

- `201` is used for newly created resources.
- `200` is used for successful reads and updates that return a body.
- `204` is used when a successful operation has no response body.
- `401` means no valid authentication; `403` means authentication succeeded
  but the principal lacks permission.
- `404` does not reveal whether a soft-deleted or unauthorized resource exists.
- A visible post's comment collection may return tombstones for deleted
  comments so replies retain their place; direct access to a deleted comment
  returns `404`.
- `409` represents uniqueness or state conflicts.
- `413` represents an upload that exceeds its limit; `415` an unsupported type.
- `422` represents request validation failure.

This is a new versioned contract. The current legacy `/api/*` routes are not
kept as a compatibility layer during the clean MVP migration.
