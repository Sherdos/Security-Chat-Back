from rest_framework import serializers
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


class ChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chat
        fields = ("id", "receiver_user_id", "sender_user_id", "created_at")
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


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = (
            "id",
            "recipient_user_id",
            "actor_user_id",
            "notification_type",
            "content",
            "is_read",
            "created_at",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "recipient_user_id": {"read_only": True},
            "actor_user_id": {"read_only": True},
            "notification_type": {"read_only": True},
            "content": {"read_only": True},
            "created_at": {"read_only": True},
        }


class GroupSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = (
            "id",
            "name",
            "description",
            "avatar",
            "avatar_url",
            "is_supergroup",
            "created_by_id",
            "created_at",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "created_by_id": {"read_only": True},
            "created_at": {"read_only": True},
        }

    def get_avatar_url(self, obj):
        request = self.context.get("request")
        if not obj.avatar:
            return None
        url = obj.avatar.url
        return request.build_absolute_uri(url) if request else url


class GroupCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    description = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )
    is_supergroup = serializers.BooleanField(required=False, default=False)
    avatar = serializers.ImageField(required=False, allow_null=True)


class GroupMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupMember
        fields = ("id", "group_id", "user_id", "role", "joined_at")
        extra_kwargs = {
            "id": {"read_only": True},
            "group_id": {"read_only": True},
            "joined_at": {"read_only": True},
        }


class GroupMemberAddSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()


class GroupTopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupTopic
        fields = ("id", "group_id", "title", "created_by_id", "created_at")
        extra_kwargs = {
            "id": {"read_only": True},
            "group_id": {"read_only": True},
            "created_by_id": {"read_only": True},
            "created_at": {"read_only": True},
        }


class GroupTopicCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120)


class GroupMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupMessage
        fields = (
            "id",
            "group_id",
            "topic_id",
            "sender_user_id",
            "ciphertext",
            "iv",
            "created_at",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "group_id": {"read_only": True},
            "sender_user_id": {"read_only": True},
            "created_at": {"read_only": True},
        }


class GroupMessageCreateSerializer(serializers.Serializer):
    topic_id = serializers.IntegerField(required=False)
    ciphertext = serializers.CharField()
    iv = serializers.CharField(max_length=32)


class MessageSerializer(serializers.ModelSerializer):
    attachments = MessageAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Message
        fields = (
            "id",
            "chat_id",
            "iv",
            "ciphertext",
            "receiver_user_id",
            "created_at",
            "sender_user_id",
            "attachments",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "created_at": {"read_only": True},
            "sender_user_id": {"read_only": True},
        }
