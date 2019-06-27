from django.contrib.auth.models import User
from django.db.models import signals
from django.db import models

from toolkit.embedding.models import Embedding
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
import json


MAX_STR_LEN = 100

class WordCluster(models.Model):
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
            print('sadf')
            #new_task = Task.objects.create(word_cluster=instance, status='created')
            #instance.task = new_task
            #instance.save()
            #from toolkit.embedding.tasks import train_embedding
            #train_embedding.apply_async(args=(instance.pk,))


signals.post_save.connect(WordCluster.cluster_embedding_vocabulary, sender=WordCluster)
