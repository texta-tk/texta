from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.timezone import now
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


class Task(models.Model):
    STATUS_CREATED = 'created'
    STATUS_QUEUED = 'queued'
    STATUS_RUNNING = 'running'
    STATUS_UPDATING = 'updating'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELED = 'canceled'
    STATUS_FAILED = 'failed'

    id = models.AutoField(primary_key=True)
    status = models.CharField(max_length=MAX_STR_LEN)
    progress = models.FloatField(default=0.0)
    step = models.CharField(max_length=MAX_STR_LEN, default='')
    time_started = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(null=True, blank=True, default=None)
    time_completed = models.DateTimeField(null=True, blank=True, default=None)

    def update_status(self, status, set_time_completed=False):
        self.status = status
        self.last_update = now()
        if set_time_completed:
            self.time_completed = now()
        self.save()

    def update_progress(self, progress, step):
        self.progress = progress
        self.step = step
        self.last_update = now()
        self.save()
