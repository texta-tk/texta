from django.db import models
from multiselectfield import MultiSelectField
from toolkit.core.user_profile.models import UserProfile
from toolkit.core.constants import MAX_STR_LEN

# Create your models here.
class Project(models.Model):
    title = models.CharField(max_length=MAX_STR_LEN)
    owner = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    users = models.ManyToManyField(UserProfile, related_name="project_users")
    indices = MultiSelectField(default=None)

    def __str__(self):
        return self.title
