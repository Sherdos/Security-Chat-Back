from django.contrib import admin

from .models import Chat, Message


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
