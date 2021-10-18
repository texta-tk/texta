import json

from django.contrib.auth.models import User
from django.db import models

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project


class Lexicon(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    description = models.CharField(max_length=MAX_DESC_LEN)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    positives_used = models.TextField(default=json.dumps([]))
    negatives_used = models.TextField(default=json.dumps([]))
    positives_unused = models.TextField(default=json.dumps([]))
    negatives_unused = models.TextField(default=json.dumps([]))


    def __str__(self):
        return self.description
