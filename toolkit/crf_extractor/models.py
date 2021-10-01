import json
import logging
import pathlib
import secrets
from django.core import serializers
from django.contrib.auth.models import User
from django.db import models, transaction

from texta_crf_extractor.feature_extraction import DEFAULT_LAYERS, DEFAULT_EXTRACTORS

from toolkit.embedding.models import Embedding
from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.elastic.tools.searcher import EMPTY_QUERY
from toolkit.settings import BASE_DIR, CELERY_LONG_TERM_TASK_QUEUE, INFO_LOGGER, RELATIVE_MODELS_PATH


class CRFExtractor(models.Model):
    MODEL_TYPE = 'crf_extractor'
    MODEL_JSON_NAME = "model.json"

    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    indices = models.ManyToManyField(Index, default=None)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))

    labels = models.TextField(default=json.dumps(["GPE", "ORG", "PER", "LOC"]))
    num_iter = models.IntegerField(default=100)
    test_size = models.FloatField(default=0.3)
    c1 = models.FloatField(default=1.0)
    c2 = models.FloatField(default=1.0)
    bias = models.BooleanField(default=True)
    window_size = models.IntegerField(default=2)
    suffix_len = models.TextField(default=json.dumps((2,2)))
    
    # this is the main field used for training
    field = models.CharField(default="text.text", max_length=MAX_DESC_LEN)
    # feature fields
    feature_fields = models.TextField(default=json.dumps(DEFAULT_LAYERS))
    context_feature_fields = models.TextField(default=json.dumps(DEFAULT_LAYERS))
    # feature extractors
    feature_extractors = models.TextField(default=json.dumps(DEFAULT_EXTRACTORS))
    context_feature_extractors = models.TextField(default=json.dumps(DEFAULT_EXTRACTORS))

    embedding = models.ForeignKey(Embedding, on_delete=models.CASCADE, default=None, null=True)

    model = models.FileField(null=True, verbose_name='', default=None, max_length=MAX_DESC_LEN)
    model_size = models.FloatField(default=None, null=True)
    plot = models.FileField(upload_to='data/media', null=True, verbose_name='')
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)


    def generate_name(self, name="crf"):
        """
        Do not change this carelessly as import/export functionality depends on this.
        Returns full and relative filepaths for the intended models.
        Args:
            name: Name for the model to distinguish itself from others in the same directory.

        Returns: Full and relative file paths, full for saving the model object and relative for actual DB storage.
        """
        model_file_name = f'{name}_{str(self.pk)}_{secrets.token_hex(10)}'
        full_path = pathlib.Path(BASE_DIR) / RELATIVE_MODELS_PATH / "tagger" / model_file_name
        relative_path = pathlib.Path(RELATIVE_MODELS_PATH) / "tagger" / model_file_name
        return str(full_path), str(relative_path)


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]


    def to_json(self) -> dict:
        serialized = serializers.serialize('json', [self])
        json_obj = json.loads(serialized)[0]["fields"]
        del json_obj["project"]
        del json_obj["author"]
        del json_obj["task"]
        return json_obj


    def train(self):
        new_task = Task.objects.create(crfextractor=self, status='created')
        self.task = new_task
        self.save()
        from toolkit.crf_extractor.tasks import start_crf_task, train_crf_task, save_crf_results
        logging.getLogger(INFO_LOGGER).info(f"Celery: Starting task for training of CRFExtractor: {self.to_json()}")
        chain = start_crf_task.s() | train_crf_task.s() | save_crf_results.s()
        transaction.on_commit(lambda: chain.apply_async(args=(self.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE))
