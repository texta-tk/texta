from django.contrib.auth.models import User
from django.db import models

from toolkit.tagger.models import Tagger
from toolkit.core.project.models import Project

MAX_STR_LEN = 100

class HybridTagger(models.Model):
    description = models.CharField(max_length=MAX_STR_LEN)
    #project = models.ForeignKey(Project, on_delete=models.CASCADE)
    #author = models.ForeignKey(User, on_delete=models.CASCADE)

    #num_dimensions = models.IntegerField(default=100)
    #max_vocab = models.IntegerField(default=0)
    #min_freq = models.IntegerField(default=10)

    taggers = models.ManyToManyField(Tagger)

    #location = models.TextField(default=None, null=True)
    #task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.description