from django.db.models import Q
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.schemas.openapi import AutoSchema
from rest_framework.views import APIView

from ..models import Chat, Message, MessageAttachment, Notification
from ..serializers import (
    ChatCreateSerializer,
    ChatSerializer,
    MessageAttachmentCreateSerializer,
    MessageAttachmentSerializer,
    MessageCreateSerializer,
    MessageSerializer,
)
from .common import User, detect_attachment_type


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
        serializer = ChatSerializer(chats, context={"request": request}, many=True)
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
        output = ChatSerializer(
            chat,
            context={"request": request},
        )
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
        serializer = MessageSerializer(
            messages, context={"request": request}, many=True
        )
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
        output = MessageSerializer(
            message,
            context={"request": request},
        )
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
