from django.db import models
from django.contrib.auth.models import User

from toolkit.constants import MAX_DESC_LEN


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    scope = models.CharField(max_length=MAX_DESC_LEN, default="None")
    # define the application user is used for (e.g. "toolkit" and "law")
    application = models.CharField(max_length=MAX_DESC_LEN, default="toolkit")

    def __str__(self):
        return f"Profile - {self.user.username}"
