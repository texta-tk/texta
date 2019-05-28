from django.contrib.auth.models import User
from django.db import models

from toolkit.tagger.models import Tagger
from toolkit.core.project.models import Project

MAX_STR_LEN = 100

class HybridTagger(models.Model):
    description = models.CharField(max_length=MAX_STR_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)

    fact_name = models.CharField(max_length=MAX_STR_LEN)
    minimum_sample_size = models.IntegerField(default=50)

    taggers = models.ManyToManyField(Tagger, default=None)

    def __str__(self):
        return self.fact_name