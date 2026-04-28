# OnlineChat Integration Guide (Mobile + Frontend)

This guide describes end-to-end integration with the current backend for:
- User registration and authentication
- Profile personalization
- Direct chat (1:1)
- Group chat and supergroups with topics
- Group end-to-end key exchange
- Attachments and notifications
- Realtime messaging via WebSocket

Base URL examples in this document use:
- HTTP: `http://127.0.0.1:8000`
- WS: `ws://127.0.0.1:8000`

---

## 1) Authentication and Session

### 1.1 Register
`POST /api/users/register/`

Request:
```json
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "StrongPass123"
}
```

### 1.2 Login (JWT)
`POST /api/token/`

Request:
```json
{
  "username": "alice",
  "password": "StrongPass123"
}
```

Response:
```json
{
  "refresh": "<refresh_token>",
  "access": "<access_token>"
}
```

### 1.3 Refresh token
`POST /api/token/refresh/`

Request:
```json
{
  "refresh": "<refresh_token>"
}
```

### 1.4 Use access token
For all protected REST endpoints:
- Header: `Authorization: Bearer <access_token>`

For WebSocket:
- Query param: `?token=<access_token>`
- Or `Authorization: Bearer <access_token>` in the handshake header

---

## 2) User and Profile Workflow

### 2.1 Get current user
`GET /api/users/me/`

### 2.2 List users (for starting chats)
`GET /api/users/list/`

### 2.3 Search users
`GET /api/users/search/?q=<query>`

Returns users whose usernames match the query, excluding the current user.

### 2.4 Update current profile personalization
`PUT /api/users/me/profile/` (multipart/form-data)

Fields:
- `avatar` (optional image file)
- `description` (optional string)
- `status` (optional string)

### 2.5 Get current profile
`GET /api/users/me/profile/`

### 2.6 Get another user profile
`GET /api/users/<user_id>/profile/`

### 2.7 Public key APIs (E2E support)
- `GET /api/users/me/public-key/`
- `PUT /api/users/me/public-key/`
- `GET /api/users/<user_id>/public-key/`

---

## 3) Direct Chat (1:1)

### 3.0 Response payload shape updates (current)
The direct chat REST endpoints now return nested user profile objects:
- `GET /api/chats/` and `POST /api/chats/` include `sender_user` and `receiver_user`.
- `GET /api/chats/<chat_id>/messages/` and `POST /api/chats/<chat_id>/messages/` include `sender_user`, `receiver_user`, and `attachments`.

Nested user profile object shape:
```json
{
  "public_key": "<base64_or_pem>",
  "username": "alice",
  "avatar_url": "http://127.0.0.1:8000/media/avatars/alice.jpg",
  "description": "Backend engineer",
  "status": "online",
  "created_at": "2026-04-24T10:00:00+00:00"
}
```

For REST profile endpoints, the backend returns `UserProfile` payloads with fields such as:
- `user_id`
- `public_key`
- `avatar`
- `avatar_url`
- `description`
- `status`
- `created_at`

For public-key endpoints, the payload is:
```json
{
  "user_id": 5,
  "public_key": "<base64_or_text_key>",
  "created_at": "2026-04-20T12:00:00+00:00"
}
```

### 3.1 Create or get existing direct chat
`POST /api/chats/`

Request:
```json
{
  "receiver_user_id": 5
}
```

### 3.2 List my direct chats
`GET /api/chats/`

Response item example:
```json
{
  "id": 7,
  "receiver_user_id": 5,
  "sender_user_id": 2,
  "created_at": "2026-04-24T10:05:00+00:00",
  "receiver_user": {
    "public_key": "<...>",
    "username": "alice",
    "avatar_url": "http://127.0.0.1:8000/media/avatars/alice.jpg",
    "description": "Backend engineer",
    "status": "online",
    "created_at": "2026-04-20T12:00:00+00:00"
  },
  "sender_user": {
    "public_key": "<...>",
    "username": "bob",
    "avatar_url": "http://127.0.0.1:8000/media/avatars/bob.jpg",
    "description": "Mobile dev",
    "status": "busy",
    "created_at": "2026-04-20T12:05:00+00:00"
  }
}
```

### 3.3 Send direct message (REST)
`POST /api/chats/<chat_id>/messages/`

Request:
```json
{
  "ciphertext": "<encrypted_text>",
  "iv": "<iv_max_32_chars>"
}
```

### 3.4 Get direct chat message history
`GET /api/chats/<chat_id>/messages/`

