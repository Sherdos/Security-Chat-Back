from rest_framework import serializers

from .base import UserProfilesSerializer
from ..models import Chat, Message, MessageAttachment


class ChatSerializer(UserProfilesSerializer):
    class Meta:
        model = Chat
        fields = (
            "id",
            "receiver_user_id",
            "sender_user_id",
            "created_at",
            "receiver_user",
            "sender_user",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "sender_user_id": {"read_only": True},
            "created_at": {"read_only": True},
        }


class ChatCreateSerializer(serializers.Serializer):
    receiver_user_id = serializers.IntegerField()


class MessageCreateSerializer(serializers.Serializer):
    ciphertext = serializers.CharField(required=False, allow_blank=True)
    iv = serializers.CharField(max_length=32)


class MessageAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = MessageAttachment
        fields = (
            "id",
            "attachment_type",
            "file",
            "file_url",
            "uploaded_by_id",
            "created_at",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "uploaded_by_id": {"read_only": True},
            "created_at": {"read_only": True},
        }

    def get_file_url(self, obj):
        request = self.context.get("request")
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url


class MessageAttachmentCreateSerializer(serializers.Serializer):
    file = serializers.FileField()


class MessageSerializer(UserProfilesSerializer):
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            "id",
            "chat_id",
            "iv",
            "ciphertext",
            "receiver_user_id",
            "sender_user_id",
            "receiver_user",
            "sender_user",
            "created_at",
            "attachments",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "created_at": {"read_only": True},
            "sender_user": {"read_only": True},
        }

    def get_attachments(self, obj):
        return MessageAttachmentSerializer(
            obj.attachments.all(),
            many=True,
            context=self.context,
        ).data
