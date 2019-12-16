import json
import os
import secrets

from django.contrib.auth.models import User
from django.db import models
from django.dispatch import receiver

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.embedding.models import Embedding
from . import choices
from toolkit.multiselectfield import PatchedMultiSelectField as MultiSelectField

# Create your models here.
class Neurotagger(models.Model):
    MODEL_TYPE = 'neurotagger'

    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    indices = MultiSelectField(default=None)
    fields = models.TextField(default=json.dumps([]))
    fact_name = models.CharField(max_length=MAX_DESC_LEN, blank=True, help_text="Fact name from which to get value and generate classes/queries from")
    fact_values = models.TextField(blank=True, help_text="Fact values/class names that come from the given fact name")
    queries = models.TextField(default=json.dumps([]), help_text="Queries that will be generated from the given fact name")
    model_architecture = models.CharField(choices=choices.model_arch_choices, max_length=10, help_text="Neural network model architecture")
    seq_len = models.IntegerField(default=choices.DEFAULT_SEQ_LEN, help_text="Sequence length every input document will be cropped to, in order to save gpu memory and training speed")
    vocab_size = models.IntegerField(default=choices.DEFAULT_VOCAB_SIZE, help_text="Number of words that will be used in the vocabulary of the model")
    num_epochs = models.IntegerField(default=choices.DEFAULT_NUM_EPOCHS, help_text="Number of training passes through the data")
    validation_split = models.FloatField(default=choices.DEFAULT_VALIDATION_SPLIT, help_text="Percentage of data that will be used for validating instead of training")
    negative_multiplier = models.FloatField(default=choices.DEFAULT_NEGATIVE_MULTIPLIER, blank=True)
    score_threshold = models.FloatField(default=choices.DEFAULT_SCORE_THRESHOLD, blank=True)
    maximum_sample_size = models.IntegerField(default=choices.DEFAULT_MAX_SAMPLE_SIZE, blank=True)
    min_fact_doc_count = models.IntegerField(default=choices.DEFAULT_MIN_FACT_DOC_COUNT, blank=True, help_text="Number of minimum documents that a fact value needs to have before its used as a class")
    max_fact_doc_count = models.IntegerField(blank=True, null=True, help_text="Number of maximum documents that when a fact has, it will not be used as a class")
    embedding = models.ForeignKey(Embedding, on_delete=models.SET_NULL, null=True, default=None)

    # RESULTS
    validation_accuracy = models.FloatField(default=None, null=True)
    training_accuracy = models.FloatField(default=None, null=True)
    training_loss = models.FloatField(default=None, null=True)
    validation_loss = models.FloatField(default=None, null=True)
    classification_report = models.TextField(blank=True)

    # File-system resources
    model = models.FileField(null=True, verbose_name='', default=None, max_length=300)
    tokenizer_model = models.FileField(null=True, verbose_name='', default=None, max_length=300)
    tokenizer_vocab = models.FileField(null=True, verbose_name='', default=None, max_length=300)
    plot = models.FileField(upload_to='data/media', null=True, verbose_name='', max_length=300)

    # For extra info, such as the classification report, confusion matrix, model json, etc
    result_json = models.TextField(blank=True)

    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)


    def __str__(self):
        return '{0} - {1}'.format(self.pk, self.description)


    def generate_name(self, name):
        return f'{name}_{self.pk}_{secrets.token_hex(10)}'


    def train(self):
        new_task = Task.objects.create(neurotagger=self, status='created')
        self.task = new_task
        self.save()

        # FOR ASYNC SCROLLING WITH CELERY CHORD, SEE ISSUE https://git.texta.ee/texta/texta-rest/issues/66
        # Due to Neurotagger using chord, it has separate logic for calling out celery task and handling tests
        # if not 'test' in sys.argv:
        #     neurotagger_train_handler.apply_async(args=(instance.pk,))
        # else:
        #     neurotagger_train_handler(instance.pk, testing=True).apply()

        # TEMPORARILY SCROLL SYNCHRONOUSLY INSTEAD
        from toolkit.neurotagger.tasks import neurotagger_train_handler
        from toolkit.helper_functions import apply_celery_task
        apply_celery_task(neurotagger_train_handler, self.pk)


@receiver(models.signals.post_delete, sender=Neurotagger)
def auto_delete_file_on_delete(sender, instance: Neurotagger, **kwargs):
    """
    Delete resources on the file-system upon neurotagger deletion.
    Triggered on individual model object and queryset Neurotagger deletion.
    """
    if instance.plot:
        if os.path.isfile(instance.plot.path):
            os.remove(instance.plot.path)

    if instance.model:
        if os.path.isfile(instance.model.path):
            os.remove(instance.model.path)

    if instance.tokenizer_model:
        if os.path.isfile(instance.tokenizer_model.path):
            os.remove(instance.tokenizer_model.path)

    if instance.tokenizer_vocab:
        if os.path.isfile(instance.tokenizer_vocab.path):
            os.remove(instance.tokenizer_vocab.path)
