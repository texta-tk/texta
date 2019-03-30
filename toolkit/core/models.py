from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.contrib.auth.models import User
from multiselectfield import MultiSelectField

from toolkit.elastic.searcher import ElasticSearcher


MAX_INT_LEN = 10
MAX_STR_LEN = 100


class Project(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=MAX_STR_LEN)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    users = models.ManyToManyField(User, related_name="project_users")
    indices = MultiSelectField(default=None)

    def __str__(self):
        return self.title


class Search(models.Model):
    id = models.AutoField(primary_key=True)
    description = models.CharField(max_length=MAX_STR_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    query = models.TextField(default=ElasticSearcher().query)

    def __str__(self):
        return self.query


class Phrase(models.Model):
    id = models.AutoField(primary_key=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    phrase = models.CharField(max_length=MAX_STR_LEN)
   
    def __str__(self):
        return self.phrase


class Lexicon(models.Model):
    id = models.AutoField(primary_key=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    description = models.CharField(max_length=MAX_STR_LEN)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    phrases = models.ManyToManyField(Phrase)

    def __str__(self):
        return self.description

