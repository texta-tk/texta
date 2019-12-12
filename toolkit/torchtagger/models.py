import json
import sys
from django.db import models
from django.contrib.auth.models import User
from django.db.models import signals
from django.dispatch import receiver

from toolkit.torchtagger import choices
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
    label_index = models.TextField(default=json.dumps({}))
    epoch_reports = models.TextField(default=json.dumps([]))
    accuracy = models.FloatField(default=None, null=True)
    training_loss = models.FloatField(default=None, null=True)
    precision = models.FloatField(default=None, null=True)
    recall = models.FloatField(default=None, null=True)
    f1_score = models.FloatField(default=None, null=True)
    model = models.FileField(null=True, verbose_name='', default=None)
    text_field = models.FileField(null=True, verbose_name='', default=None)
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


@receiver(models.signals.post_save, sender=TorchTagger)
def train_torchtagger_model(sender, instance: TorchTagger, created, **kwargs):
    TorchTagger.train_torchtagger_model(sender, instance, created, **kwargs)


@receiver(models.signals.post_delete, sender=TorchTagger)
def auto_delete_torchtagger_on_delete(sender, instance: Embedding, **kwargs):
    """
    Delete resources on the file-system upon TorchTagger deletion.
    Triggered on individual model object and queryset TorchTagger deletion.
    """
    if instance.model:
        if os.path.isfile(instance.model.path):
            os.remove(instance.model.path)

    if instance.text_field:
        if os.path.isfile(instance.text_field.path):
            os.remove(instance.text_field.path)
