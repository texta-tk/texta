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
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.evaluator import choices
from toolkit.model_constants import CommonModelMixin, FavoriteModelMixin


class Evaluator(CommonModelMixin, FavoriteModelMixin):
    MODEL_TYPE = "evaluator"
    MODEL_JSON_NAME = "model.json"

    indices = models.ManyToManyField(Index, default=None)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))

    true_fact = models.CharField(max_length=MAX_DESC_LEN, null=False)
    predicted_fact = models.CharField(max_length=MAX_DESC_LEN, null=False)
    true_fact_value = models.CharField(default=None, max_length=MAX_DESC_LEN, null=True)
    predicted_fact_value = models.CharField(default=None, max_length=MAX_DESC_LEN, null=True)

    average_function = models.CharField(null=False, max_length=MAX_DESC_LEN)
    add_individual_results = models.BooleanField(default=choices.DEFAULT_ADD_INDIVIDUAL_RESULTS, null=True)

    accuracy = models.FloatField(default=None, null=True)
    precision = models.FloatField(default=None, null=True)
    recall = models.FloatField(default=None, null=True)
    f1_score = models.FloatField(default=None, null=True)
    confusion_matrix = models.TextField(default="[]", null=True, blank=True)

    n_true_classes = models.IntegerField(default=None, null=True)
    n_predicted_classes = models.IntegerField(default=None, null=True)
    n_total_classes = models.IntegerField(default=None, null=True)
    document_count = models.IntegerField(default=None, null=True)

    scroll_size = models.IntegerField(default=choices.DEFAULT_SCROLL_SIZE, null=True)
    es_timeout = models.IntegerField(default=choices.DEFAULT_ES_TIMEOUT, null=True)

    individual_results = models.TextField(default=json.dumps({}))

    scores_imprecise = models.BooleanField(default=None, null=True)
    score_after_scroll = models.BooleanField(default=None, null=True)

    classes = models.TextField(default=json.dumps([]))

    evaluation_type = models.CharField(max_length=MAX_DESC_LEN, default=None, null=True)

    token_based = models.BooleanField(default=choices.DEFAULT_TOKEN_BASED, null=True)
    add_misclassified_examples = models.BooleanField(default=choices.DEFAULT_ADD_MISCLASSIFIED_EXAMPLES, null=True)

    misclassified_examples = models.TextField(default="{}")
    field = models.CharField(max_length=MAX_DESC_LEN, default="", null=True)

    plot = models.FileField(upload_to="data/media", null=True, verbose_name="")


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]


    def to_json(self) -> dict:
        serialized = serializers.serialize("json", [self])
        json_obj = json.loads(serialized)[0]["fields"]
        json_obj.pop("project", None)
        json_obj.pop("author", None)
        json_obj.pop("tasks", [])
        json_obj.pop("favorited_users", None)
        return json_obj


    @staticmethod
    def import_resources(zip_file, request, pk) -> int:
        with transaction.atomic():
            with zipfile.ZipFile(zip_file, "r") as archive:
                json_string = archive.read(Evaluator.MODEL_JSON_NAME).decode()
                evaluator_json = json.loads(json_string)

                indices = evaluator_json.pop("indices", [])
                evaluator_json.pop("favorited_users", None)

                evaluator_model = Evaluator(**evaluator_json)

                new_task = Task.objects.create(evaluator=evaluator_model, status=Task.STATUS_COMPLETED, task_type=Task.TYPE_APPLY)
                evaluator_model.author = User.objects.get(id=request.user.id)
                evaluator_model.project = Project.objects.get(id=pk)

                evaluator_model.save()

                evaluator_model.tasks.add(new_task)

                for index in indices:
                    index_model, is_created = Index.objects.get_or_create(name=index)
                    evaluator_model.indices.add(index_model)

                plot_name = pathlib.Path(evaluator_json["plot"])
                path = plot_name.name
                evaluator_model.plot.save(f"{secrets.token_hex(15)}.png", io.BytesIO(archive.read(path)))

                evaluator_model.save()
                return evaluator_model.id


    def export_resources(self) -> HttpResponse:
        with tempfile.SpooledTemporaryFile(encoding="utf8") as tmp:
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as archive:
                # Write model object to zip as json
                model_json = self.to_json()
                model_json = json.dumps(model_json).encode("utf8")
                archive.writestr(self.MODEL_JSON_NAME, model_json)

                for file_path in self.get_resource_paths().values():
                    path = pathlib.Path(file_path)
                    archive.write(file_path, arcname=str(path.name))

            tmp.seek(0)
            return tmp.read()


    def get_resource_paths(self):
        return {"plot": self.plot.path}


    def __str__(self):
        return "{0} - {1}".format(self.pk, self.description)


@receiver(models.signals.post_delete, sender=Evaluator)
def auto_delete_file_on_delete(sender, instance: Evaluator, **kwargs):
    """
    Delete resources on the file-system upon evaluator deletion.
    """
    if instance.plot:
        if os.path.isfile(instance.plot.path):
            os.remove(instance.plot.path)
