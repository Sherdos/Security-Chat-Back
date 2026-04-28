from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db.models import Q

from ..models import (
    Chat,
    Group,
    GroupMember,
    GroupMessage,
    GroupTopic,
    Message,
    Notification,
)

# user_id -> number of active PresenceConsumer connections
# Dict operations between awaits are safe in single-threaded asyncio.
_presence_connections: dict[int, int] = {}
_PRESENCE_GROUP = "presence"


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or user.is_anonymous:
            await self.close(code=4401)
            return

        self.chat_id = int(self.scope["url_route"]["kwargs"]["chat_id"])
        self.group_name = f"chat_{self.chat_id}"

        is_member = await self._is_chat_member(user.id, self.chat_id)
        if not is_member:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        ciphertext = content.get("ciphertext")
        iv = content.get("iv")

        if not ciphertext or not iv:
            await self.send_json({"detail": "ciphertext and iv are required."})
            return

        result = await self._create_message(
            chat_id=self.chat_id,
            sender_user_id=self.scope["user"].id,
            ciphertext=ciphertext,
            iv=iv,
        )
        if result is None:
            await self.send_json({"detail": "Unable to send message."})
            return

        notification_push = result.pop("_notification", None)

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.message",
                "payload": result,
            },
        )

        if notification_push:
            await self.channel_layer.group_send(
                f"user_{notification_push['recipient_id']}_notifications",
                {
                    "type": "send.notification",
                    "payload": {
                        "type": "notification",
                        "id": notification_push["id"],
                        "message": notification_push["content"],
                        "notification_type": notification_push["notification_type"],
                        "is_read": False,
                        "created_at": notification_push["created_at"],
                    },
                },
            )

    async def chat_message(self, event):
        await self.send_json(event["payload"])

    async def chat_typing(self, event):
        await self.send_json(event["payload"])

    @database_sync_to_async
    def _is_chat_member(self, user_id, chat_id):
        return (
            Chat.objects.filter(
                id=chat_id,
            )
            .filter(Q(sender_user_id=user_id) | Q(receiver_user_id=user_id))
            .exists()
        )

    @database_sync_to_async
    def _create_message(self, chat_id, sender_user_id, ciphertext, iv):
        chat = Chat.objects.filter(id=chat_id).first()
        if chat is None:
            return None

        if sender_user_id not in [chat.sender_user_id, chat.receiver_user_id]:
            return None

        receiver_user_id = (
            chat.receiver_user_id
            if sender_user_id == chat.sender_user_id
            else chat.sender_user_id
        )

        message = Message.objects.create(
            chat_id=chat.id,
            sender_user_id=sender_user_id,
            receiver_user_id=receiver_user_id,
            ciphertext=ciphertext,
            iv=iv,
        )
        notification = Notification.objects.create(
            recipient_user_id=receiver_user_id,
            actor_user_id=sender_user_id,
            notification_type=Notification.TYPE_MESSAGE,
            content="You received a new message.",
        )

        return {
            "id": message.id,
            "chat_id": message.chat_id,
            "iv": message.iv,
            "ciphertext": message.ciphertext,
            "receiver_user_id": message.receiver_user_id,
            "sender_user_id": message.sender_user_id,
            "created_at": message.created_at.isoformat(),
            "_notification": {
                "id": notification.id,
                "recipient_id": receiver_user_id,
                "content": notification.content,
                "notification_type": notification.notification_type,
                "created_at": notification.created_at.isoformat(),
            },
        }


class GroupConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or user.is_anonymous:
            await self.close(code=4401)
            return

        self.group_id = int(self.scope["url_route"]["kwargs"]["group_id"])
        self.group_channel_name = f"group_{self.group_id}"

        is_member = await self._is_group_member(user.id, self.group_id)
        if not is_member:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_channel_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_channel_name"):
            await self.channel_layer.group_discard(
                self.group_channel_name,
                self.channel_name,
            )

    async def receive_json(self, content, **kwargs):
        ciphertext = content.get("ciphertext")
        iv = content.get("iv")
        topic_id = content.get("topic_id")

        if not ciphertext or not iv:
            await self.send_json({"detail": "ciphertext and iv are required."})
            return

        if topic_id is not None:
            try:
                topic_id = int(topic_id)
            except (TypeError, ValueError):
                await self.send_json({"detail": "topic_id must be an integer."})
                return

        result, error = await self._create_group_message(
            group_id=self.group_id,
            sender_user_id=self.scope["user"].id,
            ciphertext=ciphertext,
            iv=iv,
            topic_id=topic_id,
        )
        if error:
            await self.send_json({"detail": error})
            return

        notification_pushes = result.pop("_notifications", [])
        message_payload = result

        await self.channel_layer.group_send(
            self.group_channel_name,
            {
                "type": "group.message",
                "payload": message_payload,
            },
        )
        if topic_id is not None:
            await self.channel_layer.group_send(
                f"group_{self.group_id}_topic_{topic_id}",
                {
                    "type": "group.message",
                    "payload": message_payload,
                },
            )

        for push in notification_pushes:
            await self.channel_layer.group_send(
                f"user_{push['recipient_id']}_notifications",
                {
                    "type": "send.notification",
                    "payload": {
                        "type": "notification",
                        "id": push["id"],
                        "message": push["content"],
                        "notification_type": push["notification_type"],
                        "is_read": False,
                        "created_at": push["created_at"],
                    },
                },
            )

    async def group_message(self, event):
        await self.send_json(event["payload"])

    async def group_typing(self, event):
        await self.send_json(event["payload"])

    @database_sync_to_async
    def _is_group_member(self, user_id, group_id):
        return GroupMember.objects.filter(group_id=group_id, user_id=user_id).exists()

    @database_sync_to_async
    def _create_group_message(self, group_id, sender_user_id, ciphertext, iv, topic_id):
        group = Group.objects.filter(id=group_id).first()
        if group is None:
            return None, "Group not found."

        is_member = GroupMember.objects.filter(
            group=group, user_id=sender_user_id
        ).exists()
        if not is_member:
            return None, "You are not a member of this group."

        topic = None
        if topic_id is not None:
            topic = GroupTopic.objects.filter(id=topic_id, group=group).first()
            if topic is None:
                return None, "Topic not found in this group."

        if group.is_supergroup and topic is None:
            return None, "topic_id is required for supergroup messages."

        message = GroupMessage.objects.create(
            group=group,
            topic=topic,
            sender_user_id=sender_user_id,
            ciphertext=ciphertext,
            iv=iv,
        )

        recipients = list(
            GroupMember.objects.filter(group=group)
            .exclude(user_id=sender_user_id)
            .select_related("user")
        )
        notification_pushes = []
        content = f"New message in group '{group.name}'."
        for member in recipients:
            notif = Notification.objects.create(
                recipient_user=member.user,
                actor_user_id=sender_user_id,
                notification_type=Notification.TYPE_MESSAGE,
                content=content,
            )
            notification_pushes.append(
                {
                    "id": notif.id,
                    "recipient_id": member.user_id,
                    "content": notif.content,
                    "notification_type": notif.notification_type,
                    "created_at": notif.created_at.isoformat(),
                }
            )

        return {
            "id": message.id,
            "group_id": message.group_id,
            "topic_id": message.topic_id,
            "sender_user_id": message.sender_user_id,
            "ciphertext": message.ciphertext,
            "iv": message.iv,
            "created_at": message.created_at.isoformat(),
            "_notifications": notification_pushes,
        }, None


class GroupTopicConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or user.is_anonymous:
            await self.close(code=4401)
            return

        self.group_id = int(self.scope["url_route"]["kwargs"]["group_id"])
        self.topic_id = int(self.scope["url_route"]["kwargs"]["topic_id"])
        self.group_channel_name = f"group_{self.group_id}"
        self.topic_channel_name = f"group_{self.group_id}_topic_{self.topic_id}"

        can_access_topic = await self._can_access_topic(
            user.id, self.group_id, self.topic_id
        )
        if not can_access_topic:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.topic_channel_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "topic_channel_name"):
            await self.channel_layer.group_discard(
                self.topic_channel_name, self.channel_name
            )

    async def receive_json(self, content, **kwargs):
        ciphertext = content.get("ciphertext")
        iv = content.get("iv")

        if not ciphertext or not iv:
            await self.send_json({"detail": "ciphertext and iv are required."})
            return

        result, error = await self._create_topic_message(
            group_id=self.group_id,
            topic_id=self.topic_id,
            sender_user_id=self.scope["user"].id,
            ciphertext=ciphertext,
            iv=iv,
        )
        if error:
            await self.send_json({"detail": error})
            return

        notification_pushes = result.pop("_notifications", [])
        message_payload = result

        await self.channel_layer.group_send(
            self.topic_channel_name,
            {
                "type": "group.message",
                "payload": message_payload,
            },
        )
        await self.channel_layer.group_send(
            self.group_channel_name,
            {
                "type": "group.message",
                "payload": message_payload,
            },
        )

        for push in notification_pushes:
            await self.channel_layer.group_send(
                f"user_{push['recipient_id']}_notifications",
                {
                    "type": "send.notification",
                    "payload": {
                        "type": "notification",
                        "id": push["id"],
                        "message": push["content"],
                        "notification_type": push["notification_type"],
                        "is_read": False,
                        "created_at": push["created_at"],
                    },
                },
            )

    async def group_message(self, event):
        await self.send_json(event["payload"])

    async def group_typing(self, event):
        await self.send_json(event["payload"])

    @database_sync_to_async
    def _can_access_topic(self, user_id, group_id, topic_id):
        is_member = GroupMember.objects.filter(
            group_id=group_id, user_id=user_id
        ).exists()
        if not is_member:
            return False
        return GroupTopic.objects.filter(id=topic_id, group_id=group_id).exists()

    @database_sync_to_async
    def _create_topic_message(self, group_id, topic_id, sender_user_id, ciphertext, iv):
        group = Group.objects.filter(id=group_id).first()
        if group is None:
            return None, "Group not found."

        topic = GroupTopic.objects.filter(id=topic_id, group_id=group_id).first()
        if topic is None:
            return None, "Topic not found in this group."

        is_member = GroupMember.objects.filter(
            group_id=group_id, user_id=sender_user_id
        ).exists()
        if not is_member:
            return None, "You are not a member of this group."

        message = GroupMessage.objects.create(
            group_id=group_id,
            topic_id=topic_id,
            sender_user_id=sender_user_id,
            ciphertext=ciphertext,
            iv=iv,
        )

        recipients = list(
            GroupMember.objects.filter(group_id=group_id)
            .exclude(user_id=sender_user_id)
            .select_related("user")
        )
        notification_pushes = []
        content = f"New message in topic '{topic.title}'."
        for member in recipients:
            notif = Notification.objects.create(
                recipient_user=member.user,
                actor_user_id=sender_user_id,
                notification_type=Notification.TYPE_MESSAGE,
                content=content,
            )
            notification_pushes.append(
                {
                    "id": notif.id,
                    "recipient_id": member.user_id,
                    "content": notif.content,
                    "notification_type": notif.notification_type,
                    "created_at": notif.created_at.isoformat(),
                }
            )

        return {
            "id": message.id,
            "group_id": message.group_id,
            "topic_id": message.topic_id,
            "sender_user_id": message.sender_user_id,
            "ciphertext": message.ciphertext,
            "iv": message.iv,
            "created_at": message.created_at.isoformat(),
            "_notifications": notification_pushes,
        }, None


