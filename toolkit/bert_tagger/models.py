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
    split_ratio = models.FloatField(default=choices.DEFAULT_TRAINING_SPLIT)
    num_examples = models.TextField(default=json.dumps({}), null=True)

    # BERT params
    num_epochs = models.IntegerField(default=choices.DEFAULT_NUM_EPOCHS)
    split_ratio = models.FloatField(default=choices.DEFAULT_TRAINING_SPLIT)
    maximum_sample_size = models.IntegerField(default=choices.DEFAULT_MAX_SAMPLE_SIZE)
    learning_rate = models.FloatField(default=choices.DEFAULT_LEARNING_RATE)
    eps = models.FloatField(default=choices.DEFAULT_EPS)
    max_length = models.IntegerField(default=choices.DEFAULT_MAX_LENGTH, min_value=1, max_value=512)
    batch_size = models.IntegerField(default=choices.DEFAULT_BATCH_SIZE)
    bert_model = models.TextField(default=choices.DEFAULT_BERT_MODEL)

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
        with transaction.atomic():
            with zipfile.ZipFile(zip_file, 'r') as archive:
                json_string = archive.read(BertTagger.MODEL_JSON_NAME).decode()
                bert_tagger_json = json.loads(json_string)

                indices = bert_tagger_json.pop("indices")

                bert_tagger_model = BertTagger(**bert_tagger_json)

                bert_tagger_model.task = Task.objects.create(berttagger=bert_tagger_model, status=Task.STATUS_COMPLETED)
                bert_tagger_model.author = User.objects.get(id=request.user.id)
                bert_tagger_model.project = Project.objects.get(id=pk)

                bert_tagger_model.save()

                for index in indices:
                    index_model, is_created = Index.objects.get_or_create(name=index)
                    bert_tagger_model.indices.add(index_model)

                full_model_path, relative_model_path = bert_tagger_model.generate_name(BertTagger.MODEL_TYPE)
                with open(full_model_path, "wb") as fp:
                    path = pathlib.Path(bert_tagger_json["model"]).name
                    fp.write(archive.read(path))
                    bert_tagger_model.model.name = relative_model_path

                plot_name = pathlib.Path(bert_tagger_json["plot"])
                path = plot_name.name
                bert_tagger_model.plot.save(f'{secrets.token_hex(15)}.png', io.BytesIO(archive.read(path)))

                bert_tagger_model.save()
                return bert_tagger_model.id


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


    def generate_name(self, name: str = "bert_tagger"):
        """
        Do not change this carelessly as import/export functionality depends on this.
        Returns full and relative filepaths for the intended models.
        Args:
            name: Name for the model to distinguish itself from others in the same directory.

        Returns: Full and relative file paths, full for saving the model object and relative for actual DB storage.
        """
        model_file_name = f'{name}_{str(self.pk)}_{secrets.token_hex(10)}'
        full_path = pathlib.Path(BASE_DIR) / RELATIVE_MODELS_PATH / self.MODEL_TYPE/ model_file_name
        relative_path = pathlib.Path(RELATIVE_MODELS_PATH) / self.MODEL_TYPE / model_file_name
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
