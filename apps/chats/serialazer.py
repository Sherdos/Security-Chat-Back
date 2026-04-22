from rest_framework import serializers
from .models import Chat, Message


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
    ciphertext = serializers.CharField()
    iv = serializers.CharField(max_length=32)


class MessageSerializer(serializers.ModelSerializer):
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
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "created_at": {"read_only": True},
            "sender_user_id": {"read_only": True},
        }
