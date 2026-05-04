# OnlineChat — Product Requirements Document

**Version:** 1.0  
**Date:** 2026-05-04  
**Status:** In Progress  

---

## 1. Overview

OnlineChat is a real-time, end-to-end encrypted messaging backend built with Django, Django Channels, and Django REST Framework. It provides the server-side infrastructure for mobile or web chat applications, exposing a REST API for CRUD operations and WebSocket connections for real-time events.

### 1.1 Goals

- Deliver a secure, scalable backend for private and group chat
- Support end-to-end encryption so the server never sees plaintext messages
- Enable real-time message delivery, presence, and typing indicators via WebSocket
- Provide a clean, well-documented API for frontend and mobile client integration

### 1.2 Out of Scope (v1)

- Frontend application (this repo is backend only)
- Push notifications to mobile OS (APNs / FCM)
- Voice or video calling
- Message reactions, threading, or replies
- Message editing or deletion
- Read receipts per message
- Production-grade deployment config (load balancing, Redis channel layer, CDN)

---

## 2. Users & Roles

| Role | Description |
|------|-------------|
| **Anonymous** | Can register and obtain a JWT token |
| **Authenticated User** | Can create chats, send messages, manage their own profile |
| **Group Member** | Can send messages inside a group they belong to |
| **Group Admin** | Can add members and create topics in a supergroup |
| **Group Owner** | All admin privileges; original group creator |

---

## 3. Functional Requirements

### 3.1 Authentication

| ID | Requirement |
|----|-------------|
| AUTH-01 | Users register with username, email, and password |
| AUTH-02 | Login returns a JWT access token and a refresh token |
| AUTH-03 | Access token is passed as `Authorization: Bearer <token>` for REST calls |
| AUTH-04 | WebSocket connections authenticate via `?token=<access_token>` query parameter |
| AUTH-05 | Invalid or missing token closes a WebSocket connection with code `4401` |

### 3.2 User Profiles

| ID | Requirement |
|----|-------------|
| USR-01 | Each user has exactly one profile (avatar, description, status, public key) |
| USR-02 | Users can update their own avatar (multipart/form-data), description, and status |
| USR-03 | Users can upload and retrieve their RSA/EC public key for E2E encryption |
| USR-04 | Any authenticated user can view another user's profile and public key |
| USR-05 | Users can search for other users by username |

### 3.3 Direct Chat (1:1)

| ID | Requirement |
|----|-------------|
| DM-01 | Creating a chat between two users is idempotent — re-calling returns the existing chat |
| DM-02 | Only the two participants can send or receive messages in a chat |
| DM-03 | Messages are stored as ciphertext + IV; the server never stores plaintext |
| DM-04 | Messages can have zero or more file attachments |
| DM-05 | Attachment type (image, video, audio, file) is auto-detected from MIME type on upload |
| DM-06 | Message history is returned in chronological order |
| DM-07 | Sending a message via WebSocket broadcasts it to both participants in real time |
| DM-08 | A notification is created for the recipient on every new message |

### 3.4 Group Chat

| ID | Requirement |
|----|-------------|
| GRP-01 | Users can create a group with a name, optional description, and optional avatar |
| GRP-02 | Groups support three member roles: `member`, `admin`, `owner` |
| GRP-03 | Only `admin` or `owner` can add new members |
| GRP-04 | Non-members cannot send or read messages; WebSocket connect returns `4403` |
| GRP-05 | Sending a group message broadcasts it to all connected members via WebSocket |
| GRP-06 | A notification is created for every group member (except the sender) on each message |
| GRP-07 | Group messages are stored as ciphertext + IV |

### 3.5 Supergroups & Topics

| ID | Requirement |
|----|-------------|
| SG-01 | A group can be flagged `is_supergroup = true` at creation time |
| SG-02 | Only supergroups support topics |
| SG-03 | Only `admin` or `owner` can create topics inside a supergroup |
| SG-04 | Messages in a supergroup must be associated with a topic |
| SG-05 | The group WebSocket stream supports optional `topic_id` filtering |
| SG-06 | A dedicated WebSocket endpoint exists per topic for topic-scoped streams |

### 3.6 End-to-End Encryption

| ID | Requirement |
|----|-------------|
| E2E-01 | Clients are responsible for encrypting/decrypting message content |
| E2E-02 | The server stores only `ciphertext` and `iv` fields; never plaintext |
| E2E-03 | Each user stores one asymmetric public key on their profile |
| E2E-04 | Groups use a shared AES-256 symmetric key |
| E2E-05 | The group AES key is encrypted individually for each member using their public key |
| E2E-06 | Encrypted group keys are stored in `GroupEncryptedKey` (one row per group-member pair) |
| E2E-07 | A member can retrieve their own encrypted group key via REST; they decrypt it client-side |
| E2E-08 | Only one encrypted key record can exist per (group, member) pair |

