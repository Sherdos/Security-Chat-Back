from django.contrib.auth import get_user_model
from django.db.models import Q
import mimetypes
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.schemas.openapi import AutoSchema
from rest_framework.views import APIView

from .models import (
    Chat,
    Group,
    GroupMember,
    GroupMessage,
    GroupTopic,
    Message,
    MessageAttachment,
    Notification,
)
from .serialazer import (
    ChatCreateSerializer,
    ChatSerializer,
    GroupCreateSerializer,
    GroupMemberAddSerializer,
    GroupMemberSerializer,
    GroupMessageCreateSerializer,
    GroupMessageSerializer,
    GroupSerializer,
    GroupTopicCreateSerializer,
    GroupTopicSerializer,
    MessageAttachmentCreateSerializer,
    MessageAttachmentSerializer,
    MessageCreateSerializer,
    MessageSerializer,
    NotificationSerializer,
)

User = get_user_model()


def detect_attachment_type(uploaded_file):
    mime_type, _ = mimetypes.guess_type(uploaded_file.name)
    if mime_type:
        if mime_type.startswith("image/"):
            return MessageAttachment.ATTACHMENT_IMAGE
        if mime_type.startswith("video/"):
            return MessageAttachment.ATTACHMENT_VIDEO
        if mime_type.startswith("audio/"):
            return MessageAttachment.ATTACHMENT_AUDIO
    return MessageAttachment.ATTACHMENT_FILE


class ChatListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(tags=["Chats"], operation_id_base="chat_list_create")

    def get_serializer_class(self):
        request = getattr(self, "request", None)
        method = getattr(request, "method", None)
        if method == "POST":
            return ChatCreateSerializer
        return ChatSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def get(self, request):
        chats = Chat.objects.filter(
            sender_user=request.user,
        ) | Chat.objects.filter(receiver_user=request.user)
        chats = chats.order_by("-created_at")
        serializer = ChatSerializer(chats, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = ChatCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        receiver_user_id = serializer.validated_data["receiver_user_id"]
        if receiver_user_id == request.user.id:
            return Response(
                {"detail": "You cannot create a chat with yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        receiver_user = User.objects.filter(id=receiver_user_id).first()
        if receiver_user is None:
            return Response(
                {"detail": "Receiver user not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        chat = Chat.objects.filter(
            Q(sender_user=request.user, receiver_user=receiver_user)
            | Q(sender_user=receiver_user, receiver_user=request.user)
        ).first()
        if chat is None:
            chat = Chat.objects.create(
                sender_user=request.user,
                receiver_user=receiver_user,
            )
        output = ChatSerializer(chat)
        return Response(output.data, status=status.HTTP_201_CREATED)


class ChatMessageListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(tags=["Chats"], operation_id_base="chat_message_list_create")

    def get_serializer_class(self):
        request = getattr(self, "request", None)
        method = getattr(request, "method", None)
        if method == "POST":
            return MessageCreateSerializer
        return MessageSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def _get_chat_if_member(self, user, chat_id):
        chat = Chat.objects.filter(id=chat_id).first()
        if chat is None:
            return None
        if user.id not in [chat.sender_user_id, chat.receiver_user_id]:
            return None
        return chat

    def get(self, request, chat_id):
        chat = self._get_chat_if_member(request.user, chat_id)
        if chat is None:
            return Response(
                {"detail": "Chat not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        messages = Message.objects.filter(chat=chat).order_by("created_at")
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, chat_id):
        chat = self._get_chat_if_member(request.user, chat_id)
        if chat is None:
            return Response(
                {"detail": "Chat not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ciphertext = serializer.validated_data.get("ciphertext", "")
        if not ciphertext:
            return Response(
                {"detail": "ciphertext is required for text messages."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.user.id == chat.sender_user_id:
            receiver_user = chat.receiver_user
        else:
            receiver_user = chat.sender_user

        message = Message.objects.create(
            chat=chat,
            sender_user=request.user,
            receiver_user=receiver_user,
            ciphertext=ciphertext,
            iv=serializer.validated_data["iv"],
        )
        Notification.objects.create(
            recipient_user=receiver_user,
            actor_user=request.user,
            notification_type=Notification.TYPE_MESSAGE,
            content="You received a new message.",
        )
        output = MessageSerializer(message)
        return Response(output.data, status=status.HTTP_201_CREATED)


class MessageAttachmentCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    schema = AutoSchema(tags=["Chats"], operation_id_base="message_attachment_create")

    def get_serializer_class(self):
        return MessageAttachmentCreateSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def post(self, request, message_id):
        serializer = MessageAttachmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = Message.objects.filter(id=message_id).first()
        if message is None:
            return Response(
                {"detail": "Message not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.user.id not in [message.sender_user_id, message.receiver_user_id]:
            return Response(
                {"detail": "Message not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        uploaded_file = serializer.validated_data["file"]
        attachment = MessageAttachment.objects.create(
            message=message,
            uploaded_by=request.user,
            file=uploaded_file,
            attachment_type=detect_attachment_type(uploaded_file),
        )
        notification_recipient = (
            message.receiver_user
            if request.user.id == message.sender_user_id
            else message.sender_user
        )
        Notification.objects.create(
            recipient_user=notification_recipient,
            actor_user=request.user,
            notification_type=Notification.TYPE_MESSAGE,
            content="You received a new attachment.",
        )
        output = MessageAttachmentSerializer(attachment, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)


class NotificationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(tags=["Chats"], operation_id_base="notification_list")

    def get_serializer_class(self):
        return NotificationSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def get(self, request):
        notifications = Notification.objects.filter(
            recipient_user=request.user
        ).order_by("-created_at")
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class NotificationMarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(tags=["Chats"], operation_id_base="notification_mark_read")

    def get_serializer_class(self):
        return NotificationSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def post(self, request, notification_id):
        notification = Notification.objects.filter(
            id=notification_id,
            recipient_user=request.user,
        ).first()
        if notification is None:
            return Response(
                {"detail": "Notification not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        serializer = NotificationSerializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GroupListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    schema = AutoSchema(tags=["Groups"], operation_id_base="group_list_create")

    def get_serializer_class(self):
        request = getattr(self, "request", None)
        method = getattr(request, "method", None)
        if method == "POST":
            return GroupCreateSerializer
        return GroupSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def get(self, request):
        groups = (
            Group.objects.filter(members__user=request.user)
            .distinct()
            .order_by("-created_at")
        )
        serializer = GroupSerializer(groups, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = GroupCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        group = Group.objects.create(
            name=serializer.validated_data["name"],
            description=serializer.validated_data.get("description", ""),
            is_supergroup=serializer.validated_data.get("is_supergroup", False),
            avatar=serializer.validated_data.get("avatar"),
            created_by=request.user,
        )
        GroupMember.objects.create(group=group, user=request.user, role=Group.OWNER)
        output = GroupSerializer(group, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)


class GroupDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(tags=["Groups"], operation_id_base="group_detail")

    def get_serializer_class(self):
        return GroupSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def get(self, request, group_id):
        group = Group.objects.filter(id=group_id, members__user=request.user).first()
        if group is None:
            return Response(
                {"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = GroupSerializer(group, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class GroupMemberListAddView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(tags=["Groups"], operation_id_base="group_member_list_add")

    def get_serializer_class(self):
        request = getattr(self, "request", None)
        method = getattr(request, "method", None)
        if method == "POST":
            return GroupMemberAddSerializer
        return GroupMemberSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def _get_group_if_member(self, user, group_id):
        return Group.objects.filter(id=group_id, members__user=user).first()

    def _is_group_admin(self, user, group):
        return GroupMember.objects.filter(
            group=group,
            user=user,
            role__in=[Group.OWNER, Group.ADMIN],
        ).exists()

    def get(self, request, group_id):
        group = self._get_group_if_member(request.user, group_id)
        if group is None:
            return Response(
                {"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND
            )
        members = GroupMember.objects.filter(group=group).order_by("joined_at")
        serializer = GroupMemberSerializer(members, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, group_id):
        group = self._get_group_if_member(request.user, group_id)
        if group is None:
            return Response(
                {"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not self._is_group_admin(request.user, group):
            return Response(
                {"detail": "Only admins can add members."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = GroupMemberAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_id = serializer.validated_data["user_id"]
        target_user = User.objects.filter(id=user_id).first()
        if target_user is None:
            return Response(
                {"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND
            )

        membership, created = GroupMember.objects.get_or_create(
            group=group,
            user=target_user,
            defaults={"role": Group.MEMBER},
        )
        if created:
            Notification.objects.create(
                recipient_user=target_user,
                actor_user=request.user,
                notification_type=Notification.TYPE_SYSTEM,
                content=f"You were added to group '{group.name}'.",
            )
        output = GroupMemberSerializer(membership)
        return Response(output.data, status=status.HTTP_201_CREATED)


class GroupTopicListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(tags=["Groups"], operation_id_base="group_topic_list_create")

    def get_serializer_class(self):
        request = getattr(self, "request", None)
        method = getattr(request, "method", None)
        if method == "POST":
            return GroupTopicCreateSerializer
        return GroupTopicSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def _get_group_if_member(self, user, group_id):
        return Group.objects.filter(id=group_id, members__user=user).first()

    def _is_group_admin(self, user, group):
        return GroupMember.objects.filter(
            group=group,
            user=user,
            role__in=[Group.OWNER, Group.ADMIN],
        ).exists()

    def get(self, request, group_id):
        group = self._get_group_if_member(request.user, group_id)
        if group is None:
            return Response(
                {"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND
            )
        topics = GroupTopic.objects.filter(group=group).order_by("created_at")
        serializer = GroupTopicSerializer(topics, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, group_id):
        group = self._get_group_if_member(request.user, group_id)
        if group is None:
            return Response(
                {"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if not group.is_supergroup:
            return Response(
                {"detail": "Topics are available only in supergroups."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not self._is_group_admin(request.user, group):
            return Response(
                {"detail": "Only admins can create topics."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = GroupTopicCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        topic = GroupTopic.objects.create(
            group=group,
            title=serializer.validated_data["title"],
            created_by=request.user,
        )
        output = GroupTopicSerializer(topic)
        return Response(output.data, status=status.HTTP_201_CREATED)


class GroupMessageListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(tags=["Groups"], operation_id_base="group_message_list_create")

    def get_serializer_class(self):
        request = getattr(self, "request", None)
        method = getattr(request, "method", None)
        if method == "POST":
            return GroupMessageCreateSerializer
        return GroupMessageSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def _get_group_if_member(self, user, group_id):
        return Group.objects.filter(id=group_id, members__user=user).first()

    def get(self, request, group_id):
        group = self._get_group_if_member(request.user, group_id)
        if group is None:
            return Response(
                {"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND
            )

        topic_id = request.query_params.get("topic_id")
        messages = GroupMessage.objects.filter(group=group)
        if topic_id:
            messages = messages.filter(topic_id=topic_id)
        messages = messages.order_by("created_at")
        serializer = GroupMessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, group_id):
        group = self._get_group_if_member(request.user, group_id)
        if group is None:
            return Response(
                {"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = GroupMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        topic_id = serializer.validated_data.get("topic_id")
        topic = None
        if topic_id is not None:
            topic = GroupTopic.objects.filter(id=topic_id, group=group).first()
            if topic is None:
                return Response(
                    {"detail": "Topic not found in this group."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        if topic is None and group.is_supergroup:
            return Response(
                {"detail": "topic_id is required for supergroup messages."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        message = GroupMessage.objects.create(
            group=group,
            topic=topic,
            sender_user=request.user,
            ciphertext=serializer.validated_data["ciphertext"],
            iv=serializer.validated_data["iv"],
        )

        recipients = GroupMember.objects.filter(group=group).exclude(user=request.user)
        notifications = [
            Notification(
                recipient_user=member.user,
                actor_user=request.user,
                notification_type=Notification.TYPE_MESSAGE,
                content=f"New message in group '{group.name}'.",
            )
            for member in recipients
        ]
        Notification.objects.bulk_create(notifications)

        output = GroupMessageSerializer(message)
        return Response(output.data, status=status.HTTP_201_CREATED)


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
