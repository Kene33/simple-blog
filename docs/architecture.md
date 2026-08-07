# Simple Blog backend architecture

## Target system

Simple Blog uses a modular monolith. One FastAPI service owns the HTTP API and
frontend delivery, PostgreSQL owns relational state, and S3-compatible storage
owns uploaded media.

```mermaid
flowchart LR
    Browser["HTML/CSS/JavaScript"] --> Proxy["Reverse proxy"]
    Proxy --> App["FastAPI application"]
    App --> Auth["Auth and users"]
    App --> Content["Posts and comments"]
    App --> Social["Likes and sharing"]
    App --> Moderation["Reports"]
    App --> Messaging["Direct messaging"]
    App --> DB[("PostgreSQL")]
    App --> Redis[("Redis rate limit + Pub/Sub")]
    App --> Objects["S3 / MinIO"]
```

The service runs as one deployable unit while its domain modules keep data
ownership and dependency direction explicit. The design leaves room to extract
media processing or search later if runtime evidence justifies that cost.

## Request flow

```mermaid
sequenceDiagram
    participant C as Browser
    participant R as API router
    participant S as Domain service
    participant D as PostgreSQL
    participant O as Object storage

    C->>R: HTTP request with cookies and CSRF header
    R->>S: Validated DTO and authenticated principal
    S->>D: Transactional repository operation
    S->>O: Media operation when required
    S-->>R: Typed response DTO
    R-->>C: JSON response and request ID
```

Routers handle transport concerns. Services handle use cases, authorization,
and transaction boundaries. Repositories handle persistence. The full layering
and ownership policy lives in [`backend-module-boundaries.md`](backend-module-boundaries.md).

## Main data flows

### Authentication

1. The client sends registration or login credentials over HTTPS.
2. The auth service hashes or verifies the password with Argon2id.
3. The service creates a short-lived access JWT and a rotated refresh session.
4. The server sets both tokens in Secure HttpOnly cookies.
5. Other modules receive the authenticated principal from the auth dependency;
   they do not accept ownership IDs from request bodies.

### Post creation

1. The client uploads media and receives media metadata and IDs.
2. The post service validates title, content, tags, and media ownership.
3. One database transaction creates the post and its tag/media relations.
4. The response returns a transport DTO with author, media, and counters.

### Feed and search

1. The router validates filters and an opaque cursor.
2. The post service applies the filter fingerprint and deterministic ordering.
3. PostgreSQL returns a bounded page using `(created_at, id)` keyset pagination.
4. The response includes `items` and `next_cursor`.

### Comments and interactions

Comments use `parent_id` for unlimited nesting and load one level at a time.
Likes use a unique user/post pair. Sharing records an event with an optional
user ID so anonymous link copies can be counted without creating an account.

### Direct messaging

Direct messages are one-to-one text conversations. PostgreSQL is the source of
truth for conversations, membership, messages, read markers, blocks, and
tombstones. The REST API commits a message before publishing a lifecycle event.
Authenticated WSS connections deliver events only to the intended member after
Origin and cookie checks; membership is checked again for every subscription
and delivery target. Redis provides rate-limit state and Pub/Sub between app
instances, while each instance keeps only its local socket registry in memory.
If realtime delivery is temporarily unavailable, clients resync from the
cursor-paginated messages endpoint.

## Components

| Component | Responsibility | State |
| --- | --- | --- |
| FastAPI app | HTTP transport, auth dependencies, OpenAPI | Stateless between requests |
| Auth/users modules | Credentials, sessions, profiles, roles | PostgreSQL |
| Posts module | Posts, tags, feed, search projection | PostgreSQL |
| Comments module | Comment tree and soft deletion | PostgreSQL |
| Media module | Validation, object keys, attachment lifecycle | PostgreSQL + S3 |
| Interactions module | Likes, shares, counters | PostgreSQL |
| Moderation module | Reports and admin queue | PostgreSQL |
| Messaging module | Direct conversations, membership, messages, read state | PostgreSQL + Redis Pub/Sub |
| Frontend | Browser state, rendering, user interactions | Browser cookies/storage |

## Cross-cutting behavior

- Every response receives an `X-Request-ID` and structured log context.
- Errors use one stable envelope with machine-readable codes.
- State-changing browser requests require CSRF validation.
- Resource ownership comes from the authenticated principal.
- Lists use cursor pagination; clients do not calculate offsets.
- Soft-deleted posts and comments preserve referential integrity.
- Media limits and MIME validation run before object storage writes finish.

See the focused contracts:

- [Backend module boundaries](backend-module-boundaries.md)
- [PostgreSQL data model](database-schema.md)
- [REST API v1](api-v1.md)
- [API schemas](api-schemas.md)
- [Error format](error-format.md)
- [Cursor pagination](pagination.md)

## Deployment shape

Development uses Docker Compose with FastAPI, PostgreSQL, MinIO, and Redis.
Production can replace MinIO with an S3-compatible provider and place a reverse
proxy in front of FastAPI. Redis is required for production rate-limit state
and multi-instance messaging delivery; a single-process local run may use the
in-memory fallback. A queue and separate search service remain deferred.

The service must expose liveness and readiness checks. Alembic migrations run as
an explicit deployment step before the application accepts traffic.

## Decisions and tradeoffs

| Decision | Reason | Deferred alternative |
| --- | --- | --- |
| Modular monolith | Keeps deployment and local development simple | Split services after measured pressure |
| PostgreSQL | Gives constraints, transactions, and full-text search | Managed PostgreSQL provider |
| S3-compatible media | Separates large files from relational state | CDN and direct browser uploads |
| HttpOnly cookie tokens | Fits the browser client and avoids localStorage tokens | Server sessions or bearer tokens |
| Cursor pagination | Stable feed traversal without offset drift | Offset pagination for admin-only reports |
| Versioned REST API | Lets frontend and backend evolve against a named contract | Additional API versions later |

## Current repository boundary

The `src` package is the application runtime. It uses PostgreSQL through
SQLAlchemy and Alembic; the old SQLite implementation has been removed and is
not read or updated.
