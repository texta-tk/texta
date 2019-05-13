from django.db import models
from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.core.project.models import Project
from toolkit.core.user_profile.models import UserProfile
from toolkit.core.constants import MAX_STR_LEN

# Create your models here.
class Phrase(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    phrase = models.CharField(max_length=MAX_STR_LEN)
   
    def __str__(self):
        return self.phrase
