from django.db.models import signals
from django.dispatch import receiver
from django.db import models
from django.contrib.auth.models import User
from multiselectfield import MultiSelectField

from toolkit.elastic.utils import get_field_choices
from toolkit.elastic.elastic import Elastic
from toolkit.core.models import Project

MAX_INT_LEN = 10
MAX_STR_LEN = 100


class Task(models.Model):
    id = models.AutoField(primary_key=True)
    task_type = models.CharField(max_length=MAX_STR_LEN)
    status = models.CharField(max_length=MAX_STR_LEN)
    progress = models.FloatField(default=0.0)
    progress_message = models.CharField(max_length=MAX_STR_LEN, default='')
    time_started = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(null=True, blank=True, default=None)
    time_completed = models.DateTimeField(null=True, blank=True, default=None)


class Embedding(models.Model):
    id = models.AutoField(primary_key=True)
    description = models.CharField(max_length=MAX_STR_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    query = models.TextField(default=Elastic().empty_query)
    index = MultiSelectField()
    fields = MultiSelectField()

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
            Task.objects.create(embedding=instance, status='created', task_type='embedding')
            from toolkit.trainers.tasks import train_embedding
            train_embedding.apply_async(args=(instance.pk,))

signals.post_save.connect(Embedding.start_training_task, sender=Embedding)


class Tagger(models.Model):
    id = models.AutoField(primary_key=True)
    description = models.CharField(max_length=MAX_STR_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    query = models.TextField(default=Elastic().empty_query)
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

