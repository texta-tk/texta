import sys
import json
from django.db.models import signals
from django.dispatch import receiver
from django.db import models
from django.contrib.auth.models import User
from multiselectfield import MultiSelectField

from toolkit.constants import get_field_choices
from toolkit.core.project.models import Project
from toolkit.core.lexicon.models import Lexicon
from toolkit.core.task.models import Task
from toolkit.embedding.models import Embedding
from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.constants import MAX_DESC_LEN
from toolkit.tagger.choices import (
    DEFAULT_NEGATIVE_MULTIPLIER,
    DEFAULT_MAX_SAMPLE_SIZE,
    DEFAULT_MIN_SAMPLE_SIZE,
    DEFAULT_CLASSIFIER,
    DEFAULT_FEATURE_SELECTOR,
    DEFAULT_VECTORIZER
)
from toolkit.helper_functions import apply_celery_task


class Tagger(models.Model):
    MODEL_TYPE = 'tagger'

    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    fields = models.TextField(default=json.dumps([]))
    embedding = models.ForeignKey(Embedding, on_delete=models.SET_NULL, null=True, default=None)
    stop_words = models.TextField(default='[]')
    vectorizer = models.CharField(default=DEFAULT_VECTORIZER, max_length=MAX_DESC_LEN)
    classifier = models.CharField(default=DEFAULT_CLASSIFIER, max_length=MAX_DESC_LEN)
    negative_multiplier = models.FloatField(default=DEFAULT_NEGATIVE_MULTIPLIER, blank=True)
    maximum_sample_size = models.IntegerField(default=DEFAULT_MAX_SAMPLE_SIZE, blank=True)
    score_threshold = models.FloatField(default=0.0, blank=True)

    precision = models.FloatField(default=None, null=True)
    recall = models.FloatField(default=None, null=True)
    f1_score = models.FloatField(default=None, null=True)
    num_features = models.IntegerField(default=None, null=True)
    location = models.TextField()
    plot = models.FileField(upload_to='data/media', null=True, verbose_name='')
    
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return '{0} - {1}'.format(self.pk, self.description)

    @classmethod
    def train_tagger_model(cls, sender, instance, created, **kwargs):
        if created:
            new_task = Task.objects.create(tagger=instance, status='created')
            instance.task = new_task
            instance.save()
            from toolkit.tagger.tasks import train_tagger

            apply_celery_task(train_tagger, instance.pk)

signals.post_save.connect(Tagger.train_tagger_model, sender=Tagger)


class TaggerGroup(models.Model):
    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)

    fact_name = models.CharField(max_length=MAX_DESC_LEN)
    minimum_sample_size = models.IntegerField(default=DEFAULT_MIN_SAMPLE_SIZE)

    taggers = models.ManyToManyField(Tagger, default=None)

    def __str__(self):
        return self.fact_name
