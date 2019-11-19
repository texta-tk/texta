import json
import sys
from django.db import models
from django.contrib.auth.models import User
from django.db.models import signals

from toolkit.torchtagger import choices
#from toolkit.constants import get_field_choices
from toolkit.constants import MAX_DESC_LEN
from toolkit.core.task.models import Task
from toolkit.core.project.models import Project
from toolkit.embedding.models import Embedding
from toolkit.elastic.searcher import EMPTY_QUERY


class TorchTagger(models.Model):
    MODEL_TYPE = 'torchtagger'

    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    fields = models.TextField(default=json.dumps([]))
    embedding = models.ForeignKey(Embedding, on_delete=models.CASCADE, default=None)

    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    fact_name = models.CharField(max_length=MAX_DESC_LEN, null=True)
    minimum_sample_size = models.IntegerField(default=choices.DEFAULT_MIN_SAMPLE_SIZE)

    model_architecture = models.CharField(default=choices.MODEL_CHOICES[0][0], max_length=10)
    #seq_len = models.IntegerField(default=choices.DEFAULT_SEQ_LEN)
    #vocab_size = models.IntegerField(default=choices.DEFAULT_VOCAB_SIZE)
    num_epochs = models.IntegerField(default=choices.DEFAULT_NUM_EPOCHS)
    validation_ratio = models.FloatField(default=choices.DEFAULT_VALIDATION_SPLIT)
    negative_multiplier = models.FloatField(default=choices.DEFAULT_NEGATIVE_MULTIPLIER)
    maximum_sample_size = models.IntegerField(default=choices.DEFAULT_MAX_SAMPLE_SIZE)

    # RESULTS
    epoch_reports = models.TextField(default=json.dumps([]))
    accuracy = models.FloatField(default=None, null=True)
    training_loss = models.FloatField(default=None, null=True)
    precision = models.FloatField(default=None, null=True)
    recall = models.FloatField(default=None, null=True)
    f1_score = models.FloatField(default=None, null=True)
    location = models.TextField()
    plot = models.FileField(upload_to='data/media', null=True, verbose_name='')
    
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return '{0} - {1}'.format(self.pk, self.description)

    @classmethod
    def train_torchtagger_model(cls, sender, instance, created, **kwargs):
        if created:
            new_task = Task.objects.create(torchtagger=instance, status='created')
            instance.task = new_task
            instance.save()
            from toolkit.torchtagger.tasks import torchtagger_train_handler       
            from toolkit.helper_functions import apply_celery_task
            apply_celery_task(torchtagger_train_handler, instance.pk)

signals.post_save.connect(TorchTagger.train_torchtagger_model, sender=TorchTagger)
