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
| `POST` | `/auth/password-reset/request` | Public | Send a one-time reset link by email | `200` |
| `POST` | `/auth/password-reset/confirm` | Public | Set a new password and revoke sessions | `204` |
| `GET` | `/users/me` | Access cookie | Return the current user | `200` |
| `PATCH` | `/users/me` | Access cookie | Update the current profile | `200` |
| `GET` | `/users/{username}` | Public | Return a public profile | `200` |
| `GET` | `/users/{username}/comments` | Public | List the user's visible comments | `200` |

The authenticated principal comes from the access cookie. A client cannot
choose the owner of a resource by sending a username or user ID.

`profile_visibility=private` makes the public profile return `404`.
`posts_visibility=private` hides the user's posts from public feeds, search,
and profile counts; the owner still has access. `comments_visibility=private`
hides the user's comments from the public profile comments endpoint. Email is
never returned by a public profile.

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

## Categories

| Method | Path | Auth | Purpose | Success |
| --- | --- | --- | --- | --- |
| `GET` | `/categories` | Public | List approved categories | `200` |
| `POST` | `/category-requests` | Access cookie | Propose a category | `201` |
| `GET` | `/me/category-requests` | Access cookie | List own category requests | `200` |
| `GET` | `/admin/category-requests` | Staff | List requests by status | `200` |
| `PATCH` | `/admin/category-requests/{request_id}` | Staff + CSRF | Approve or reject a request | `200` |

Post and draft writes accept one category selection: `category_id` for an
approved category or `category_request_id` for a pending proposal. A post with
a pending proposal has `status=pending_category` and is not public. Approval
publishes it; rejection moves it to `needs_category_change` in the author's
drafts.

## Drafts

| Method | Path | Auth | Purpose | Success |
| --- | --- | --- | --- | --- |
| `POST` | `/drafts` | Access cookie | Create a private draft | `201` |
| `GET` | `/drafts` | Access cookie | List the current user's drafts | `200` |
| `GET` | `/drafts/{draft_id}` | Owner | Read one draft | `200` |
| `PATCH` | `/drafts/{draft_id}` | Owner | Update a draft | `200` |
| `POST` | `/drafts/{draft_id}/publish` | Owner | Publish a valid draft | `200` |
| `DELETE` | `/drafts/{draft_id}` | Owner | Delete a draft | `204` |

Drafts are private and never appear in `GET /posts`. Publishing requires a
non-empty title, content, and category.

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

Public attached media uses a short, configurable cache lifetime
(`MEDIA_PUBLIC_CACHE_SECONDS`, default 300 seconds) with stale-while-revalidate.
It is intentionally not immutable because moderation or deletion must become
effective without waiting a year for a shared cache to expire.

`purpose=cover` is an image upload used by a profile cover. Post creation and update accept previously uploaded `media_ids`. The media
service verifies ownership and attachment limits before the post transaction
commits.

## Comments

| Method | Path | Auth | Purpose | Success |
| --- | --- | --- | --- | --- |
| `GET` | `/posts/{post_id}/comments` | Public/owner | List comments for a post or parent | `200` |
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

## Bookmarks

| Method | Path | Auth | Purpose | Success |
| --- | --- | --- | --- | --- |
| `PUT` | `/posts/{post_id}/bookmark` | Access cookie | Add a bookmark | `200` |
| `DELETE` | `/posts/{post_id}/bookmark` | Access cookie | Remove a bookmark | `204` |
| `GET` | `/bookmarks` | Access cookie | List the user's bookmarked posts | `200` |

`PostRead` includes `bookmarked_by_me`. Bookmark listing uses the standard
`items` and `next_cursor` response.

## Reports and moderation

| Method | Path | Auth | Purpose | Success |
| --- | --- | --- | --- | --- |
| `POST` | `/reports` | Access cookie | Report exactly one post or comment | `201` |
| `GET` | `/admin/reports` | Staff | List the moderation queue | `200` |
| `GET` | `/admin/reports/count` | Staff | Count open reports for a navigation badge | `200` |
| `GET` | `/admin/reports/{report_id}` | Staff | Read a report with a target snapshot | `200` |
| `PATCH` | `/admin/reports/{report_id}` | Staff + CSRF | Resolve or reject a report | `200` |
| `GET` | `/admin/users` | Staff | Find users by username or email | `200` |
| `PATCH` | `/admin/users/{user_id}/moderation` | Staff + CSRF | Ban, unban, mute, or unmute a user | `200` |
| `PATCH` | `/admin/users/{user_id}/role` | Admin + CSRF | Set `user` or `moderator` role | `200` |
| `DELETE` | `/admin/users/{user_id}` | Admin + CSRF | Anonymize an account while retaining authored content | `204` |
| `PATCH` | `/admin/posts/{post_id}/hide` | Admin + CSRF | Hide a post | `204` |
| `PATCH` | `/admin/posts/{post_id}/restore` | Admin + CSRF | Restore a hidden post | `204` |
| `PATCH` | `/admin/comments/{comment_id}/hide` | Admin + CSRF | Hide a comment | `204` |
| `PATCH` | `/admin/comments/{comment_id}/restore` | Admin + CSRF | Restore a hidden comment | `204` |
| `GET` | `/admin/moderation-actions` | Admin | List moderation audit actions | `200` |

