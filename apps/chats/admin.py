from django.contrib import admin

from .models import (
    Chat,
    Group,
    GroupMember,
    GroupMessage,
    GroupTopic,
    Message,
    MessageAttachment,
    Notification,
)


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ("id", "sender_user", "receiver_user", "created_at")
    search_fields = (
        "sender_user__username",
        "sender_user__email",
        "receiver_user__username",
        "receiver_user__email",
    )
    list_filter = ("created_at",)
    ordering = ("-created_at",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "chat",
        "sender_user",
        "receiver_user",
        "created_at",
    )
    search_fields = (
        "chat__id",
        "sender_user__username",
        "sender_user__email",
        "receiver_user__username",
        "receiver_user__email",
    )
    list_filter = ("created_at", "chat")
    ordering = ("-created_at",)


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "message",
        "attachment_type",
        "uploaded_by",
        "created_at",
    )
    search_fields = (
        "message__id",
        "uploaded_by__username",
        "uploaded_by__email",
        "file",
    )
    list_filter = ("attachment_type", "created_at")
    ordering = ("-created_at",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "recipient_user",
        "actor_user",
        "notification_type",
        "is_read",
        "created_at",
    )
    search_fields = (
        "recipient_user__username",
        "recipient_user__email",
        "actor_user__username",
        "actor_user__email",
        "content",
    )
    list_filter = ("notification_type", "is_read", "created_at")
    ordering = ("-created_at",)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_supergroup", "created_by", "created_at")
    search_fields = ("name", "description", "created_by__username", "created_by__email")
    list_filter = ("is_supergroup", "created_at")
    ordering = ("-created_at",)


@admin.register(GroupMember)
class GroupMemberAdmin(admin.ModelAdmin):
    list_display = ("id", "group", "user", "role", "joined_at")
    search_fields = ("group__name", "user__username", "user__email")
    list_filter = ("role", "joined_at")
    ordering = ("-joined_at",)


@admin.register(GroupTopic)
class GroupTopicAdmin(admin.ModelAdmin):
    list_display = ("id", "group", "title", "created_by", "created_at")
    search_fields = ("group__name", "title", "created_by__username")
    list_filter = ("created_at",)
    ordering = ("-created_at",)


@admin.register(GroupMessage)
class GroupMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "group", "topic", "sender_user", "created_at")
    search_fields = ("group__name", "topic__title", "sender_user__username")
    list_filter = ("group", "topic", "created_at")
    ordering = ("-created_at",)
