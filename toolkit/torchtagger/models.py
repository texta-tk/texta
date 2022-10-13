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
from texta_elastic.searcher import EMPTY_QUERY
from texta_embedding.embedding import W2VEmbedding
from texta_torch_tagger.tagger import TorchTagger as TextTorchTagger

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.elastic.tools.feedback import Feedback
from toolkit.embedding.models import Embedding
from toolkit.model_constants import CommonModelMixin, FavoriteModelMixin
from toolkit.settings import BASE_DIR, CELERY_LONG_TERM_TASK_QUEUE, RELATIVE_MODELS_PATH
from toolkit.torchtagger import choices


class TorchTagger(FavoriteModelMixin, CommonModelMixin):
    MODEL_TYPE = 'torchtagger'
    MODEL_JSON_NAME = "model.json"

    fields = models.TextField(default=json.dumps([]))
    indices = models.ManyToManyField(Index, default=None)

    embedding = models.ForeignKey(Embedding, on_delete=models.CASCADE)

    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    fact_name = models.CharField(max_length=MAX_DESC_LEN, null=True)
    pos_label = models.CharField(max_length=MAX_DESC_LEN, null=True, default="", blank=True)
    minimum_sample_size = models.IntegerField(default=choices.DEFAULT_MIN_SAMPLE_SIZE)

    model_architecture = models.CharField(default=choices.MODEL_CHOICES[0][0], max_length=10)
    # seq_len = models.IntegerField(default=choices.DEFAULT_SEQ_LEN)
    # vocab_size = models.IntegerField(default=choices.DEFAULT_VOCAB_SIZE)
    num_epochs = models.IntegerField(default=choices.DEFAULT_NUM_EPOCHS)
    validation_ratio = models.FloatField(default=choices.DEFAULT_VALIDATION_SPLIT)
    negative_multiplier = models.FloatField(default=choices.DEFAULT_NEGATIVE_MULTIPLIER)
    maximum_sample_size = models.IntegerField(default=choices.DEFAULT_MAX_SAMPLE_SIZE)

    balance = models.BooleanField(default=choices.DEFAULT_BALANCE)
    use_sentence_shuffle = models.BooleanField(default=choices.DEFAULT_USE_SENTENCE_SHUFFLE)
    balance_to_max_limit = models.BooleanField(default=choices.DEFAULT_BALANCE_TO_MAX_LIMIT)

    num_examples = models.TextField(default="{}", null=True)
    classes = models.TextField(default=json.dumps([]))

    # RESULTS
    label_index = models.TextField(default=json.dumps({}))
    epoch_reports = models.TextField(default=json.dumps([]))
    accuracy = models.FloatField(default=None, null=True)
    training_loss = models.FloatField(default=None, null=True)
    precision = models.FloatField(default=None, null=True)
    recall = models.FloatField(default=None, null=True)
    f1_score = models.FloatField(default=None, null=True)
    confusion_matrix = models.TextField(default="[]", null=True, blank=True)
    model = models.FileField(null=True, verbose_name='', default=None)
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
        json_obj.pop("embedding")
        json_obj.pop("project")
        json_obj.pop("author")
        json_obj.pop("tasks")
        return json_obj


    @staticmethod
    def import_resources(zip_file, request, pk) -> int:
        with transaction.atomic():
            with zipfile.ZipFile(zip_file, 'r') as archive:
                json_string = archive.read(TorchTagger.MODEL_JSON_NAME).decode()
                torch_and_embedding = json.loads(json_string)

                torchtagger_json = torch_and_embedding["torchtagger"]
                embedding_json = torch_and_embedding["embedding"]

                embedding_fields = embedding_json["fields"]
                extra_embeddings = embedding_json["embedding_extras"]

                indices = torchtagger_json.pop("indices")
                torchtagger_json.pop("embedding", None)
                torchtagger_json.pop("favorited_users", None)

                torchtagger_model = TorchTagger(**torchtagger_json)

                torchtagger_model.author = User.objects.get(id=request.user.id)
                torchtagger_model.project = Project.objects.get(id=pk)

                embedding_model = Embedding.create_embedding_object(embedding_fields, user_id=request.user.id, project_id=pk)
                embedding_model = Embedding.add_file_to_embedding_object(archive, embedding_model, embedding_fields, "embedding", "embedding_model")
                Embedding.save_embedding_extra_files(archive, embedding_model, embedding_fields, extra_paths=extra_embeddings)
                embedding_model.save()

                torchtagger_model.embedding = embedding_model
                torchtagger_model.save()

                new_task = Task.objects.create(torchtagger=torchtagger_model, status=Task.STATUS_COMPLETED)
                torchtagger_model.tasks.add(new_task)

                for index in indices:
                    index_model, is_created = Index.objects.get_or_create(name=index)
                    torchtagger_model.indices.add(index_model)

                full_model_path, relative_model_path = torchtagger_model.generate_name(TorchTagger.MODEL_TYPE)
                with open(full_model_path, "wb") as fp:
                    path = pathlib.Path(torchtagger_json["model"]).name
                    fp.write(archive.read(path))
                    torchtagger_model.model.name = relative_model_path

                plot_name = pathlib.Path(torchtagger_json["plot"])
                path = plot_name.name
                torchtagger_model.plot.save(f'{secrets.token_hex(15)}.png', io.BytesIO(archive.read(path)))

                torchtagger_model.save()
                return torchtagger_model.id


    def export_resources(self) -> HttpResponse:
        with tempfile.SpooledTemporaryFile(encoding="utf8") as tmp:
            with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as archive:
                # Write model object to zip as json
                model_json = {"torchtagger": self.to_json(), "embedding": self.embedding.to_json()}
                model_json = json.dumps(model_json).encode("utf8")
                archive.writestr(self.MODEL_JSON_NAME, model_json)

                for file_path in self.get_resource_paths().values():
                    path = pathlib.Path(file_path)
                    archive.write(file_path, arcname=str(path.name))

                embedding = self.embedding.to_json()

                embedding_path = pathlib.Path(embedding["fields"]["embedding_model"])
                archive.write(str(embedding_path), arcname=str(embedding_path.name))

                for file in embedding["embedding_extras"]:
                    archive.write(str(file), arcname=str(pathlib.Path(file).name))

            tmp.seek(0)
            return tmp.read()


    def generate_name(self, name: str):
        """
        Do not change this carelessly as import/export functionality depends on this.
        Returns full and relative filepaths for the intended models.
        Args:
            name: Name for the model to distinguish itself from others in the same directory.

        Returns: Full and relative file paths, full for saving the model object and relative for actual DB storage.
        """
        model_file_name = f'{name}_{str(self.pk)}_{secrets.token_hex(10)}'
        full_path = pathlib.Path(BASE_DIR) / RELATIVE_MODELS_PATH / TorchTagger.MODEL_TYPE / model_file_name
        relative_path = pathlib.Path(RELATIVE_MODELS_PATH) / TorchTagger.MODEL_TYPE / model_file_name
        return str(full_path), str(relative_path)


    def __str__(self):
        return '{0} - {1}'.format(self.pk, self.description)


    def train(self):
        new_task = Task.objects.create(torchtagger=self, task_type=Task.TYPE_TRAIN, status=Task.STATUS_CREATED)
        self.save()
        self.tasks.add(new_task)
        from toolkit.torchtagger.tasks import train_torchtagger
        train_torchtagger.apply_async(args=(self.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE)


    def get_resource_paths(self):
        return {"plot": self.plot.path, "model": self.model.path}


    def load_tagger(self):
        """Load tagger from disc."""
        # load embedding & phraser
        embedding = W2VEmbedding()
        embedding.load_django(self.embedding)
        # retrieve model
        tagger = TextTorchTagger(embedding)
        tagger.load_django(self)
        return tagger


    def apply_loaded_tagger(self, tagger: TextTorchTagger, tagger_input: Union[str, Dict], input_type: str = 'text', feedback: bool = False):
        """Predict with loaded tagger."""
        # tag text
        if input_type == 'doc':
            tagger_result = tagger.tag_doc(tagger_input)
        else:
            tagger_result = tagger.tag_text(tagger_input)
        # reform output
        prediction = {
            'probability': tagger_result['probability'],
            'tagger_id': self.pk,
            'result': tagger_result['prediction']
        }
        # add optional feedback
        if feedback:
            project_pk = self.project.pk
            feedback_object = Feedback(project_pk, model_object=self)
            feedback_id = feedback_object.store(tagger_input, prediction['result'])
            feedback_url = f'/projects/{project_pk}/torchtaggers/{self.pk}/feedback/'
            prediction['feedback'] = {'id': feedback_id, 'url': feedback_url}
        return prediction


@receiver(models.signals.post_delete, sender=TorchTagger)
def auto_delete_torchtagger_on_delete(sender, instance: TorchTagger, **kwargs):
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
