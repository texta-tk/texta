from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from texta.settings import DATASET_ACCESS_DEFAULT

MAX_INT_LEN = 10
MAX_STR_LEN = 100


class Dataset(models.Model):
    id = models.AutoField(primary_key=True)
    index = models.CharField(max_length=MAX_STR_LEN)
    mapping = models.CharField(max_length=MAX_STR_LEN)
    author = models.ForeignKey(User, on_delete=models.CASCADE)  # NEW PY REQUIREMENT
    daterange = models.TextField()
    access = models.CharField(default=DATASET_ACCESS_DEFAULT, max_length=7)

    def __str__(self):
        return 'Index: {0} by user {1}'.format(self.index, self.author.username)


class ScriptProject(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=MAX_STR_LEN)
    desc = models.TextField()
    entrance_point = models.CharField(max_length=MAX_STR_LEN)
    arguments = models.TextField()
    last_modified = models.DateTimeField()

    def save(self, *args, **kwargs):
        """From http://stackoverflow.com/questions/1737017/django-auto-now-and-auto-now-add - update last_modified on save """
        self.last_modified = timezone.now()
        return super(ScriptProject, self).save(*args, **kwargs)
