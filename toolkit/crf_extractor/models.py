import json
import logging
import os
import pathlib
import secrets
import tempfile
import zipfile
from io import BytesIO

from django.contrib.auth.models import User
from django.core import serializers
from django.db import models, transaction
from django.dispatch import receiver
from django.http import HttpResponse
from multiselectfield import MultiSelectField
from texta_crf_extractor.config import CRFConfig
from texta_crf_extractor.crf_extractor import CRFExtractor as Extractor
from texta_crf_extractor.exceptions import ModelLoadFailedError
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.embedding.models import Embedding
from toolkit.settings import (
    BASE_DIR,
    CELERY_LONG_TERM_TASK_QUEUE,
    INFO_LOGGER,
    RELATIVE_MODELS_PATH
)
from .choices import FEATURE_EXTRACTOR_CHOICES, FEATURE_FIELDS_CHOICES
from ..model_constants import CommonModelMixin, FavoriteModelMixin


class CRFExtractor(FavoriteModelMixin, CommonModelMixin):
    MODEL_TYPE = 'crf_extractor'
    MODEL_JSON_NAME = "model.json"

    indices = models.ManyToManyField(Index, default=None)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    embedding = models.ForeignKey(Embedding, on_delete=models.CASCADE, default=None, null=True)
    # training params
    labels = models.TextField(default=json.dumps(["GPE", "ORG", "PER", "LOC"]))
    num_iter = models.IntegerField(default=100)
    test_size = models.FloatField(default=0.3)
    c_values = models.TextField(default=json.dumps([0.001, 0.1, 0.5]))
    bias = models.BooleanField(default=True)
    window_size = models.IntegerField(default=2)
    suffix_len = models.TextField(default=json.dumps((2, 2)))
    # this is the main field used for training
    mlp_field = models.CharField(default="text", max_length=MAX_DESC_LEN)
    # these are the parsed feature fields
    feature_fields = MultiSelectField(choices=FEATURE_FIELDS_CHOICES)
    context_feature_fields = MultiSelectField(choices=FEATURE_FIELDS_CHOICES)
    # these are used feature extractors
    feature_extractors = MultiSelectField(choices=FEATURE_EXTRACTOR_CHOICES)
    context_feature_extractors = MultiSelectField(choices=FEATURE_EXTRACTOR_CHOICES)
    # training output
    best_c1 = models.FloatField(default=None, null=True)
    best_c2 = models.FloatField(default=None, null=True)
    precision = models.FloatField(default=None, null=True)
    recall = models.FloatField(default=None, null=True)
    f1_score = models.FloatField(default=None, null=True)
    confusion_matrix = models.TextField(default="[]", null=True, blank=True)
    model = models.FileField(null=True, verbose_name='', default=None, max_length=MAX_DESC_LEN)
    model_size = models.FloatField(default=None, null=True)
    plot = models.FileField(upload_to='data/media', null=True, verbose_name='')


    @property
    def mlp_analyzers(self):
        unique_analyzers = set(self.context_feature_fields + self.feature_fields)
        without_text = unique_analyzers - {"text"}  # Since 'text' isn't a legitimate MLP analyzer.
        return list(without_text)


    def __str__(self):
        return f"{self.description} by @{self.author.username}"


    def get_labels(self):
        return json.loads(self.labels)


    def get_query(self):
        return json.loads(self.query)


    def get_suffix_len(self):
        return json.loads(self.suffix_len)


    def get_c_values(self):
        return json.loads(self.c_values)


    def generate_name(self, name="crf"):
        """
        Do not change this carelessly as import/export functionality depends on this.
        Returns full and relative filepaths for the intended models.
        Args:
            name: Name for the model to distinguish itself from others in the same directory.
        Returns: Full and relative file paths, full for saving the model object and relative for actual DB storage.
        """
        model_file_name = f'{name}_{str(self.pk)}_{secrets.token_hex(10)}'
        full_path = pathlib.Path(BASE_DIR) / RELATIVE_MODELS_PATH / "crf" / model_file_name
        relative_path = pathlib.Path(RELATIVE_MODELS_PATH) / "crf" / model_file_name
        return str(full_path), str(relative_path)


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]


    def to_json(self) -> dict:
        serialized = serializers.serialize('json', [self])
        json_obj = json.loads(serialized)[0]["fields"]
        del json_obj["project"]
        del json_obj["author"]
        del json_obj["tasks"]
        return json_obj


    def train(self):
        new_task = Task.objects.create(crfextractor=self, task_type=Task.TYPE_TRAIN, status=Task.STATUS_CREATED)
        self.save()

        self.tasks.add(new_task)
        from toolkit.crf_extractor.tasks import start_crf_task, train_crf_task, save_crf_results
        logging.getLogger(INFO_LOGGER).info(f"Celery: Starting task for training of CRFExtractor: {self.to_json()}")
        chain = start_crf_task.s() | train_crf_task.s() | save_crf_results.s()
        transaction.on_commit(lambda: chain.apply_async(args=(self.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE))


    def export_resources(self) -> HttpResponse:
        with tempfile.SpooledTemporaryFile(encoding="utf8") as tmp:
            with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as archive:
                # Write model object to zip as json
                model_json = self.to_json()
                model_json = json.dumps(model_json).encode("utf8")
                archive.writestr(self.MODEL_JSON_NAME, model_json)
                for file_path in self.get_resource_paths().values():
                    path = pathlib.Path(file_path)
                    archive.write(file_path, arcname=str(path.name))
            tmp.seek(0)
            return tmp.read()


    @staticmethod
    def import_resources(zip_file, request, pk) -> int:
        with transaction.atomic():
            with zipfile.ZipFile(zip_file, 'r') as archive:
                json_string = archive.read(CRFExtractor.MODEL_JSON_NAME).decode()
                model_json = json.loads(json_string)
                indices = model_json.pop("indices")
                model_json.pop("favorited_users", None)
                new_model = CRFExtractor(**model_json)
                new_model.author = User.objects.get(id=request.user.id)
                new_model.project = Project.objects.get(id=pk)
                new_model.save()  # Save the intermediate results.

                new_task = Task.objects.create(crfextractor=new_model, status=Task.STATUS_COMPLETED)
                new_model.tasks.add(new_task)

                for index in indices:
                    index_model, is_created = Index.objects.get_or_create(name=index)
                    new_model.indices.add(index_model)

                full_tagger_path, relative_tagger_path = new_model.generate_name("crf")
                with open(full_tagger_path, "wb") as fp:
                    path = pathlib.Path(model_json["model"]).name
                    fp.write(archive.read(path))
                    new_model.model.name = relative_tagger_path

                plot_name = pathlib.Path(model_json["plot"])
                path = plot_name.name
                new_model.plot.save(f'{secrets.token_hex(15)}.png', BytesIO(archive.read(path)))

                new_model.save()
                return new_model.id


    def get_resource_paths(self):
        """
        Return the full paths of every resource used by this model that lives
        on the filesystem.
        """
        return {"model": self.model.path, "plot": self.plot.path}


    def get_crf_config(self):
        return CRFConfig(
            labels=self.get_labels(),
            num_iter=self.num_iter,
            test_size=self.test_size,
            c_values=self.get_c_values(),
            bias=self.bias,
            window_size=self.window_size,
            suffix_len=self.get_suffix_len(),
            context_feature_layers=list(self.context_feature_fields),
            context_feature_extractors=list(self.context_feature_extractors),
            feature_layers=list(self.feature_fields),
            feature_extractors=list(self.feature_extractors)
        )


    def load_extractor(self):
        """Loading model from disc."""
        try:
            # load embedding
            if self.embedding:
                embedding = self.embedding.get_embedding()
                embedding.load_django(self.embedding)
            else:
                embedding = False
            # load config
            config = self.get_crf_config()
            # load extractor model
            extractor = Extractor(config=config, embedding=embedding)
            loaded = extractor.load_django(self)
            # check if model gets loaded
            if not loaded:
                raise ModelLoadFailedError()
            return extractor
        except Exception as e:
            raise ModelLoadFailedError(str(e))


    def apply_loaded_extractor(self, extractor: Extractor, mlp_document):
        result = extractor.tag(mlp_document)
        return result


@receiver(models.signals.post_delete, sender=CRFExtractor)
def auto_delete_crfextractor_on_delete(sender, instance: CRFExtractor, **kwargs):
    """
    Delete resources on the file-system upon TorchTagger deletion.
    Triggered on individual model object and queryset TorchTagger deletion.
    """
    if instance.model:
        if os.path.isfile(instance.model.path):
            os.remove(instance.model.path)

    if instance.plot:
        if os.path.isfile(instance.plot.path):
            os.remove(instance.plot.path)