### 3.7 Presence & Typing Indicators

| ID | Requirement |
|----|-------------|
| PRS-01 | Connecting to `/ws/presence/` marks the user as online and broadcasts to all connected users |
| PRS-02 | Disconnecting marks the user as offline — but only when the last active connection closes (multi-tab support) |
| PRS-03 | Clients send `{"type": "ping"}` to keep the presence connection alive |
| PRS-04 | Clients send a typing event scoped to a `chat_id`, `group_id`, or `topic_id` |
| PRS-05 | Typing events are broadcast to other participants in that chat/group/topic |

### 3.8 Notifications

| ID | Requirement |
|----|-------------|
| NTF-01 | Notifications have two types: `message` and `system` |
| NTF-02 | Notifications are persisted in the database with `is_read` state |
| NTF-03 | Clients can list their notifications via REST (GET) |
| NTF-04 | Clients can mark a specific notification as read via REST (POST) |
| NTF-05 | New notifications are pushed in real time to `/ws/notifications/` |

---

## 4. Non-Functional Requirements

### 4.1 Security

- All REST endpoints (except registration and token issuance) require a valid JWT
- WebSocket connections are validated before `connect()` completes
- No plaintext message content is stored or logged server-side
- CORS is restricted to configured origins (currently `localhost:3000`)
- File uploads are validated and stored outside the web root

### 4.2 Performance (Targets for v1)

- WebSocket message round-trip latency: < 100 ms on local network
- REST API response time (p95): < 200 ms for list/create operations
- Concurrent WebSocket connections per server: > 1,000 (subject to channel layer backend)

### 4.3 Reliability

- ASGI server: Daphne, managed by a process supervisor in production
- Channel layer: InMemoryChannelLayer in development; must be replaced with Redis in production for horizontal scaling
- Database: SQLite in development; must be replaced with PostgreSQL in production

### 4.4 Scalability Considerations

- Stateless JWT auth allows horizontal scaling of HTTP workers
- WebSocket state (presence counters) is currently in-process; migrating to Redis channel layer removes this bottleneck
- Media files should be served from object storage (S3-compatible) in production

---

## 5. Data Model Summary

```
User (Django built-in)
└── UserProfile          (1:1) public key, avatar, description, status

Chat                     (1:1 between two users, unique constraint)
└── Message              (many) ciphertext, iv
    └── MessageAttachment (many) file, attachment_type

Group                    name, description, avatar, is_supergroup
├── GroupMember          (many) user, role (member/admin/owner)
├── GroupTopic           (many, supergroup only) title
├── GroupMessage         (many) ciphertext, iv, topic (nullable)
└── GroupEncryptedKey    (many) encrypted AES key per member

Notification             recipient, actor, type, content, is_read
```

---

## 6. API Surface

### 6.1 REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/token/` | Obtain JWT token pair |
| POST | `/api/token/refresh/` | Refresh access token |
| POST | `/api/users/register/` | Register new user |
| GET | `/api/users/me/` | Current user info |
| GET | `/api/users/list/` | List all users |
| GET | `/api/users/search/?q=` | Search users |
| GET/PUT | `/api/users/me/profile/` | Get / update own profile |
| GET | `/api/users/<id>/profile/` | Get another user's profile |
| GET/PUT | `/api/users/me/public-key/` | Get / set own public key |
| GET | `/api/users/<id>/public-key/` | Get another user's public key |
| GET/POST | `/api/chats/` | List chats / create (idempotent) |
| GET/POST | `/api/chats/<id>/messages/` | List / send direct messages |
| POST | `/api/chats/messages/<id>/attachments/` | Add attachment to message |
| GET/POST | `/api/chats/groups/` | List groups / create group |
| GET | `/api/chats/groups/<id>/` | Group details |
| GET/POST | `/api/chats/groups/<id>/members/` | List / add members |
| GET/POST | `/api/chats/groups/<id>/topics/` | List / create topics |
| GET/POST | `/api/chats/groups/<id>/messages/` | List / send group messages |
| GET/POST | `/api/chats/groups/<id>/e2e-key/` | Get / distribute group encryption key |
| GET | `/api/chats/notifications/` | List notifications |
| POST | `/api/chats/notifications/<id>/read/` | Mark notification as read |
| GET | `/api/schema/` | OpenAPI 3.0 schema |
| GET | `/api/docs/` | Swagger UI |

