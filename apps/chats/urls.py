from django.urls import path

from .views import (
    ChatListCreateView,
    ChatMessageListCreateView,
    GroupDetailView,
    GroupE2EKeyView,
    GroupListCreateView,
    GroupMemberListAddView,
    GroupMessageListCreateView,
    GroupTopicListCreateView,
    MessageAttachmentCreateView,
    NotificationListView,
    NotificationMarkReadView,
)

urlpatterns = [
    path("", ChatListCreateView.as_view(), name="chat_list_create"),
    path("groups/", GroupListCreateView.as_view(), name="group_list_create"),
    path("groups/<int:group_id>/", GroupDetailView.as_view(), name="group_detail"),
    path(
        "groups/<int:group_id>/members/",
        GroupMemberListAddView.as_view(),
        name="group_members",
    ),
    path(
        "groups/<int:group_id>/topics/",
        GroupTopicListCreateView.as_view(),
        name="group_topics",
    ),
    path(
        "groups/<int:group_id>/messages/",
        GroupMessageListCreateView.as_view(),
        name="group_messages",
    ),
    path(
        "groups/<int:group_id>/e2e-key/",
        GroupE2EKeyView.as_view(),
        name="group_e2e_key",
    ),
    path(
        "<int:chat_id>/messages/",
        ChatMessageListCreateView.as_view(),
        name="chat_messages",
    ),
    path(
        "messages/<int:message_id>/attachments/",
        MessageAttachmentCreateView.as_view(),
        name="message_attachment_create",
    ),
    path("notifications/", NotificationListView.as_view(), name="notification_list"),
    path(
        "notifications/<int:notification_id>/read/",
        NotificationMarkReadView.as_view(),
        name="notification_mark_read",
    ),
]