Reports are separate resources. Content ownership remains with the posts or
comments module; moderation invokes explicit service methods rather than
writing another module's tables directly.

Staff means `admin` or `moderator`. A moderator can approve categories, process
reports, and ban ordinary users with a reason. Only admins can assign roles,
mute users, unban users, restore content, and read moderation audit logs.

`GET /admin/users` accepts `banned=true|false`, `muted=true|false`, and `limit`.
`GET /admin/reports` accepts `status=open|resolved|rejected`, `cursor`, and
`limit`. A report can be transitioned from `open` to `resolved` or `rejected`;
`hide_target` and `ban_author` may be sent with a resolved report.

Post, comment, and profile authors include `status=active|banned|deleted`,
`is_banned`, and `is_deleted`. Banned authors and their published posts remain
public. Deleted authors are shown as `Deleted user` without avatar or profile;
moderation reasons are never included in public author data.

## Messaging

| Method | Path | Auth | Purpose | Success |
| --- | --- | --- | --- | --- |
| `POST` | `/conversations/direct/{user_id}` | Access cookie + CSRF | Create or return a direct conversation | `201`/`200` |
| `POST` | `/conversations/groups` | Access cookie + CSRF | Create a group conversation | `201` |
| `GET` | `/conversations` | Access cookie | List the current user's conversations | `200` |
| `POST` | `/messaging/devices` | Access cookie + CSRF | Register a browser device public key | `201` |
| `GET` | `/messaging/devices` | Access cookie | List current user's active devices | `200` |
| `DELETE` | `/messaging/devices/{device_id}` | Access cookie + CSRF | Revoke own device | `204` |
| `GET` | `/conversations/{conversation_id}/devices` | Member | List active public keys for conversation members | `200` |
| `GET` | `/conversations/{conversation_id}/messages` | Member | List messages by cursor | `200` |
| `GET` | `/conversations/{conversation_id}/messages/search?q=...` | Member | Deprecated plaintext search; client-side search is required | `409` |
| `POST` | `/conversations/{conversation_id}/messages` | Member + CSRF | Send an encrypted message envelope | `201` |
| `POST` | `/conversations/{conversation_id}/members` | Group admin + CSRF | Add a group member | `204` |
| `DELETE` | `/conversations/{conversation_id}/members/{user_id}` | Group admin/member + CSRF | Remove a member or leave | `204` |
| `POST` | `/conversations/{conversation_id}/mute` | Member + CSRF | Mute or unmute a conversation | `200` |
| `PATCH` | `/conversations/{conversation_id}/read` | Member + CSRF | Mark a conversation as read | `204` |
| `PATCH` | `/messages/{message_id}` | Sender + CSRF | Edit a message | `200` |
| `DELETE` | `/messages/{message_id}` | Sender + CSRF | Soft-delete a message | `204` |
| `POST` | `/users/{user_id}/block` | Access cookie + CSRF | Block a user from messaging | `204` |
| `DELETE` | `/users/{user_id}/block` | Access cookie + CSRF | Remove a messaging block | `204` |
| `POST` | `/push/subscriptions` | Access cookie + CSRF | Register a browser push subscription | `204` |
| `DELETE` | `/push/subscriptions` | Access cookie + CSRF | Remove a browser push subscription | `204` |

The WebSocket endpoint is `/api/v1/ws/messages`. It authenticates with the access
cookie, checks `Origin`, and emits only events for conversations the current
user may access. PostgreSQL remains the source of truth; clients resync from
the REST cursor after reconnecting.

Messages contain only encrypted envelopes. The API never receives or searches
plaintext content. Message attachments use `media` uploads with `purpose=message`; media URLs are
private and readable only by conversation members. Typing events are ephemeral
WebSocket events and are never stored in PostgreSQL. Group conversations use
`kind=group`, `title`, and `participants` in `ConversationRead`.

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
