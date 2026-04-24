from django.db import models
from django.contrib.auth import get_user_model

user = get_user_model()
# Create your models here.


class Chat(models.Model):
    receiver_user = models.ForeignKey(
        user, on_delete=models.CASCADE, related_name="receive_chats"
    )
    sender_user = models.ForeignKey(
        user, on_delete=models.CASCADE, related_name="send_chats"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("receiver_user", "sender_user")


class Message(models.Model):
    ciphertext = models.TextField()
    iv = models.CharField(max_length=32)
    chat = models.ForeignKey(
        "chats.Chat", on_delete=models.CASCADE, related_name="messages"
    )
    receiver_user = models.ForeignKey(
        user, on_delete=models.CASCADE, related_name="receive_messages"
    )
    sender_user = models.ForeignKey(
        user, on_delete=models.CASCADE, related_name="send_messages"
    )
    created_at = models.DateTimeField(auto_now_add=True)


class MessageAttachment(models.Model):
    ATTACHMENT_IMAGE = "image"
    ATTACHMENT_VIDEO = "video"
    ATTACHMENT_AUDIO = "audio"
    ATTACHMENT_FILE = "file"

    ATTACHMENT_TYPE_CHOICES = (
        (ATTACHMENT_IMAGE, "Image"),
        (ATTACHMENT_VIDEO, "Video"),
        (ATTACHMENT_AUDIO, "Audio"),
        (ATTACHMENT_FILE, "File"),
    )

    message = models.ForeignKey(
        "chats.Message", on_delete=models.CASCADE, related_name="attachments"
    )
    uploaded_by = models.ForeignKey(
        user, on_delete=models.CASCADE, related_name="uploaded_attachments"
    )
    file = models.FileField(upload_to="message_attachments/")
    attachment_type = models.CharField(max_length=16, choices=ATTACHMENT_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)


class Notification(models.Model):
    TYPE_MESSAGE = "message"
    TYPE_SYSTEM = "system"

    TYPE_CHOICES = (
        (TYPE_MESSAGE, "Message"),
        (TYPE_SYSTEM, "System"),
    )

    recipient_user = models.ForeignKey(
        user, on_delete=models.CASCADE, related_name="notifications"
    )
    actor_user = models.ForeignKey(
        user,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sent_notifications",
    )
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    content = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class Group(models.Model):
    MEMBER = "member"
    ADMIN = "admin"
    OWNER = "owner"

    ROLE_CHOICES = (
        (MEMBER, "Member"),
        (ADMIN, "Admin"),
        (OWNER, "Owner"),
    )

    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True, default="")
    avatar = models.ImageField(upload_to="group_avatars/", null=True, blank=True)
    is_supergroup = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        user,
        on_delete=models.CASCADE,
        related_name="created_groups",
    )
    created_at = models.DateTimeField(auto_now_add=True)


class GroupMember(models.Model):
    group = models.ForeignKey(
        "chats.Group", on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        user, on_delete=models.CASCADE, related_name="group_memberships"
    )
    role = models.CharField(
        max_length=20, choices=Group.ROLE_CHOICES, default=Group.MEMBER
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("group", "user")


class GroupTopic(models.Model):
    group = models.ForeignKey(
        "chats.Group", on_delete=models.CASCADE, related_name="topics"
    )
    title = models.CharField(max_length=120)
    created_by = models.ForeignKey(
        user,
        on_delete=models.CASCADE,
        related_name="created_topics",
    )
    created_at = models.DateTimeField(auto_now_add=True)


class GroupMessage(models.Model):
    group = models.ForeignKey(
        "chats.Group", on_delete=models.CASCADE, related_name="messages"
    )
    topic = models.ForeignKey(
        "chats.GroupTopic",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="messages",
    )
    sender_user = models.ForeignKey(
        user,
        on_delete=models.CASCADE,
        related_name="sent_group_messages",
    )
    ciphertext = models.TextField()
    iv = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)
