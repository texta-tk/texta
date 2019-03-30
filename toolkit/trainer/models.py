import json
from django.utils.timezone import now
from django.db.models import signals
from django.dispatch import receiver
from django.db import models
from django.contrib.auth.models import User
from multiselectfield import MultiSelectField

from toolkit.trainer.choices import get_field_choices
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.core.models import Project

MAX_INT_LEN = 10
MAX_STR_LEN = 100


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
    progress_message = models.CharField(max_length=MAX_STR_LEN, default='')
    time_started = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(null=True, blank=True, default=None)
    time_completed = models.DateTimeField(null=True, blank=True, default=None)


    def update_status(self, status, set_time_completed=False):
        self.status = status
        self.last_update = now()
        if set_time_completed:
            self.time_completed = now()
        self.save()


    def update_progress(self, progress, progress_message):
        self.progress = progress
        self.progress_message = progress_message
        self.last_update = now()
        self.save()


class Embedding(models.Model):
    id = models.AutoField(primary_key=True)
    description = models.CharField(max_length=MAX_STR_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    query = models.TextField(default=json.dumps(ElasticSearcher().query))
    fields = MultiSelectField(max_length=MAX_STR_LEN*100)

    num_dimensions = models.IntegerField(default=100)
    max_vocab = models.IntegerField(default=0)
    min_freq = models.IntegerField(default=10)
    vocab_size = models.IntegerField(default=0)

    location = models.TextField(default=None, null=True)
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.description
    
    @classmethod
    def start_training_task(cls, sender, instance, created, **kwargs):
        if created:
            new_task = Task.objects.create(embedding=instance, status='created')
            instance.task = new_task
            instance.save()
            from toolkit.trainer.tasks import train_embedding
            train_embedding.apply_async(args=(instance.pk,))

signals.post_save.connect(Embedding.start_training_task, sender=Embedding)


class Tagger(models.Model):
    id = models.AutoField(primary_key=True)
    description = models.CharField(max_length=MAX_STR_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    query = models.TextField(default=ElasticSearcher().query)
    fields = MultiSelectField(choices=get_field_choices(), default=None)

    vectorizer = models.CharField(max_length=MAX_STR_LEN)
    classifier = models.CharField(max_length=MAX_STR_LEN)
    negative_multiplier = models.FloatField(default=0.0)
    maximum_sample_size = models.IntegerField(default=10000)
    score_threshold = models.FloatField(default=0.0)

    location = models.TextField()
    task = models.OneToOneField(Task, on_delete=models.CASCADE)

    def __str__(self):
        return self.description


class Extractor(models.Model):
    pass

