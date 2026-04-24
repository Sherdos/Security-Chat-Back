from rest_framework import serializers

from ..models import Notification


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
