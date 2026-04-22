from django.contrib.auth import get_user_model
from django.db.models import Q
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
