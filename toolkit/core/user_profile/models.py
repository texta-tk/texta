import json
import uuid as unique_id  # To avoid potential name conflicts.

from django.contrib.auth.models import User
from django.db import models

from toolkit.constants import MAX_DESC_LEN


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    uuid = models.UUIDField(null=True, editable=False, unique=True)

    first_name = models.TextField(null=True, default=None)
    last_name = models.TextField(null=True, default=None)

    is_uaa_account = models.BooleanField(default=False)
    scopes = models.CharField(max_length=MAX_DESC_LEN, default=json.dumps([]))
    # define the application user is used for (e.g. "toolkit" and "law")
    application = models.CharField(max_length=MAX_DESC_LEN, default="toolkit")


    @staticmethod
    def create_uuid(method=unique_id.uuid4, attempt_count: int = 10) -> str:
        """
        Safely handle the creation of uuid's
        """
        for i in range(attempt_count):
            unique_id_string = method().hex
            is_duplicate = UserProfile.objects.filter(uuid=unique_id_string).exists()
            if is_duplicate is False:
                return unique_id_string

        raise ValueError(f"Did not manage to get unique uuid in {attempt_count} attemps!")


    @property
    def get_display_name(self):

        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        else:
            return self.user.username


    def __str__(self):
        return f"Profile - {self.user.username}"
