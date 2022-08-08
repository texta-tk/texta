import json
import os
import pathlib
import secrets
import tempfile
import zipfile

from django.contrib.auth.models import User
from django.core import serializers
from django.db import models
from django.dispatch import receiver
from django.http import HttpResponse
from texta_elastic.searcher import EMPTY_QUERY
from texta_embedding.embedding import FastTextEmbedding, W2VEmbedding
from texta_tools.text_processor import TextProcessor

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.choices import DEFAULT_SNOWBALL_LANGUAGE
from toolkit.elastic.index.models import Index
from toolkit.embedding.choices import FASTTEXT_EMBEDDING, W2V_EMBEDDING
from toolkit.model_constants import CommonModelMixin, FavoriteModelMixin
from toolkit.settings import BASE_DIR, CELERY_LONG_TERM_TASK_QUEUE, RELATIVE_MODELS_PATH


class Embedding(FavoriteModelMixin, CommonModelMixin):
    MODEL_JSON_NAME = "model.json"

    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    fields = models.TextField(default=json.dumps([]))
    indices = models.ManyToManyField(Index)
    num_dimensions = models.IntegerField(default=100)
    max_documents = models.IntegerField(default=0)
    min_freq = models.IntegerField(default=10)
    window_size = models.IntegerField(default=1)
    num_epochs = models.IntegerField(default=1)
    stop_words = models.TextField(default=json.dumps([]))
    vocab_size = models.IntegerField(default=0)
    use_phraser = models.BooleanField(default=True)
    snowball_language = models.CharField(default=DEFAULT_SNOWBALL_LANGUAGE, null=True, max_length=MAX_DESC_LEN)
    embedding_type = models.TextField(default=W2V_EMBEDDING)
    embedding_model = models.FileField(null=True, verbose_name='', default=None)


    @staticmethod
    def get_extra_model_file_names(embedding_model_path: str):
        container = []
        embedding_model_path = pathlib.Path(embedding_model_path)
        model_type, pk, model_hash = embedding_model_path.name.split("_")
        for item in embedding_model_path.parent.glob("*{}*".format(model_hash)):
            if item.name != embedding_model_path.name:
                container.append(str(item))
        return container


    @staticmethod
    def save_embedding_extra_files(archive, modified_model_object, old_model_data: dict, extra_paths: list, embedding_field="embedding_model"):
        # Add the extra files from Gensim, they are not stored inside the mode,
        # but need to have the same suffix as the name of the embedding file for Gensim
        # to pick it up.
        old_embedding_path = pathlib.Path(old_model_data[embedding_field]).name
        new_embedding_path = pathlib.Path(modified_model_object.embedding_model.path).name
        for filename in extra_paths:
            path = pathlib.Path(filename).name
            old_file_content = archive.read(path)
            new_file_name = filename.replace(old_embedding_path, new_embedding_path)
            new_file_path = pathlib.Path(RELATIVE_MODELS_PATH) / "embedding" / new_file_name
            with open(new_file_path, "wb") as fp:
                fp.write(old_file_content)


    @staticmethod
    def add_file_to_embedding_object(archive, model_object, model_json, name_key: str, model_json_key: str):
        """
        Get all the informational segments from the name, later used in changing the id
        to avoid any collisions just in case.
        """
        full_model_path, relative_model_path = model_object.generate_name(name_key)

        old_path = pathlib.Path(model_json[model_json_key])
        with open(full_model_path, "wb") as fp:
            fp.write(archive.read(old_path.name))
            ref = getattr(model_object, model_json_key)  # Get reference to the field in the Embedding.
            setattr(ref, "name", str(relative_model_path))  # Set the fields name parameter to the new path.

        return model_object


    @staticmethod
    def create_embedding_object(model_data: dict, user_id: int, project_id: int):
        indices = model_data.pop("indices")
        new_model = Embedding(**model_data)

        # Create a task object to fill the new model object with.
        # Pull the user and project into which it's imported from the web request.
        new_task = Task.objects.create(embedding=new_model, task_type=Task.TYPE_TRAIN, status=Task.STATUS_COMPLETED)
        new_model.author = User.objects.get(id=user_id)
        new_model.project = Project.objects.get(id=project_id)
        new_model.save()  # Save the intermediate results.

        new_model.tasks.add(new_task)

        for index_name in indices:
            index, is_created = Index.objects.get_or_create(name=index_name)
            new_model.indices.add(index)

        new_model.save()
        return new_model


    def get_embedding(self):
        """
        Returns embedding object based on embedding type.
        """
        stop_words = json.loads(self.stop_words)
        stopword_kwargs = {"custom_stop_words": stop_words} if stop_words else {}

        if self.embedding_type == FASTTEXT_EMBEDDING:
            return FastTextEmbedding(
                min_freq=self.min_freq,
                num_dimensions=self.num_dimensions,
                window=self.window_size,
                num_epochs=self.num_epochs,
                text_processor=TextProcessor(sentences=True, remove_stop_words=True, words_as_list=True, **stopword_kwargs)
            )
        elif self.embedding_type == W2V_EMBEDDING:
            return W2VEmbedding(
                min_freq=self.min_freq,
                num_dimensions=self.num_dimensions,
                window=self.window_size,
                num_epochs=self.num_epochs,
                text_processor=TextProcessor(sentences=True, remove_stop_words=True, words_as_list=True, **stopword_kwargs)
            )
        else:
            return W2VEmbedding(
                min_freq=self.min_freq,
                num_dimensions=self.num_dimensions,
                window=self.window_size,
                num_epochs=self.num_epochs,
                text_processor=TextProcessor(sentences=True, remove_stop_words=True, words_as_list=True, **stopword_kwargs)
            )


    def get_indices(self):
        return [index.name for index in self.indices.all()]


    def to_json(self) -> dict:
        serialized = serializers.serialize('json', [self])
        json_obj = {"fields": json.loads(serialized)[0]["fields"], "embedding_extras": []}
        json_obj["fields"].pop("project")
        json_obj["fields"].pop("author", None)
        json_obj["fields"].pop("tasks", None)
        json_obj["embedding_extras"] = Embedding.get_extra_model_file_names(self.embedding_model.path)
        return json_obj


    def export_resources(self) -> HttpResponse:
        with tempfile.SpooledTemporaryFile(encoding="utf8") as tmp:
            with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as archive:
                # write model object to zip as json
                model_fields = self.to_json()
                model_json = json.dumps(model_fields).encode("utf8")
                archive.writestr(self.MODEL_JSON_NAME, model_json)
                # Create some helper paths.
                embedding_path = pathlib.Path(self.embedding_model.path)
                model_type, pk, model_hash = embedding_path.name.split("_")
                model_dir_path = embedding_path.parent
                # Fetch all the embedding related models that share the same hash and write
                # them into the zip. Gensim creates additional files for larger embeddings,
                # which makes this necessary.
                for item in model_dir_path.glob("*{}*".format(model_hash)):
                    archive.write(item, arcname=str(pathlib.Path(item).name))
            tmp.seek(0)
            return tmp.read()


    @staticmethod
    def import_resources(zip_file, request, pk) -> int:
        with zipfile.ZipFile(zip_file, 'r') as archive:
            json_string = archive.read(Embedding.MODEL_JSON_NAME).decode()
            original_json = json.loads(json_string)
            model_json = original_json["fields"]
            model_json.pop("favorited_users", None)

            # Create the new embedding object and save it to the DB.
            new_model = Embedding.create_embedding_object(model_json, request.user.id, pk)
            new_model = Embedding.add_file_to_embedding_object(archive, new_model, model_json, "embedding", "embedding_model")

            Embedding.save_embedding_extra_files(archive, new_model, model_json, extra_paths=original_json["embedding_extras"])

            new_model.save()
            return new_model.id


    def generate_name(self, name="embedding"):
        """
        Do not change this carelessly as import/export functionality depends on this.
        Returns full and relative filepaths for the intended models.
        Args:
            name: Name for the model to distinguish itself from others in the same directory.

        Returns: Full and relative file paths, full for saving the model object and relative for actual DB storage.
        """
        model_file_name = f'{name}_{str(self.pk)}_{secrets.token_hex(10)}'
        full_path = pathlib.Path(BASE_DIR) / RELATIVE_MODELS_PATH / "embedding" / model_file_name
        relative_path = pathlib.Path(RELATIVE_MODELS_PATH) / "embedding" / model_file_name
        return str(full_path), str(relative_path)


    def train(self):
        new_task = Task.objects.create(embedding=self, task_type=Task.TYPE_TRAIN, status=Task.STATUS_CREATED)
        self.save()
        self.tasks.add(new_task)
        from toolkit.embedding.tasks import train_embedding
        train_embedding.apply_async(args=(self.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE)


    def __str__(self):
        return self.description


@receiver(models.signals.post_delete, sender=Embedding)
def auto_delete_embedding_on_delete(sender, instance: Embedding, **kwargs):
    """
    Delete resources on the file-system upon Embedding deletion.
    Triggered on individual model object and queryset Embedding deletion.
    """
    if instance.embedding_model:
        embedding_path = pathlib.Path(instance.embedding_model.path)
        for path in embedding_path.parent.glob("{}*".format(embedding_path.name)):
            if path.exists():
                os.remove(str(path))
        if os.path.isfile(instance.embedding_model.path):
            os.remove(instance.embedding_model.path)
