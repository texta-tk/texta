import sys
import json
from django.db.models import signals
from django.dispatch import receiver
from django.db import models
from django.contrib.auth.models import User
from multiselectfield import MultiSelectField

from toolkit.embedding.choices import get_field_choices
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.embedding.models import Embedding
from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.tagger.choices import DEFAULT_NEGATIVE_MULTIPLIER, DEFAULT_MAX_SAMPLE_SIZE, DEFAULT_MIN_SAMPLE_SIZE

MAX_STR_LEN = 100


class Tagger(models.Model):
    description = models.CharField(max_length=MAX_STR_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    fields = MultiSelectField(choices=get_field_choices())
    embedding = models.ForeignKey(Embedding, on_delete=models.SET_NULL, null=True, default=None)

    vectorizer = models.IntegerField(default=0)
    classifier = models.IntegerField(default=0)
    feature_selector = models.IntegerField(default=0)
    negative_multiplier = models.FloatField(default=DEFAULT_NEGATIVE_MULTIPLIER, blank=True)
    maximum_sample_size = models.IntegerField(default=DEFAULT_MAX_SAMPLE_SIZE, blank=True)
    score_threshold = models.FloatField(default=0.0, blank=True)

    precision = models.FloatField(default=None, null=True)
    recall = models.FloatField(default=None, null=True)
    f1_score = models.FloatField(default=None, null=True)
    num_features = models.IntegerField(default=None, null=True)
    location = models.TextField()
    plot = models.FileField(upload_to='media', null=True, verbose_name='')
    
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

            # If not running tests via python manage.py test
            if not 'test' in sys.argv:
                train_tagger.apply_async(args=(instance.pk,))
            else: 
                train_tagger(instance.pk)

signals.post_save.connect(Tagger.train_tagger_model, sender=Tagger)


class TaggerGroup(models.Model):
    description = models.CharField(max_length=MAX_STR_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)

    fact_name = models.CharField(max_length=MAX_STR_LEN)
    minimum_sample_size = models.IntegerField(default=DEFAULT_MIN_SAMPLE_SIZE)

    taggers = models.ManyToManyField(Tagger, default=None)

    def __str__(self):
        return self.fact_name