Response item example:
```json
{
  "id": 101,
  "chat_id": 7,
  "iv": "1234567890abcdef",
  "ciphertext": "ENC(...)",
  "receiver_user_id": 5,
  "sender_user_id": 2,
  "receiver_user": {
    "public_key": "<...>",
    "username": "alice",
    "avatar_url": "http://127.0.0.1:8000/media/avatars/alice.jpg",
    "description": "Backend engineer",
    "status": "online",
    "created_at": "2026-04-20T12:00:00+00:00"
  },
  "sender_user": {
    "public_key": "<...>",
    "username": "bob",
    "avatar_url": "http://127.0.0.1:8000/media/avatars/bob.jpg",
    "description": "Mobile dev",
    "status": "busy",
    "created_at": "2026-04-20T12:05:00+00:00"
  },
  "created_at": "2026-04-24T10:08:00+00:00",
  "attachments": [
    {
      "id": 3,
      "attachment_type": "image",
      "file": "/media/chat_attachments/photo.jpg",
      "file_url": "http://127.0.0.1:8000/media/chat_attachments/photo.jpg",
      "uploaded_by_id": 2,
      "created_at": "2026-04-24T10:09:00+00:00"
    }
  ]
}
```

### 3.5 Upload message attachment
`POST /api/chats/messages/<message_id>/attachments/` (multipart/form-data)

Field:
- `file` (required)

Attachment type is auto-detected as `image`, `video`, `audio`, or `file`.

---

## 4) Groups and Supergroups

## 4.1 Create group/supergroup
`POST /api/chats/groups/` (multipart/form-data)

Fields:
- `name` (required)
- `description` (optional)
- `is_supergroup` (optional bool, default false)
- `avatar` (optional image)

Creator becomes `owner` automatically.

### 4.2 List my groups
`GET /api/chats/groups/`

### 4.3 Get group details
`GET /api/chats/groups/<group_id>/`

### 4.4 List/Add members
- `GET /api/chats/groups/<group_id>/members/`
- `POST /api/chats/groups/<group_id>/members/`

Add-member request:
```json
{
  "user_id": 9
}
```

Only `owner`/`admin` can add members.

Member response item example:
```json
{
  "id": 25,
  "group_id": 15,
  "user_id": 9,
  "user": {
    "public_key": "<...>",
    "username": "charlie",
    "avatar_url": "/media/avatars/charlie.jpg",
    "description": "QA",
    "status": "offline",
    "created_at": "2026-04-22T09:00:00+00:00"
  },
  "role": "member",
  "joined_at": "2026-04-24T10:10:00+00:00"
}
```

### 4.5 Topics (supergroup only)
- `GET /api/chats/groups/<group_id>/topics/`
- `POST /api/chats/groups/<group_id>/topics/`

Create-topic request:
```json
{
  "title": "Backend"
}
```

### 4.6 Group messages via REST
- `GET /api/chats/groups/<group_id>/messages/`
- `GET /api/chats/groups/<group_id>/messages/?topic_id=<topic_id>`
- `POST /api/chats/groups/<group_id>/messages/`

Request body:
```json
{
  "ciphertext": "<encrypted_text>",
  "iv": "<iv_max_32_chars>",
  "topic_id": 11
}
```

Rules:
- For supergroups, `topic_id` is required.
- For regular groups, `topic_id` is optional (usually omitted).

Response item example:
```json
{
  "id": 301,
  "group_id": 15,
  "topic_id": 11,
  "sender_user_id": 2,
  "sender_user": {
    "public_key": "<...>",
    "username": "bob",
    "avatar_url": "/media/avatars/bob.jpg",
    "description": "Mobile dev",
    "status": "busy",
    "created_at": "2026-04-20T12:05:00+00:00"
  },
  "ciphertext": "ENC(...)",
  "iv": "1234567890abcdef",
  "created_at": "2026-04-24T10:12:00+00:00"
}
```

### 4.7 Group E2E key exchange
`GET /api/chats/groups/<group_id>/e2e-key/`

Returns the group AES key encrypted for the current user:
```json
{
  "ciphertext": "<encrypted_group_key>",
  "iv": "<iv>",
  "encrypted_by_id": 2
}
```

`POST /api/chats/groups/<group_id>/e2e-key/` (JSON)

Request:
```json
{
  "for_user_id": 9,
  "ciphertext": "<encrypted_group_key>",
  "iv": "<iv>"
}
```

Only group members can store key material for another member.

---

## 5) Realtime WebSocket Integration

### 5.0 Presence and notifications sockets

Presence endpoint:
`/ws/presence/?token=<access_token>`

Incoming frames:
```json
{ "type": "ping" }
```
```json
{ "type": "typing", "chat_id": 7 }
```
```json
{ "type": "typing", "group_id": 15 }
```
```json
{ "type": "typing", "topic_id": 11 }
```

Outgoing frames:
```json
{ "type": "presence", "user_id": 2, "online": true }
```
```json
{ "type": "typing", "user_id": 2, "chat_id": 7 }
```
```json
{ "type": "typing", "user_id": 2, "group_id": 15 }
```
```json
{ "type": "typing", "user_id": 2, "topic_id": 11 }
```

