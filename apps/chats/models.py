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
