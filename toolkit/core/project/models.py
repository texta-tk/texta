from django.db import models
from django.contrib.auth.models import User

from multiselectfield import MultiSelectField
from toolkit.constants import MAX_DESC_LEN


class Project(models.Model):
    title = models.CharField(max_length=MAX_DESC_LEN)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    users = models.ManyToManyField(User, related_name="project_users")
    indices = MultiSelectField(default=None)

    def __str__(self):
        return self.title
