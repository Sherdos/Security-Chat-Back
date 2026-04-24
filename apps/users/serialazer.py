from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import UserProfile

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("id", "username", "email", "password")
        extra_kwargs = {
            "id": {"read_only": True},
        }

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email")
        extra_kwargs = {
            "id": {"read_only": True},
            "email": {"read_only": True},
        }


class PublicKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ("user_id", "public_key", "created_at")
        extra_kwargs = {
            "user_id": {"read_only": True},
            "created_at": {"read_only": True},
        }


class PublicKeyUpdateSerializer(serializers.Serializer):
    public_key = serializers.CharField()


class UserProfileSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = (
            "user_id",
            "public_key",
            "avatar",
            "avatar_url",
            "description",
            "status",
            "created_at",
        )
        extra_kwargs = {
            "user_id": {"read_only": True},
            "public_key": {"read_only": True},
            "created_at": {"read_only": True},
        }

    def get_avatar_url(self, obj):
        request = self.context.get("request")
        if not obj.avatar:
            return None
        url = obj.avatar.url
        return request.build_absolute_uri(url) if request else url


class UserProfileUpdateSerializer(serializers.Serializer):
    avatar = serializers.ImageField(required=False, allow_null=True)
    description = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )
    status = serializers.CharField(required=False, allow_blank=True, max_length=120)