Notification endpoint:
`/ws/notifications/?token=<access_token>`

This socket only receives notification frames and does not expect client messages.

## 5.1 Direct chat socket
Endpoint:
`/ws/chats/<chat_id>/?token=<access_token>`

Send payload:
```json
{
  "ciphertext": "<encrypted_text>",
  "iv": "<iv_max_32_chars>"
}
```

Receive payload:
```json
{
  "id": 101,
  "chat_id": 7,
  "iv": "...",
  "ciphertext": "...",
  "receiver_user_id": 5,
  "sender_user_id": 2,
  "created_at": "2026-04-22T12:34:56.123456+00:00"
}
```

### 5.2 Group socket (group-level stream)
Endpoint:
`/ws/groups/<group_id>/?token=<access_token>`

Send payload (regular group):
```json
{
  "ciphertext": "<encrypted_text>",
  "iv": "<iv_max_32_chars>"
}
```

Send payload (supergroup):
```json
{
  "ciphertext": "<encrypted_text>",
  "iv": "<iv_max_32_chars>",
  "topic_id": 11
}
```

### 5.3 Topic socket (topic-only stream)
Endpoint:
`/ws/groups/<group_id>/topics/<topic_id>/?token=<access_token>`

Send payload:
```json
{
  "ciphertext": "<encrypted_text>",
  "iv": "<iv_max_32_chars>"
}
```

Receive payload (group/topic message):
```json
{
  "id": 301,
  "group_id": 15,
  "topic_id": 11,
  "sender_user_id": 2,
  "ciphertext": "...",
  "iv": "...",
  "created_at": "2026-04-22T12:35:00.654321+00:00"
}
```

### 5.4 WebSocket close/error semantics
- `4401`: unauthorized (missing/invalid token)
- `4403`: forbidden (not a member / no topic access)

---

## 6) Notifications Workflow

### 6.1 List notifications
`GET /api/chats/notifications/`

### 6.2 Mark notification as read
`POST /api/chats/notifications/<notification_id>/read/`

Use this from mobile/frontend after user opens chat/group/topic related to that notification.

---

## 7) Recommended Client Workflow

## 7.1 App startup
1. Load stored refresh/access token.
2. If missing or expired, login/refresh.
3. Fetch `GET /api/users/me/` and `GET /api/users/me/profile/`.
4. Fetch `GET /api/chats/notifications/`.
5. Open `/ws/presence/` and `/ws/notifications/` for realtime status and alert updates.

### 7.2 Direct chat screen
1. Open direct chat via `POST /api/chats/` (idempotent behavior for existing pair).
2. Fetch history `GET /api/chats/<chat_id>/messages/`.
3. Connect socket `/ws/chats/<chat_id>/?token=...`.
4. Send encrypted payload over WS; use REST fallback on socket reconnect issues.
5. Upload files after message creation via attachments endpoint.

### 7.3 Group list and details
1. Fetch `GET /api/chats/groups/`.
2. Open group detail `GET /api/chats/groups/<group_id>/`.
3. Load members/topics/messages as needed.

### 7.4 Supergroup topic chat
1. Fetch topics: `GET /api/chats/groups/<group_id>/topics/`.
2. Open topic stream using topic WS endpoint.
3. Optionally keep group socket connected for all-topic updates.

---

## 8) Mobile/Frontend Implementation Notes

- Always include JWT on REST and WS requests.
- Keep local message queue for offline/retry behavior.
- Use optimistic UI for sent messages, then reconcile with server message object.
- For media upload:
  - send encrypted text message first (or placeholder text)
  - upload file via attachment endpoint
  - append attachment to message UI when upload returns.
- Handle token refresh race safely (single refresh lock per app session).

---

## 9) Dev/Test Endpoints

- OpenAPI schema: `/api/schema/`
- Swagger UI: `/api/docs/`
- Chat demo page: `/demo/chat/`

---

## 10) Quick cURL examples

### Login
```bash
curl -X POST http://127.0.0.1:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"StrongPass123"}'
```

### Create group
```bash
curl -X POST http://127.0.0.1:8000/api/chats/groups/ \
  -H "Authorization: Bearer <access>" \
  -F "name=Engineering" \
  -F "description=Team discussions" \
  -F "is_supergroup=true"
```

### Create topic
```bash
curl -X POST http://127.0.0.1:8000/api/chats/groups/15/topics/ \
  -H "Authorization: Bearer <access>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Mobile"}'
```

### Send group message (REST)
```bash
curl -X POST http://127.0.0.1:8000/api/chats/groups/15/messages/ \
  -H "Authorization: Bearer <access>" \
  -H "Content-Type: application/json" \
  -d '{"ciphertext":"ENC(...)","iv":"1234567890abcdef","topic_id":11}'
```
