import json
import sys
from django.db import models
from django.contrib.auth.models import User
from django.db.models import signals

from . import choices
from toolkit.constants import get_field_choices
from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.constants import MAX_DESC_LEN
from toolkit.core.task.models import Task
from toolkit.core.project.models import Project
from toolkit.embedding.models import Embedding


# Create your models here.
class Neurotagger(models.Model):
    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)

    fields = models.TextField(default=json.dumps([]))
    queries = models.TextField(default=json.dumps([]))
    fact_name = models.CharField(max_length=MAX_DESC_LEN, blank=True)
    fact_values = models.TextField(blank=True)

    model_architecture = models.CharField(choices=choices.model_arch_choices, max_length=10)
    seq_len = models.IntegerField(default=choices.DEFAULT_SEQ_LEN)
    vocab_size = models.IntegerField(default=choices.DEFAULT_VOCAB_SIZE)
    num_epochs = models.IntegerField(default=choices.DEFAULT_NUM_EPOCHS)
    validation_split = models.FloatField(default=choices.DEFAULT_VALIDATION_SPLIT)

    negative_multiplier = models.FloatField(default=choices.DEFAULT_NEGATIVE_MULTIPLIER, blank=True)
    maximum_sample_size = models.IntegerField(default=choices.DEFAULT_MAX_SAMPLE_SIZE, blank=True)
    min_fact_doc_count = models.IntegerField(default=choices.DEFAULT_MIN_FACT_DOC_COUNT, blank=True)
    max_fact_doc_count = models.IntegerField(blank=True, null=True)
    score_threshold = models.FloatField(default=choices.DEFAULT_SCORE_THRESHOLD, blank=True)
    embedding = models.ForeignKey(Embedding, on_delete=models.SET_NULL, null=True, default=None)

    # RESULTS
    validation_accuracy = models.FloatField(default=None, null=True)
    training_accuracy = models.FloatField(default=None, null=True)
    training_loss = models.FloatField(default=None, null=True)
    validation_loss = models.FloatField(default=None, null=True)
    classification_report = models.TextField(blank=True)

    location = models.TextField()
    model_plot = models.FileField(upload_to='media', null=True, verbose_name='')
    plot = models.FileField(upload_to='media', null=True, verbose_name='')
    result_json = models.TextField(blank=True)
    
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return '{0} - {1}'.format(self.pk, self.description)

    @classmethod
    def train_neurotagger_model(cls, sender, instance, created, **kwargs):
        if created:
            new_task = Task.objects.create(neurotagger=instance, status='created')
            instance.task = new_task
            instance.save()
            from toolkit.neurotagger.tasks import neurotagger_train_handler

            # If not running tests via python manage.py test
            if not 'test' in sys.argv:
                neurotagger_train_handler.apply_async(args=(instance.pk,))

signals.post_save.connect(Neurotagger.train_neurotagger_model, sender=Neurotagger)