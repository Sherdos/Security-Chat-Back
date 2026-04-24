from rest_framework import serializers

from .base import BaseSerializer, UserProfileChatSerializer, UserProfilesSerializer
from ..models import Group, GroupMember, GroupMessage, GroupTopic


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


class GroupMemberSerializer(BaseSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = GroupMember
        fields = ("id", "group_id", "user_id", "user", "role", "joined_at")
        extra_kwargs = {
            "id": {"read_only": True},
            "group_id": {"read_only": True},
            "joined_at": {"read_only": True},
        }

    def get_user(self, obj):
        return self.get_nested(UserProfileChatSerializer, obj.user.profile)


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


class GroupMessageSerializer(UserProfilesSerializer):
    class Meta:
        model = GroupMessage
        fields = (
            "id",
            "group_id",
            "topic_id",
            "sender_user_id",
            "sender_user",
            "ciphertext",
            "iv",
            "created_at",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "group_id": {"read_only": True},
            "sender_user_id": {"read_only": True},
            "sender_user": {"read_only": True},
            "created_at": {"read_only": True},
        }


class GroupMessageCreateSerializer(serializers.Serializer):
    topic_id = serializers.IntegerField(required=False)
    ciphertext = serializers.CharField()
    iv = serializers.CharField(max_length=32)
