from rest_framework import serializers
from .models import Message


class PublicKey(serializers.Serializer):
    public_key = serializers.CharField()


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
