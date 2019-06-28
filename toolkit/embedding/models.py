import sys
import json
from django.contrib.auth.models import User
from django.db.models import signals
from django.db import models
from multiselectfield import MultiSelectField

from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.searcher import EMPTY_QUERY


MAX_STR_LEN = 100

class Embedding(models.Model):
    description = models.CharField(max_length=MAX_STR_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    fields = MultiSelectField(max_length=MAX_STR_LEN*100)

    num_dimensions = models.IntegerField(default=100)
    #max_vocab = models.IntegerField(default=0)
    min_freq = models.IntegerField(default=10)

    vocab_size = models.IntegerField(default=0)
    location = models.TextField(default=None, null=True)
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.description
    
    @classmethod
    def train_embedding_model(cls, sender, instance, created, **kwargs):
        if created:
            new_task = Task.objects.create(embedding=instance, status='created')
            instance.task = new_task
            instance.save()
            from toolkit.embedding.tasks import train_embedding
            if not 'test' in sys.argv:
                train_embedding.apply_async(args=(instance.pk,))
            else:
                train_embedding(instance.pk)


signals.post_save.connect(Embedding.train_embedding_model, sender=Embedding)


class EmbeddingCluster(models.Model):
    description = models.CharField(max_length=MAX_STR_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    embedding = models.ForeignKey(Embedding, on_delete=models.CASCADE)
    num_clusters = models.IntegerField(default=100)
    location = models.TextField(default=None, null=True)
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
            cluster_embedding.apply_async(args=(instance.pk,))


signals.post_save.connect(EmbeddingCluster.cluster_embedding_vocabulary, sender=EmbeddingCluster)