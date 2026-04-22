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
