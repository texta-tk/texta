import json
import os
import secrets

from django.contrib.auth.models import User
from django.db import models
from django.dispatch import receiver

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.helper_functions import apply_celery_task
from toolkit.settings import MODELS_DIR


class Embedding(models.Model):
    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    fields = models.TextField(default=json.dumps([]))

    num_dimensions = models.IntegerField(default=100)
    max_documents = models.IntegerField(default=0)
    min_freq = models.IntegerField(default=10)

    vocab_size = models.IntegerField(default=0)
    embedding_model = models.FileField(null=True, verbose_name='', default=None)
    phraser_model = models.FileField(null=True, verbose_name='', default=None)
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)

    def generate_name(self, name):
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
