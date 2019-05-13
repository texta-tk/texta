from django.db import models

from toolkit.core.project.models import Project
from toolkit.core.user_profile.models import UserProfile
from toolkit.core.phrase.models import Phrase
from toolkit.core.constants import MAX_STR_LEN

# Create your models here.
class Lexicon(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    description = models.CharField(max_length=MAX_STR_LEN)
    author = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    phrases = models.ManyToManyField(Phrase)

    def __str__(self):
        return self.description
