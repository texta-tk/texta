from django.db import models
from django.contrib.auth.models import User

from toolkit.core.project.models import Project
from toolkit.core.phrase.models import Phrase
from toolkit.constants import MAX_DESC_LEN

# Create your models here.
class Lexicon(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    description = models.CharField(max_length=MAX_DESC_LEN)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    phrases = models.TextField(default='')

    def __str__(self):
        return self.description
