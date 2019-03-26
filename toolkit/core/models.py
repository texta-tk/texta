from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from toolkit.core.elastic import Elastic

import uuid
import json

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
    query = models.TextField()

    def __str__(self):
        return self.query


class Model(models.Model):
    STATUS_CREATED = 'created'
    STATUS_QUEUED = 'queued'
    STATUS_RUNNING = 'running'
    STATUS_UPDATING = 'updating'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELED = 'canceled'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = (
        (STATUS_CREATED, 'Created'),
        (STATUS_QUEUED, 'Queued'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_UPDATING, 'Updating'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELED, 'Canceled'),
        (STATUS_FAILED, 'Failed'),
    )

    id = models.AutoField(primary_key=True)
    unique_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    description = models.CharField(max_length=MAX_STR_LEN)
    model_type = models.CharField(max_length=MAX_STR_LEN)
    parameters = models.TextField(default=None)
    result = models.TextField(default=None)
    status = models.CharField(choices=STATUS_CHOICES, max_length=MAX_STR_LEN)
    progress = models.FloatField(default=0.0)
    progress_message = models.CharField(max_length=MAX_STR_LEN, default='')
    time_started = models.DateTimeField()
    last_update = models.DateTimeField(null=True, blank=True, default=None)
    time_completed = models.DateTimeField(null=True, blank=True, default=None)


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
