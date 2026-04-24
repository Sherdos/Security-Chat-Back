from django.db import models
from django.contrib.auth import get_user_model

user = get_user_model()
# Create your models here.


class UserProfile(models.Model):

    user = models.OneToOneField(user, on_delete=models.CASCADE, related_name="profile")

    public_key = models.TextField(blank=True, default="")
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    description = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=120, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
