from django.db import models
from toolkit.core.project.models import Project
from toolkit.core.user_profile.models import UserProfile
from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.core.constants import MAX_STR_LEN

# Create your models here.
class Search(models.Model):
    description = models.CharField(max_length=MAX_STR_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    query = models.TextField(default=EMPTY_QUERY)

    def __str__(self):
        return self.query
