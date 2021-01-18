import io
import json
import os
import pathlib
import secrets
import tempfile
import zipfile

from django.contrib.auth.models import User
from django.core import serializers
from django.db import models, transaction
from django.dispatch import receiver
from django.http import HttpResponse

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.models import Index
from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.settings import BASE_DIR, CELERY_LONG_TERM_TASK_QUEUE, RELATIVE_MODELS_PATH
from toolkit.bert_tagger import choices


class BertTagger(models.Model):
    MODEL_TYPE = 'bert_tagger'
    MODEL_JSON_NAME = "model.json"

    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    fields = models.TextField(default=json.dumps([]))
    indices = models.ManyToManyField(Index, default=None)

    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    fact_name = models.CharField(max_length=MAX_DESC_LEN, null=True)
    minimum_sample_size = models.IntegerField(default=choices.DEFAULT_MIN_SAMPLE_SIZE)
    negative_multiplier = models.FloatField(default=choices.DEFAULT_NEGATIVE_MULTIPLIER)
    split_ratio = models.FloatField(default=choices.DEFAULT_VALIDATION_SPLIT)

    # BERT PARAMS TO ADD:
    # split_ratio = validation_ratio
    # batch_size NB! autoadjust with max_length
    # max_length (max 512 or something)
    # bert model!!! (How to choose?)
    # learning_rate
    # eps

    num_epochs = models.IntegerField(default=choices.DEFAULT_NUM_EPOCHS)
    validation_ratio = models.FloatField(default=choices.DEFAULT_VALIDATION_SPLIT)
    maximum_sample_size = models.IntegerField(default=choices.DEFAULT_MAX_SAMPLE_SIZE)
    learning_rate = models.FloatField(default=choices.DEFAULT_LEARNING_RATE)
    eps = models.FloatField(default=choices.DEFAULT_EPS)
    max_length = models.IntegerField(default=choices.DEFAULT_MAX_LENGTH)
    batch_size = models.IntegerField(default=choices.DEFAULT_BATCH_SIZE)
    bert_model = models.TextField(default=choices.DEFAULT_BERT_MODEL)


    # RESULTS

    # validation loss
    # validation time
    # training time
    label_index = models.TextField(default=json.dumps({}))
    epoch_reports = models.TextField(default=json.dumps([]))
    accuracy = models.FloatField(default=None, null=True)
    training_loss = models.FloatField(default=None, null=True)
    validation_loss = models.FloatField(default=None, null=True)
    precision = models.FloatField(default=None, null=True)
    recall = models.FloatField(default=None, null=True)
    f1_score = models.FloatField(default=None, null=True)
    model = models.FileField(null=True, verbose_name='', default=None)
    plot = models.FileField(upload_to='data/media', null=True, verbose_name='')

    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]


    def to_json(self) -> dict:
        serialized = serializers.serialize('json', [self])
        json_obj = json.loads(serialized)[0]["fields"]
        json_obj.pop("project")
        json_obj.pop("author")
        json_obj.pop("task")
        return json_obj


    @staticmethod
    def import_resources(zip_file, request, pk) -> int:
        # TODO: see torch_tagger
        pass

    def export_resources(self) -> HttpResponse:
        # TODO: see torch_tagger
        pass

    def generate_name(self, name: str = "bert_tagger"):
        """
        Do not change this carelessly as import/export functionality depends on this.
        Returns full and relative filepaths for the intended models.
        Args:
            name: Name for the model to distinguish itself from others in the same directory.

        Returns: Full and relative file paths, full for saving the model object and relative for actual DB storage.
        """
        model_file_name = f'{name}_{str(self.pk)}_{secrets.token_hex(10)}'
        full_path = pathlib.Path(BASE_DIR) / RELATIVE_MODELS_PATH / "bert_tagger" / model_file_name
        relative_path = pathlib.Path(RELATIVE_MODELS_PATH) / "bert_tagger" / model_file_name
        return str(full_path), str(relative_path)


    def __str__(self):
        return '{0} - {1}'.format(self.pk, self.description)


    def train(self):
        new_task = Task.objects.create(berttagger=self, status='created')
        self.task = new_task
        self.save()
        from toolkit.bert_tagger.tasks import train_bert_tagger
        train_bert_tagger.apply_async(args=(self.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE)


    def get_resource_paths(self):
        return {"plot": self.plot.path, "model": self.model.path}


@receiver(models.signals.post_delete, sender = BertTagger)
def auto_delete_bert_tagger_on_delete(sender, instance: BertTagger, **kwargs):
    """
    Delete resources on the file-system upon BertTagger deletion.
    Triggered on individual model object and queryset BertTagger deletion.
    """
    if instance.model:
        if os.path.isfile(instance.model.path):
            os.remove(instance.model.path)

    if instance.plot:
        if os.path.isfile(instance.plot.path):
            os.remove(instance.plot.path)