### 6.2 WebSocket Endpoints

| Path | Consumer | Description |
|------|----------|-------------|
| `/ws/presence/` | `PresenceConsumer` | Global presence + typing indicators |
| `/ws/chats/<chat_id>/` | `ChatConsumer` | Direct chat message stream |
| `/ws/groups/<group_id>/` | `GroupConsumer` | Group message stream |
| `/ws/groups/<group_id>/topics/<topic_id>/` | `GroupTopicConsumer` | Topic-scoped message stream |
| `/ws/notifications/` | `NotificationConsumer` | Real-time notification push |

---

## 7. WebSocket Event Reference

### 7.1 Presence (`/ws/presence/`)

**Client → Server**

| Type | Payload | Effect |
|------|---------|--------|
| `ping` | _(none)_ | Keepalive; no response |
| `typing` | `{"chat_id": N}` | Broadcast typing to direct chat |
| `typing` | `{"group_id": N}` | Broadcast typing to group |
| `typing` | `{"topic_id": N}` | Broadcast typing to topic |

**Server → Client (broadcast)**

| Type | Payload | Trigger |
|------|---------|---------|
| `presence` | `{"user_id": N, "online": true}` | User connected |
| `presence` | `{"user_id": N, "online": false}` | User last tab disconnected |
| `typing` | `{"user_id": N, "chat_id": N}` | User typing in direct chat |
| `typing` | `{"user_id": N, "group_id": N}` | User typing in group |
| `typing` | `{"user_id": N, "topic_id": N}` | User typing in topic |

### 7.2 Direct Chat (`/ws/chats/<chat_id>/`)

**Client → Server:** `{"ciphertext": "...", "iv": "..."}`

**Server → Client:**
```json
{
  "id": 101,
  "chat_id": 7,
  "sender_user_id": 2,
  "receiver_user_id": 5,
  "ciphertext": "...",
  "iv": "...",
  "created_at": "2026-04-22T12:34:56.123456+00:00"
}
```

### 7.3 Group Chat (`/ws/groups/<group_id>/`)

**Client → Server:** `{"ciphertext": "...", "iv": "...", "topic_id": N}`

**Server → Client:**
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

### 7.4 Notifications (`/ws/notifications/`)

**Server → Client (push only):**
```json
{
  "type": "notification",
  "id": 42,
  "message": "You received a new message.",
  "notification_type": "message",
  "is_read": false,
  "created_at": "2026-04-24T10:09:00+00:00"
}
```

---

## 8. Feature Status

| Feature | Status | Notes |
|---------|--------|-------|
| User registration & JWT auth | Done | |
| User profiles & public keys | Done | |
| Direct (1:1) chat | Done | |
| Message attachments | Done | Auto-type detection |
| Group chat | Done | Roles: member / admin / owner |
| Supergroups with topics | Done | |
| End-to-end encryption support | Done | Client encrypts; server stores ciphertext |
| Presence (online/offline) | Done | Multi-tab aware |
| Typing indicators | Done | Per chat / group / topic |
| Real-time notifications | Done | WebSocket push + REST history |
| OpenAPI / Swagger docs | Done | `/api/docs/` |
| Redis channel layer | Not done | Required for production scaling |
| PostgreSQL database | Not done | Required for production |
| Production deployment config | Not done | |
| Push notifications (APNs/FCM) | Not done | Out of scope for v1 |
| Message read receipts | Not done | Planned for v2 |
| Message editing / deletion | Not done | Planned for v2 |
| Voice / video calling | Not done | Out of scope |

---

## 9. Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.x |
| Web Framework | Django 6.0.4 |
| REST API | Django REST Framework |
| Real-time | Django Channels + Daphne (ASGI) |
| Authentication | JWT via `djangorestframework-simplejwt` |
| Channel Layer | InMemoryChannelLayer (dev) → Redis (prod) |
| Database | SQLite (dev) → PostgreSQL (prod) |
| Media Storage | Local filesystem (dev) → Object storage (prod) |
| CORS | `django-cors-headers` |

---

## 10. Future Considerations (v2)

- **Message read receipts** — per-message delivery and read status
- **Message editing and deletion** — with edit history
- **File upload to object storage** — S3-compatible backend for attachments
- **Push notifications** — APNs and FCM integration for mobile clients
- **Message search** — full-text search over encrypted metadata (sender, date, group)
- **Rate limiting** — per-user and per-IP throttling on message send
- **Admin dashboard** — group moderation and user management UI
- **Audit logging** — compliance log of access patterns (not message content)
