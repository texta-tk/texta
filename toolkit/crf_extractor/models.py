import json
import logging
import pathlib
import secrets
import tempfile
import zipfile
from io import BytesIO
from django.core import serializers
from django.contrib.auth.models import User
from django.db import models, transaction
from django.http import HttpResponse
from multiselectfield import MultiSelectField

from texta_crf_extractor.crf_extractor import CRFExtractor as Extractor

from toolkit.embedding.models import Embedding
from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.elastic.tools.searcher import EMPTY_QUERY
from toolkit.settings import (
    BASE_DIR,
    CELERY_LONG_TERM_TASK_QUEUE,
    INFO_LOGGER,
    RELATIVE_MODELS_PATH
)
from .choices import FEATURE_FIELDS_CHOICES, FEATURE_EXTRACTOR_CHOICES


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
    mlp_field = models.CharField(default="text", max_length=MAX_DESC_LEN)
    # these are the parsed feature fields
    feature_fields = MultiSelectField(choices=FEATURE_FIELDS_CHOICES)
    context_feature_fields = MultiSelectField(choices=FEATURE_FIELDS_CHOICES)
    # these are used feature extractors
    feature_extractors = MultiSelectField(choices=FEATURE_EXTRACTOR_CHOICES)
    context_feature_extractors = MultiSelectField(choices=FEATURE_EXTRACTOR_CHOICES)

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
                new_model = CRFExtractor(**model_json)
                new_model.task = Task.objects.create(crfextractor=new_model, status=Task.STATUS_COMPLETED)
                new_model.author = User.objects.get(id=request.user.id)
                new_model.project = Project.objects.get(id=pk)
                new_model.save()  # Save the intermediate results.

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


    def load_extractor(self):
        """Loading model from disc."""
        # load embedding
        if self.embedding:
            embedding = self.embedding.get_embedding()
            embedding.load_django(self.embedding)
        else:
            embedding = False
        # load extractor model
        extractor = Extractor(embedding=embedding)
        loaded = extractor.load_django(self)
        # check if model gets loaded
        if not loaded:
            return None
        return extractor


    def apply_loaded_extractor(self, extractor: Extractor, mlp_document):
        result = extractor.tag(mlp_document)
        return result
