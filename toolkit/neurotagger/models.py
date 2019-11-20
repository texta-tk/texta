import json
import sys
from django.db import models
from django.contrib.auth.models import User
from django.db.models import signals

from . import choices
from toolkit.constants import get_field_choices
from toolkit.constants import MAX_DESC_LEN
from toolkit.core.task.models import Task
from toolkit.core.project.models import Project
from toolkit.embedding.models import Embedding


# Create your models here.
class Neurotagger(models.Model):
    MODEL_TYPE = 'neurotagger'

    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)

    fields = models.TextField(default=json.dumps([]))
    # The fact name from which to get value and generate classes/queries from
    fact_name = models.CharField(max_length=MAX_DESC_LEN, blank=True)
    # Fact values/class names that come from the given fact name
    fact_values = models.TextField(blank=True)
    # Queries that will be generated from the given fact name
    queries = models.TextField(default=json.dumps([]))

    # The neural network model architecture
    model_architecture = models.CharField(choices=choices.model_arch_choices, max_length=10)
    # The sequence length every input document will be cropped to, in order to save gpu memory and training speed
    seq_len = models.IntegerField(default=choices.DEFAULT_SEQ_LEN)
    # The number of words that will be used in the vocabulary of the model
    vocab_size = models.IntegerField(default=choices.DEFAULT_VOCAB_SIZE)
    # Number of training passes through the data
    num_epochs = models.IntegerField(default=choices.DEFAULT_NUM_EPOCHS)
    # The % of data that will be used for validating instead of training
    validation_split = models.FloatField(default=choices.DEFAULT_VALIDATION_SPLIT)

    negative_multiplier = models.FloatField(default=choices.DEFAULT_NEGATIVE_MULTIPLIER, blank=True)
    score_threshold = models.FloatField(default=choices.DEFAULT_SCORE_THRESHOLD, blank=True)
    maximum_sample_size = models.IntegerField(default=choices.DEFAULT_MAX_SAMPLE_SIZE, blank=True)
    # Number of minimum documents that a fact value needs to have before its used as a class
    min_fact_doc_count = models.IntegerField(default=choices.DEFAULT_MIN_FACT_DOC_COUNT, blank=True)
    # Number of maximum documents that when a fact has, it will not be used as a class
    max_fact_doc_count = models.IntegerField(blank=True, null=True)

    embedding = models.ForeignKey(Embedding, on_delete=models.SET_NULL, null=True, default=None)

    # RESULTS
    validation_accuracy = models.FloatField(default=None, null=True)
    training_accuracy = models.FloatField(default=None, null=True)
    training_loss = models.FloatField(default=None, null=True)
    validation_loss = models.FloatField(default=None, null=True)
    classification_report = models.TextField(blank=True)

    location = models.TextField()
    plot = models.FileField(upload_to='data/media', null=True, verbose_name='')
    # For extra info, such as the classification report, confusion matrix, model json, etc
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

            # FOR ASYNC SCROLLING WITH CELERY CHORD, SEE ISSUE https://git.texta.ee/texta/texta-rest/issues/66
            # Due to Neurotagger using chord, it has separate logic for calling out celery task and handling tests
            # if not 'test' in sys.argv:
            #     neurotagger_train_handler.apply_async(args=(instance.pk,))
            # else:
            #     neurotagger_train_handler(instance.pk, testing=True).apply()

            # TEMPORARILY SCROLL SYNCHRONOUSLY ISNTEAD            
            from toolkit.helper_functions import apply_celery_task
            apply_celery_task(neurotagger_train_handler, instance.pk)

signals.post_save.connect(Neurotagger.train_neurotagger_model, sender=Neurotagger)
