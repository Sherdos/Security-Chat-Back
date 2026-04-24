from rest_framework import serializers

from apps.users.models import UserProfile


class BaseSerializer(serializers.ModelSerializer):

    def get_nested(self, serializer_class, instance, many=False, **kwargs):
        """Serialize nested object with forwarded context"""
        return serializer_class(
            instance, many=many, context=self.context, **kwargs
        ).data

    def get_absolute_url(self, file_field):
        """Build absolute URL for any file field"""
        request = self.context.get("request")
        if not file_field:
            return None
        url = file_field.url
        return request.build_absolute_uri(url) if request else url

    def get_request(self):
        """Safely get request from context"""
        return self.context.get("request")


class UserProfileChatSerializer(BaseSerializer):
    avatar_url = serializers.SerializerMethodField()
    username = serializers.CharField(source="user.username")

    class Meta:
        model = UserProfile
        fields = (
            "public_key",
            "username",
            "avatar_url",
            "description",
            "status",
            "created_at",
        )
        extra_kwargs = {
            "public_key": {"read_only": True},
            "created_at": {"read_only": True},
        }

    def get_avatar_url(self, obj):
        return self.get_absolute_url(obj.avatar)  # ← use base method


class UserProfilesSerializer(BaseSerializer):
    sender_user = serializers.SerializerMethodField()
    receiver_user = serializers.SerializerMethodField()

    def get_sender_user(self, obj):
        return self.get_nested(
            UserProfileChatSerializer, obj.sender_user.profile
        )  # ← use base method

    def get_receiver_user(self, obj):
        return self.get_nested(
            UserProfileChatSerializer, obj.receiver_user.profile
        )  # ← use base method
