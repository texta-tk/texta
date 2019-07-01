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

from multiselectfield import MultiSelectField


# Create your models here.
class Neurotagger(models.Model):
    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    queries = models.TextField(default=json.dumps([EMPTY_QUERY]))
    fields = MultiSelectField(choices=get_field_choices())

    model_architecture = models.IntegerField()
    seq_len = models.IntegerField(default=choices.DEFAULT_SEQ_LEN)
    vocab_size = models.IntegerField(default=choices.DEFAULT_VOCAB_SIZE)
    num_epochs = models.IntegerField(default=choices.DEFAULT_NUM_EPOCHS)
    validation_split = models.FloatField(default=choices.DEFAULT_VALIDATION_SPLIT)

    negative_multiplier = models.FloatField(default=choices.DEFAULT_NEGATIVE_MULTIPLIER, blank=True)
    maximum_sample_size = models.IntegerField(default=choices.DEFAULT_MAX_SAMPLE_SIZE, blank=True)
    score_threshold = models.FloatField(default=choices.DEFAULT_SCORE_THRESHOLD, blank=True)
    embedding = models.ForeignKey(Embedding, on_delete=models.SET_NULL, null=True, default=None)
    
    accuracy = models.FloatField(default=None, null=True)
    loss = models.FloatField(default=None, null=True)
    f1_score = models.FloatField(default=None, null=True)
    location = models.TextField()
    plot = models.FileField(upload_to='media', null=True, verbose_name='')
    
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return '{0} - {1}'.format(self.pk, self.description)

    @classmethod
    def train_neurotagger_model(cls, sender, instance, created, **kwargs):
        if created:
            new_task = Task.objects.create(neurotagger=instance, status='created')
            instance.task = new_task
            instance.save()
            from toolkit.neurotagger.tasks import train_neurotagger

            # If not running tests via python manage.py test
            if not 'test' in sys.argv:
                train_neurotagger.apply_async(args=(instance.pk,))
            else: 
                train_neurotagger(instance.pk)

signals.post_save.connect(Neurotagger.train_neurotagger_model, sender=Neurotagger)
