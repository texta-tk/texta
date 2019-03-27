from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from toolkit.core.elastic import Elastic


MAX_INT_LEN = 10
MAX_STR_LEN = 100


class Dataset(models.Model):
    id = models.AutoField(primary_key=True)
    index = models.CharField(choices=Elastic().get_indices(), max_length=MAX_STR_LEN, blank=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.index


class Project(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=MAX_STR_LEN)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    users = models.ManyToManyField(User, related_name="project_users")
    datasets = models.ManyToManyField(Dataset, blank=True)

    def __str__(self):
        return self.title


class Search(models.Model):
    id = models.AutoField(primary_key=True)
    description = models.CharField(max_length=MAX_STR_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    query = models.TextField(default=Elastic().empty_query)

    def __str__(self):
        return self.query


class Lexicon(models.Model):
    id = models.AutoField(primary_key=True)
    description = models.CharField(max_length=MAX_STR_LEN)
    author = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.description


class Phrase(models.Model):
    id = models.AutoField(primary_key=True)
    lexicon = models.ForeignKey(Lexicon, on_delete=models.CASCADE)
    phrase = models.CharField(max_length=MAX_STR_LEN)
   
    def __str__(self):
        return self.phrase
