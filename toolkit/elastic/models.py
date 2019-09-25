from toolkit.elastic.core import ElasticCore
from toolkit.constants import MAX_DESC_LEN
from toolkit.core.task.models import Task
from toolkit.core.project.models import Project
from toolkit.helper_functions import apply_celery_task

from django.contrib.auth.models import User
from django.db.models import signals
from django.db import models
import json


class Reindexer(models.Model):
    description = models.CharField(max_length=MAX_DESC_LEN, default="")
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    indices = models.TextField(default=json.dumps([]))
    fields = models.TextField(default=json.dumps([]))
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)
    new_index = models.CharField(max_length=MAX_DESC_LEN, default="")

    def __str__(self):
        return self.description


    @classmethod
    def create_reindexer_model(cls, sender, instance, created, **kwargs):
        if created:
            new_task = Task.objects.create(reindexer=instance, status='created')
            instance.task = new_task
            instance.save()
            from toolkit.elastic.tasks import reindex_task

            apply_celery_task(reindex_task, instance.pk)


signals.post_save.connect(Reindexer.create_reindexer_model, sender=Reindexer)
