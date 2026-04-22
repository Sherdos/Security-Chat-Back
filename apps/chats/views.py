from django.contrib.auth import get_user_model
from django.db.models import Q
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.schemas.openapi import AutoSchema
from rest_framework.views import APIView

from .models import Chat, Message
from .serialazer import (
    ChatCreateSerializer,
    ChatSerializer,
    MessageCreateSerializer,
    MessageSerializer,
)

User = get_user_model()


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

        if request.user.id == chat.sender_user_id:
            receiver_user = chat.receiver_user
        else:
            receiver_user = chat.sender_user

        message = Message.objects.create(
            chat=chat,
            sender_user=request.user,
            receiver_user=receiver_user,
            ciphertext=serializer.validated_data["ciphertext"],
            iv=serializer.validated_data["iv"],
        )
        output = MessageSerializer(message)
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

        return {
            "id": message.id,
            "chat_id": message.chat_id,
            "iv": message.iv,
            "ciphertext": message.ciphertext,
            "receiver_user_id": message.receiver_user_id,
            "sender_user_id": message.sender_user_id,
            "created_at": message.created_at.isoformat(),
        }
