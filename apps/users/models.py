from django.db import models
from django.contrib.auth import get_user_model

user = get_user_model()
# Create your models here.


class UserProfile(models.Model):

    user = models.OneToOneField(user, on_delete=models.CASCADE, related_name="profile")

    public_key = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
