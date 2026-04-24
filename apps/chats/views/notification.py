from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.schemas.openapi import AutoSchema
from rest_framework.views import APIView

from ..models import Notification
from ..serializers import NotificationSerializer


class NotificationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(tags=["Chats"], operation_id_base="notification_list")

    def get_serializer_class(self):
        return NotificationSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def get(self, request):
        notifications = Notification.objects.filter(
            recipient_user=request.user
        ).order_by("-created_at")
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class NotificationMarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(tags=["Chats"], operation_id_base="notification_mark_read")

    def get_serializer_class(self):
        return NotificationSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def post(self, request, notification_id):
        notification = Notification.objects.filter(
            id=notification_id,
            recipient_user=request.user,
        ).first()
        if notification is None:
            return Response(
                {"detail": "Notification not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        serializer = NotificationSerializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)
