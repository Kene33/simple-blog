# Direct Messages Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add authenticated direct conversations with paginated history, realtime delivery, moderation controls, and mobile-safe UX.

**Architecture:** Keep REST calls in `src/frontend/src/lib/api.js`, WebSocket lifecycle in a small `src/frontend/src/lib/messagesSocket.js`, and screen state in `/messages` components. REST remains the source of truth; WebSocket events only update or invalidate the visible conversation and unread counts.

**Tech Stack:** React 19, Vite, JavaScript/JSX, vanilla CSS, `lucide-react`, `fetch`, HttpOnly cookies, CSRF header, native WebSocket.

## Global Constraints

- Guests can read only public UI and cannot send direct messages.
- Message text is rendered as React text; no `innerHTML` or `dangerouslySetInnerHTML`.
- Messages are not stored in `localStorage` and private content is not put in URLs.
- Every mutation uses the existing API layer and CSRF/idempotency behavior.
- Every task ends with a focused test, build check, and commit.

## Backend contract required before implementation

The current repository has no conversation/message REST routes or WebSocket endpoint. Backend must provide:

- `GET /api/v1/conversations?cursor=&limit=` → `{ items: [{ id, participant, last_message, last_message_at, unread_count }], next_cursor }`.
- `POST /api/v1/conversations` with `{ username }` → conversation summary; existing conversation is returned instead of duplicated.
- `GET /api/v1/conversations/{id}/messages?before=&limit=` → `{ items, next_cursor }`, oldest-to-newest or an explicit ordering contract.
- `POST /api/v1/conversations/{id}/messages` with `{ body, client_id }` → canonical message.
- `PATCH /api/v1/messages/{id}` and `DELETE /api/v1/messages/{id}` → canonical edited/deleted message.
- `POST /api/v1/conversations/{id}/read` and mute/block/report endpoints with explicit 401/403/404/429 errors.
- `WS /api/v1/ws/messages` authenticated by the existing HttpOnly session; event envelope must include stable `event_id`, `type`, `conversation_id`, and message/unread payloads.
- Replay endpoint or cursor contract for reconnect (`after`/`cursor`) so missed events can be fetched without duplicates.
- Server-side ban/mute/privacy enforcement and message length limits.

### Task 1: REST API surface

**Files:**
- Modify: `src/frontend/src/lib/api.js`
- Test: `src/frontend/src/lib/api.test.js` (or existing frontend test location)

- [ ] Add `conversations`, `createConversation`, `conversationMessages`, `sendMessage`, `updateMessage`, `deleteMessage`, `markConversationRead`, `muteConversation`, `blockUser`, `unblockUser`, and `reportMessage` methods.
- [ ] Add a failing test for URL/query/body construction, then implement and run it.
- [ ] Commit `feat(messages): add direct message REST methods`.

### Task 2: Router and shared states

**Files:**
- Modify: `src/frontend/src/App.jsx`
- Modify: `src/frontend/src/components/AppShell.jsx`
- Create: `src/frontend/src/pages/MessagesPage.jsx`
- Create: `src/frontend/src/styles/messages.css`

- [ ] Add `/messages` route and authenticated navigation entry.
- [ ] Add loading, empty, offline, 401, 403, 404, and 429 states.
- [ ] Add failing route/guest-render tests, implement, build, and commit.

### Task 3: Conversation list

**Files:**
- Modify: `src/frontend/src/pages/MessagesPage.jsx`
- Create: `src/frontend/src/components/ConversationList.jsx`

- [ ] Render avatar, username, last message, timestamp, unread count, cursor pagination, and user search.
- [ ] Create/open a conversation through the REST method; prevent duplicate conversations.
- [ ] Add keyboard navigation and focus management for search and list selection.
- [ ] Test guest restrictions, pagination, and empty state; commit.

### Task 4: Conversation window

**Files:**
- Create: `src/frontend/src/components/ConversationView.jsx`
- Create: `src/frontend/src/components/MessageBubble.jsx`

- [ ] Load history with cursor pagination upward.
- [ ] Add textarea input, Enter-to-send, Shift+Enter newline, optimistic pending state, and server reconciliation.
- [ ] Show sender/time, own-message styling, edit, delete confirmation, deleted tombstone, and read status.
- [ ] Render message bodies as text and enforce the server-provided max length client-side.
- [ ] Test edit/delete/tombstone and 403 behavior; commit.

### Task 5: WebSocket lifecycle

**Files:**
- Create: `src/frontend/src/lib/messagesSocket.js`
- Modify: `src/frontend/src/pages/MessagesPage.jsx`
- Modify: `src/frontend/src/components/ConversationView.jsx`

- [ ] Connect only after authentication; handle online/offline and reconnect state.
- [ ] Deduplicate by `event_id` and `message.id`; update active conversation and unread counts without reload.
- [ ] Replay missed messages from the backend cursor after reconnect.
- [ ] Test realtime delivery, reconnect, offline state, and duplicate suppression; commit.

### Task 6: User actions and responsive UX

**Files:**
- Modify: `src/frontend/src/components/ConversationView.jsx`
- Modify: `src/frontend/src/styles/messages.css`

- [ ] Add mute, block/unblock, report, ban/mute restrictions, and delete confirmation.
- [ ] Use a desktop side-by-side layout and a mobile push-style conversation view with a back button.
- [ ] Test block/mute UI and mobile layout; commit.

### Task 7: Browser smoke coverage

**Files:**
- Create: `tests/messages-smoke.md` or existing browser smoke test location.

- [ ] Verify two authenticated users: create conversation, send, receive realtime, edit, delete, mark read, reconnect, block/mute, and report.
- [ ] Verify guest cannot send and a 403 does not break the page.
- [ ] Run frontend build and the complete available test suite; commit.

## Scope review

The frontend checklist is fully mapped above. Implementation is blocked until the backend contract in this document exists; adding UI against guessed endpoints would create a false-positive frontend and break production integration.
