from django.db import models
from django.contrib.auth.models import User

from toolkit.elastic.tools.searcher import EMPTY_QUERY
from toolkit.core.project.models import Project
from toolkit.constants import MAX_DESC_LEN

# Create your models here.
class Phrase(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    phrase = models.CharField(max_length=MAX_DESC_LEN)
   
    def __str__(self):
        return self.phrase
