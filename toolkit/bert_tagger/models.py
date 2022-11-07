import io
import json
import os
import pathlib
import secrets
import tempfile
import zipfile
from typing import Dict, List, Union

from django.contrib.auth.models import User
from django.core import serializers
from django.db import models, transaction
from django.dispatch import receiver
from django.http import HttpResponse
from texta_bert_tagger.tagger import BertTagger as TextBertTagger
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.bert_tagger import choices
from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.elastic.tools.feedback import Feedback
from toolkit.helper_functions import get_core_setting
from toolkit.model_constants import CommonModelMixin, FavoriteModelMixin, S3ModelMixin
from toolkit.settings import (BASE_DIR, BERT_CACHE_DIR, BERT_FINETUNED_MODEL_DIRECTORY, BERT_PRETRAINED_MODEL_DIRECTORY, CELERY_LONG_TERM_TASK_QUEUE)


class BertTagger(FavoriteModelMixin, CommonModelMixin, S3ModelMixin):
    MODEL_TYPE = 'bert_tagger'
    MODEL_JSON_NAME = "model.json"

    fields = models.TextField(default=json.dumps([]))
    indices = models.ManyToManyField(Index, default=None)

    checkpoint_model = models.ForeignKey("self", null=True, on_delete=models.SET_NULL, default=None)

    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    fact_name = models.CharField(max_length=MAX_DESC_LEN, null=True)
    pos_label = models.CharField(max_length=MAX_DESC_LEN, null=True, default="", blank=True)
    minimum_sample_size = models.IntegerField(default=choices.DEFAULT_MIN_SAMPLE_SIZE)
    negative_multiplier = models.FloatField(default=choices.DEFAULT_NEGATIVE_MULTIPLIER)
    num_examples = models.TextField(default=json.dumps({}), null=True)

    # BERT params
    use_gpu = models.BooleanField(default=True)

    num_epochs = models.IntegerField(default=choices.DEFAULT_NUM_EPOCHS)
    split_ratio = models.FloatField(default=choices.DEFAULT_TRAINING_SPLIT)
    maximum_sample_size = models.IntegerField(default=choices.DEFAULT_MAX_SAMPLE_SIZE)
    learning_rate = models.FloatField(default=choices.DEFAULT_LEARNING_RATE)
    eps = models.FloatField(default=choices.DEFAULT_EPS)
    max_length = models.IntegerField(default=choices.DEFAULT_MAX_LENGTH)
    batch_size = models.IntegerField(default=choices.DEFAULT_BATCH_SIZE)
    bert_model = models.TextField(default=choices.DEFAULT_BERT_MODEL)
    adjusted_batch_size = models.IntegerField(default=choices.DEFAULT_BATCH_SIZE)
    confusion_matrix = models.TextField(default="[]", null=True, blank=True)

    label_index = models.TextField(default=json.dumps({}))
    epoch_reports = models.TextField(default=json.dumps([]))

    accuracy = models.FloatField(default=None, null=True)
    training_loss = models.FloatField(default=None, null=True)
    validation_loss = models.FloatField(default=None, null=True)
    precision = models.FloatField(default=None, null=True)
    recall = models.FloatField(default=None, null=True)
    f1_score = models.FloatField(default=None, null=True)
    classes = models.TextField(default=json.dumps([]))

    balance = models.BooleanField(default=choices.DEFAULT_BALANCE)
    use_sentence_shuffle = models.BooleanField(default=choices.DEFAULT_USE_SENTENCE_SHUFFLE)
    balance_to_max_limit = models.BooleanField(default=choices.DEFAULT_BALANCE_TO_MAX_LIMIT)

    model = models.FileField(null=True, verbose_name='', default=None, max_length=MAX_DESC_LEN)
    plot = models.FileField(upload_to='data/media', null=True, verbose_name='')


    def get_available_or_all_indices(self, indices: List[str] = None) -> List[str]:
        """
        Used in views where the user can select the indices they wish to use.
        Returns a list of index names from the ones that are in the project
        and in the indices parameter or all of the indices if it's None or empty.
        """
        if indices:
            indices = self.indices.filter(name__in=indices, is_open=True)
            if not indices:
                indices = self.project.indices.all()
        else:
            indices = self.indices.all()

        indices = [index.name for index in indices]
        indices = list(set(indices))  # Leave only unique names just in case.
        return indices


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]


    def to_json(self) -> dict:
        serialized = serializers.serialize('json', [self])
        json_obj = json.loads(serialized)[0]["fields"]
        json_obj.pop("project")
        json_obj.pop("author")
        json_obj.pop("tasks")
        return json_obj


    @staticmethod
    def import_resources(zip_file: io.BytesIO, user_pk: int, project_pk: int) -> int:
        with transaction.atomic():
            with zipfile.ZipFile(zip_file, 'r') as archive:
                json_string = archive.read(BertTagger.MODEL_JSON_NAME).decode()
                bert_tagger_json = json.loads(json_string)

                indices = bert_tagger_json.pop("indices")
                bert_tagger_json.pop("favorited_users", None)

                bert_tagger_model = BertTagger(**bert_tagger_json)

                bert_tagger_model.author = User.objects.get(pk=user_pk)
                bert_tagger_model.project = Project.objects.get(pk=project_pk)

                bert_tagger_model.save()

                new_task = Task.objects.create(berttagger=bert_tagger_model, status=Task.STATUS_COMPLETED)
                bert_tagger_model.tasks.add(new_task)

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
        full_path = pathlib.Path(BASE_DIR) / BERT_FINETUNED_MODEL_DIRECTORY / model_file_name
        relative_path = pathlib.Path(BERT_FINETUNED_MODEL_DIRECTORY) / model_file_name
        return str(full_path), str(relative_path)


    def __str__(self):
        return '{0} - {1}'.format(self.pk, self.description)


    def train(self):
        new_task = Task.objects.create(berttagger=self, task_type=Task.TYPE_TRAIN, status=Task.STATUS_CREATED)
        self.save()
        self.tasks.add(new_task)
        from toolkit.bert_tagger.tasks import train_bert_tagger


        queue = CELERY_LONG_TERM_TASK_QUEUE if self.use_gpu is False else get_core_setting("TEXTA_LONG_TERM_GPU_TASK_QUEUE")
        train_bert_tagger.apply_async(args=(self.pk,), queue=queue)


    def get_resource_paths(self):
        return {"plot": self.plot.path, "model": self.model.path}


    def load_tagger(self):
        """Load BERT tagger from disc."""
        # NB! Saving pretrained models must be disabled!
        tagger = TextBertTagger(
            allow_standard_output=choices.DEFAULT_ALLOW_STANDARD_OUTPUT,
            save_pretrained=False,
            pretrained_models_dir=BERT_PRETRAINED_MODEL_DIRECTORY,
            use_gpu=self.use_gpu,
            # logger = logging.getLogger(INFO_LOGGER),
            cache_dir=BERT_CACHE_DIR
        )
        tagger.load(self.model.path)
        # use state dict for binary taggers
        if tagger.config.n_classes == 2:
            tagger.config.use_state_dict = True
        else:
            tagger.config.use_state_dict = False
        return tagger


    def apply_loaded_tagger(self, tagger: TextBertTagger, tagger_input: Union[str, Dict], input_type: str = "text", feedback: bool = False):
        """Apply loaded BERT tagger to doc or text."""
        # tag doc or text
        if input_type == 'doc':
            tagger_result = tagger.tag_doc(tagger_input)
        else:
            tagger_result = tagger.tag_text(tagger_input)
        # reform output
        prediction = {
            'probability': float(tagger_result['probability']),
            'tagger_id': self.id,
            'result': tagger_result['prediction']
        }
        # add optional feedback
        if feedback:
            project_pk = self.project.pk
            feedback_object = Feedback(project_pk, model_object=self)
            feedback_id = feedback_object.store(tagger_input, prediction['result'])
            feedback_url = f'/projects/{project_pk}/bert_taggers/{self.pk}/feedback/'
            prediction['feedback'] = {'id': feedback_id, 'url': feedback_url}
        return prediction


@receiver(models.signals.post_delete, sender=BertTagger)
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
