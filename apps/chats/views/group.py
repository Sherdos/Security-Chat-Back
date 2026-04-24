from rest_framework import permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.schemas.openapi import AutoSchema
from rest_framework.views import APIView

from ..models import Group, GroupMember, GroupMessage, GroupTopic, Notification
from ..serializers import (
    GroupCreateSerializer,
    GroupMemberAddSerializer,
    GroupMemberSerializer,
    GroupMessageCreateSerializer,
    GroupMessageSerializer,
    GroupSerializer,
    GroupTopicCreateSerializer,
    GroupTopicSerializer,
)
from .common import User


class GroupListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    schema = AutoSchema(tags=["Groups"], operation_id_base="group_list_create")

    def get_serializer_class(self):
        request = getattr(self, "request", None)
        method = getattr(request, "method", None)
        if method == "POST":
            return GroupCreateSerializer
        return GroupSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def get(self, request):
        groups = (
            Group.objects.filter(members__user=request.user)
            .distinct()
            .order_by("-created_at")
        )
        serializer = GroupSerializer(groups, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = GroupCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        group = Group.objects.create(
            name=serializer.validated_data["name"],
            description=serializer.validated_data.get("description", ""),
            is_supergroup=serializer.validated_data.get("is_supergroup", False),
            avatar=serializer.validated_data.get("avatar"),
            created_by=request.user,
        )
        GroupMember.objects.create(group=group, user=request.user, role=Group.OWNER)
        output = GroupSerializer(group, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)


class GroupDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(tags=["Groups"], operation_id_base="group_detail")

    def get_serializer_class(self):
        return GroupSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def get(self, request, group_id):
        group = Group.objects.filter(id=group_id, members__user=request.user).first()
        if group is None:
            return Response(
                {"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = GroupSerializer(group, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class GroupMemberListAddView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(tags=["Groups"], operation_id_base="group_member_list_add")

    def get_serializer_class(self):
        request = getattr(self, "request", None)
        method = getattr(request, "method", None)
        if method == "POST":
            return GroupMemberAddSerializer
        return GroupMemberSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def _get_group_if_member(self, user, group_id):
        return Group.objects.filter(id=group_id, members__user=user).first()

    def _is_group_admin(self, user, group):
        return GroupMember.objects.filter(
            group=group,
            user=user,
            role__in=[Group.OWNER, Group.ADMIN],
        ).exists()

    def get(self, request, group_id):
        group = self._get_group_if_member(request.user, group_id)
        if group is None:
            return Response(
                {"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND
            )
        members = GroupMember.objects.filter(group=group).order_by("joined_at")
        serializer = GroupMemberSerializer(members, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, group_id):
        group = self._get_group_if_member(request.user, group_id)
        if group is None:
            return Response(
                {"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not self._is_group_admin(request.user, group):
            return Response(
                {"detail": "Only admins can add members."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = GroupMemberAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_id = serializer.validated_data["user_id"]
        target_user = User.objects.filter(id=user_id).first()
        if target_user is None:
            return Response(
                {"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND
            )

        membership, created = GroupMember.objects.get_or_create(
            group=group,
            user=target_user,
            defaults={"role": Group.MEMBER},
        )
        if created:
            Notification.objects.create(
                recipient_user=target_user,
                actor_user=request.user,
                notification_type=Notification.TYPE_SYSTEM,
                content=f"You were added to group '{group.name}'.",
            )
        output = GroupMemberSerializer(membership)
        return Response(output.data, status=status.HTTP_201_CREATED)


class GroupTopicListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(tags=["Groups"], operation_id_base="group_topic_list_create")

    def get_serializer_class(self):
        request = getattr(self, "request", None)
        method = getattr(request, "method", None)
        if method == "POST":
            return GroupTopicCreateSerializer
        return GroupTopicSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def _get_group_if_member(self, user, group_id):
        return Group.objects.filter(id=group_id, members__user=user).first()

    def _is_group_admin(self, user, group):
        return GroupMember.objects.filter(
            group=group,
            user=user,
            role__in=[Group.OWNER, Group.ADMIN],
        ).exists()

    def get(self, request, group_id):
        group = self._get_group_if_member(request.user, group_id)
        if group is None:
            return Response(
                {"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND
            )
        topics = GroupTopic.objects.filter(group=group).order_by("created_at")
        serializer = GroupTopicSerializer(topics, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, group_id):
        group = self._get_group_if_member(request.user, group_id)
        if group is None:
            return Response(
                {"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if not group.is_supergroup:
            return Response(
                {"detail": "Topics are available only in supergroups."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not self._is_group_admin(request.user, group):
            return Response(
                {"detail": "Only admins can create topics."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = GroupTopicCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        topic = GroupTopic.objects.create(
            group=group,
            title=serializer.validated_data["title"],
            created_by=request.user,
        )
        output = GroupTopicSerializer(topic)
        return Response(output.data, status=status.HTTP_201_CREATED)


class GroupMessageListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(tags=["Groups"], operation_id_base="group_message_list_create")

    def get_serializer_class(self):
        request = getattr(self, "request", None)
        method = getattr(request, "method", None)
        if method == "POST":
            return GroupMessageCreateSerializer
        return GroupMessageSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def _get_group_if_member(self, user, group_id):
        return Group.objects.filter(id=group_id, members__user=user).first()

    def get(self, request, group_id):
        group = self._get_group_if_member(request.user, group_id)
        if group is None:
            return Response(
                {"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND
            )

        topic_id = request.query_params.get("topic_id")
        messages = GroupMessage.objects.filter(group=group)
        if topic_id:
            messages = messages.filter(topic_id=topic_id)
        messages = messages.order_by("created_at")
        serializer = GroupMessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, group_id):
        group = self._get_group_if_member(request.user, group_id)
        if group is None:
            return Response(
                {"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = GroupMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        topic_id = serializer.validated_data.get("topic_id")
        topic = None
        if topic_id is not None:
            topic = GroupTopic.objects.filter(id=topic_id, group=group).first()
            if topic is None:
                return Response(
                    {"detail": "Topic not found in this group."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        if topic is None and group.is_supergroup:
            return Response(
                {"detail": "topic_id is required for supergroup messages."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        message = GroupMessage.objects.create(
            group=group,
            topic=topic,
            sender_user=request.user,
            ciphertext=serializer.validated_data["ciphertext"],
            iv=serializer.validated_data["iv"],
        )

        recipients = GroupMember.objects.filter(group=group).exclude(user=request.user)
        notifications = [
            Notification(
                recipient_user=member.user,
                actor_user=request.user,
                notification_type=Notification.TYPE_MESSAGE,
                content=f"New message in group '{group.name}'.",
            )
            for member in recipients
        ]
        Notification.objects.bulk_create(notifications)

        output = GroupMessageSerializer(message)
        return Response(output.data, status=status.HTTP_201_CREATED)