class PresenceConsumer(AsyncJsonWebsocketConsumer):
    """
    Global presence WebSocket at /ws/presence/

    Incoming frames:
      {"type": "ping"}                            — keepalive, no reply
      {"type": "typing", "chat_id": N}            — direct chat typing
      {"type": "typing", "group_id": N}           — group typing
      {"type": "typing", "topic_id": N}           — topic typing

    Outgoing frames:
      {"type": "presence", "user_id": N, "online": bool}
      {"type": "typing",   "user_id": N, "chat_id"|"group_id"|"topic_id": N}
    """

    async def connect(self):
        user = self.scope.get("user")
        if user is None or user.is_anonymous:
            await self.close(code=4401)
            return

        self.user_id: int = user.id

        await self.channel_layer.group_add(_PRESENCE_GROUP, self.channel_name)
        await self.accept()

        # Send snapshot of everyone already online before announcing self.
        for uid in list(_presence_connections):
            await self.send_json({"type": "presence", "user_id": uid, "online": True})

        # Increment connection count; broadcast "online" only on the first tab.
        was_offline = self.user_id not in _presence_connections
        _presence_connections[self.user_id] = (
            _presence_connections.get(self.user_id, 0) + 1
        )
        if was_offline:
            await self.channel_layer.group_send(
                _PRESENCE_GROUP,
                {"type": "presence.update", "user_id": self.user_id, "online": True},
            )

    async def disconnect(self, close_code):
        if not hasattr(self, "user_id"):
            return

        count = _presence_connections.get(self.user_id, 0)
        if count <= 1:
            _presence_connections.pop(self.user_id, None)
            await self.channel_layer.group_send(
                _PRESENCE_GROUP,
                {"type": "presence.update", "user_id": self.user_id, "online": False},
            )
        else:
            _presence_connections[self.user_id] = count - 1

        await self.channel_layer.group_discard(_PRESENCE_GROUP, self.channel_name)

    async def receive_json(self, content, **kwargs):
        msg_type = content.get("type")
        if msg_type == "typing":
            await self._handle_typing(content)
        # "ping" and unknown types are silently ignored.

    # ------------------------------------------------------------------ #
    # Channel-layer event handler (called on all connected presence clients)
    # ------------------------------------------------------------------ #

    async def presence_update(self, event):
        await self.send_json(
            {
                "type": "presence",
                "user_id": event["user_id"],
                "online": event["online"],
            }
        )

    # ------------------------------------------------------------------ #
    # Typing dispatch                                                      #
    # ------------------------------------------------------------------ #

    async def _handle_typing(self, content):
        user_id = self.user_id
        raw_chat_id = content.get("chat_id")
        raw_group_id = content.get("group_id")
        raw_topic_id = content.get("topic_id")

        try:
            if raw_chat_id is not None:
                chat_id = int(raw_chat_id)
                if not await self._is_chat_member(user_id, chat_id):
                    return
                await self.channel_layer.group_send(
                    f"chat_{chat_id}",
                    {
                        "type": "chat.typing",
                        "payload": {
                            "type": "typing",
                            "user_id": user_id,
                            "chat_id": chat_id,
                        },
                    },
                )

            elif raw_group_id is not None:
                group_id = int(raw_group_id)
                if not await self._is_group_member(user_id, group_id):
                    return
                await self.channel_layer.group_send(
                    f"group_{group_id}",
                    {
                        "type": "group.typing",
                        "payload": {
                            "type": "typing",
                            "user_id": user_id,
                            "group_id": group_id,
                        },
                    },
                )

            elif raw_topic_id is not None:
                topic_id = int(raw_topic_id)
                group_id = await self._get_topic_group_id(user_id, topic_id)
                if group_id is None:
                    return
                await self.channel_layer.group_send(
                    f"group_{group_id}_topic_{topic_id}",
                    {
                        "type": "group.typing",
                        "payload": {
                            "type": "typing",
                            "user_id": user_id,
                            "topic_id": topic_id,
                        },
                    },
                )

        except (TypeError, ValueError):
            pass

    # ------------------------------------------------------------------ #
    # DB helpers                                                           #
    # ------------------------------------------------------------------ #

    @database_sync_to_async
    def _is_chat_member(self, user_id: int, chat_id: int) -> bool:
        return (
            Chat.objects.filter(id=chat_id)
            .filter(Q(sender_user_id=user_id) | Q(receiver_user_id=user_id))
            .exists()
        )

    @database_sync_to_async
    def _is_group_member(self, user_id: int, group_id: int) -> bool:
        return GroupMember.objects.filter(
            group_id=group_id, user_id=user_id
        ).exists()

    @database_sync_to_async
    def _get_topic_group_id(self, user_id: int, topic_id: int) -> int | None:
        """Return group_id if user is a member of the topic's group, else None."""
        topic = (
            GroupTopic.objects.filter(id=topic_id).only("group_id").first()
        )
        if topic is None:
            return None
        is_member = GroupMember.objects.filter(
            group_id=topic.group_id, user_id=user_id
        ).exists()
        return topic.group_id if is_member else None


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """
    Per-user notification WebSocket at /ws/notifications/

    Outgoing frames:
      {
        "type": "notification",
        "id": N,
        "message": "...",
        "notification_type": "message"|"system",
        "is_read": false,
        "created_at": "ISO8601"
      }
    """

    async def connect(self):
        user = self.scope.get("user")
        if user is None or user.is_anonymous:
            await self.close(code=4401)
            return

        self.user_id: int = user.id
        self.notification_group = f"user_{self.user_id}_notifications"

        await self.channel_layer.group_add(self.notification_group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "notification_group"):
            await self.channel_layer.group_discard(
                self.notification_group, self.channel_name
            )

    async def receive_json(self, content, **kwargs):
        pass  # clients send nothing

    async def send_notification(self, event):
        await self.send_json(event["payload"])
