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

        message_payload = await self._create_message(
            chat_id=self.chat_id,
            sender_user_id=self.scope["user"].id,
            ciphertext=ciphertext,
            iv=iv,
        )
        if message_payload is None:
            await self.send_json({"detail": "Unable to send message."})
            return

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.message",
                "payload": message_payload,
            },
        )

    async def chat_message(self, event):
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
        Notification.objects.create(
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

        message_payload, error = await self._create_group_message(
            group_id=self.group_id,
            sender_user_id=self.scope["user"].id,
            ciphertext=ciphertext,
            iv=iv,
            topic_id=topic_id,
        )
        if error:
            await self.send_json({"detail": error})
            return

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

    async def group_message(self, event):
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

        recipients = GroupMember.objects.filter(group=group).exclude(
            user_id=sender_user_id
        )
        Notification.objects.bulk_create(
            [
                Notification(
                    recipient_user=member.user,
                    actor_user_id=sender_user_id,
                    notification_type=Notification.TYPE_MESSAGE,
                    content=f"New message in group '{group.name}'.",
                )
                for member in recipients
            ]
        )

        return {
            "id": message.id,
            "group_id": message.group_id,
            "topic_id": message.topic_id,
            "sender_user_id": message.sender_user_id,
            "ciphertext": message.ciphertext,
            "iv": message.iv,
            "created_at": message.created_at.isoformat(),
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

        message_payload, error = await self._create_topic_message(
            group_id=self.group_id,
            topic_id=self.topic_id,
            sender_user_id=self.scope["user"].id,
            ciphertext=ciphertext,
            iv=iv,
        )
        if error:
            await self.send_json({"detail": error})
            return

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

    async def group_message(self, event):
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

        recipients = GroupMember.objects.filter(group_id=group_id).exclude(
            user_id=sender_user_id
        )
        Notification.objects.bulk_create(
            [
                Notification(
                    recipient_user=member.user,
                    actor_user_id=sender_user_id,
                    notification_type=Notification.TYPE_MESSAGE,
                    content=f"New message in topic '{topic.title}'.",
                )
                for member in recipients
            ]
        )

        return {
            "id": message.id,
            "group_id": message.group_id,
            "topic_id": message.topic_id,
            "sender_user_id": message.sender_user_id,
            "ciphertext": message.ciphertext,
            "iv": message.iv,
            "created_at": message.created_at.isoformat(),
        }, None
