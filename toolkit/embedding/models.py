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

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.helper_functions import apply_celery_task
from toolkit.multiselectfield import PatchedMultiSelectField as MultiSelectField
from toolkit.settings import MODELS_DIR


class Embedding(models.Model):
    MODEL_JSON_NAME = "model.json"

    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    fields = models.TextField(default=json.dumps([]))
    indices = MultiSelectField(default=None)
    num_dimensions = models.IntegerField(default=100)
    max_documents = models.IntegerField(default=0)
    min_freq = models.IntegerField(default=10)
    vocab_size = models.IntegerField(default=0)

    embedding_model = models.FileField(null=True, verbose_name='', default=None)
    phraser_model = models.FileField(null=True, verbose_name='', default=None)
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)


    def to_json(self) -> dict:
        serialized = serializers.serialize('json', [self])
        json_obj = {"fields": json.loads(serialized)[0]["fields"], "embedding_extras": []}
        json_obj["fields"].pop("project", None)
        json_obj["fields"].pop("author", None)
        json_obj["fields"].pop("task", None)

        embedding_model_path = pathlib.Path(self.embedding_model.path)
        model_type, pk, model_hash = embedding_model_path.name.split("_")
        for item in pathlib.Path(self.embedding_model.path).parent.glob("*{}*".format(model_hash)):
            if item.name != embedding_model_path.name:
                json_obj["embedding_extras"].append(item.name)

        return json_obj


    def export_resources(self) -> HttpResponse:
        with tempfile.SpooledTemporaryFile(encoding="utf8") as tmp:
            with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as archive:
                # write model object to zip as json
                model_fields = self.to_json()
                model_json = json.dumps(model_fields).encode("utf8")
                archive.writestr(self.MODEL_JSON_NAME, model_json)

                # Create some helper paths.
                phraser_path = pathlib.Path(self.phraser_model.path)
                model_dir_path = phraser_path.parent
                embedding_path = pathlib.Path(self.embedding_model.path)
                model_type, pk, model_hash = embedding_path.name.split("_")

                # Write the phraser model into the zip.
                archive.write(str(phraser_path), arcname=str(phraser_path.name))

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
            new_model = Embedding(**model_json)

            # Create a task object to fill the new model object with.
            # Pull the user and project into which it's imported from the web request.
            new_model.task = Task.objects.create(embedding=new_model, status=Task.STATUS_COMPLETED)
            new_model.author = User.objects.get(id=request.user.id)
            new_model.project = Project.objects.get(id=pk)
            new_model.save()  # Save the intermediate results.

            # Get all the informational segments from the name, later used in changing the id
            # to avoid any collisions just in case.
            old_embedding_path = pathlib.Path(model_json["embedding_model"])
            new_embedding_path = pathlib.Path(new_model.generate_name("embedding"))

            old_phraser_path = pathlib.Path(model_json["phraser_model"])
            new_phraser_path = pathlib.Path(new_model.generate_name("phraser"))

            with open(new_phraser_path, "wb") as fp:
                fp.write(archive.read(old_phraser_path.name))
                new_model.phraser_model.name = str(new_phraser_path)

            with open(new_embedding_path, "wb") as fp:
                fp.write(archive.read(old_embedding_path.name))
                new_model.embedding_model.name = str(new_embedding_path)

            # Add the extra files from Gensim, they are not stored inside the mode,
            # but need to have the same suffix as the name of the embedding file for Gensim
            # to pick it up.
            for filename in original_json["embedding_extras"]:
                old_file_content = archive.read(filename)
                new_file_name = filename.replace(old_embedding_path.name, new_embedding_path.name)
                new_file_path = pathlib.Path(MODELS_DIR) / "embedding" / new_file_name
                with open(new_file_path, "wb") as fp:
                    fp.write(old_file_content)

            new_model.save()
            return new_model.id


    def generate_name(self, name="embedding"):
        """Model import/export is dependant on the name, do not change carelessly."""
        return os.path.join(MODELS_DIR, 'embedding', f'{name}_{str(self.pk)}_{secrets.token_hex(10)}')


    def train(self):
        new_task = Task.objects.create(embedding=self, status='created')
        self.task = new_task
        self.save()
        from toolkit.embedding.tasks import train_embedding
        apply_celery_task(train_embedding, self.pk)


    def __str__(self):
        return self.description


class EmbeddingCluster(models.Model):
    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    embedding = models.ForeignKey(Embedding, on_delete=models.CASCADE)
    num_clusters = models.IntegerField(default=100)
    cluster_model = models.FileField(null=True, verbose_name='', default=None)
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)


    def __str__(self):
        return self.description


    @classmethod
    def cluster_embedding_vocabulary(cls, sender, instance, created, **kwargs):
        if created:
            new_task = Task.objects.create(embeddingcluster=instance, status='created')
            instance.task = new_task
            instance.save()
            from toolkit.embedding.tasks import cluster_embedding
            apply_celery_task(cluster_embedding, instance.pk)


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

    if instance.phraser_model:
        if os.path.isfile(instance.phraser_model.path):
            os.remove(instance.phraser_model.path)


@receiver(models.signals.post_save, sender=EmbeddingCluster)
def train_cluster_embedding_vocabulary(sender, instance: EmbeddingCluster, created, **kwargs):
    EmbeddingCluster.cluster_embedding_vocabulary(sender, instance, created, **kwargs)


@receiver(models.signals.post_delete, sender=EmbeddingCluster)
def auto_delete_embedding_cluster_on_delete(sender, instance: EmbeddingCluster, **kwargs):
    """
    Delete resources on the file-system upon cluster deletion.
    Triggered on individual model object and queryset EmbeddingCluster deletion.
    """
    if instance.cluster_model:
        if os.path.isfile(instance.cluster_model.path):
            os.remove(instance.cluster_model.path)
