import json

from django.contrib.auth.models import User
from django.db import models, transaction

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from texta_elastic.searcher import EMPTY_QUERY
from toolkit.settings import CELERY_MLP_TASK_QUEUE


class MLPWorker(models.Model):
    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    indices = models.ManyToManyField(Index)
    fields = models.TextField(default=json.dumps([]))
    analyzers = models.TextField(default=json.dumps([]))
    es_scroll_size = models.IntegerField(default=100)
    es_timeout = models.IntegerField(default=30)

    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]


    def __str__(self):
        return '{0} - {1}'.format(self.pk, self.description)


    def process(self):
        from toolkit.mlp.tasks import start_mlp_worker

        new_task = Task.objects.create(mlpworker=self, task_type=Task.TYPE_APPLY, status=Task.STATUS_CREATED)
        self.task = new_task
        self.save()

        transaction.on_commit(lambda: start_mlp_worker.s(self.pk).apply_async(queue=CELERY_MLP_TASK_QUEUE))


class ApplyLangWorker(models.Model):
    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    field = models.TextField()
    indices = models.ManyToManyField(Index)
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)


    def process(self):
        from toolkit.mlp.tasks import apply_lang_on_indices

        new_task = Task.objects.create(applylangworker=self, task_type=Task.TYPE_APPLY, status=Task.STATUS_CREATED)
        self.task = new_task
        self.save()

        # Run the task.
        apply_lang_on_indices.apply_async(args=(self.pk,), queue=CELERY_MLP_TASK_QUEUE)


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]
