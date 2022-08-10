import json

from django.contrib.auth.models import User
from django.db import models, transaction
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.model_constants import CommonModelMixin
from toolkit.settings import CELERY_MLP_TASK_QUEUE


class MLPWorker(CommonModelMixin):
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    indices = models.ManyToManyField(Index)
    fields = models.TextField(default=json.dumps([]))
    analyzers = models.TextField(default=json.dumps([]))
    es_scroll_size = models.IntegerField(default=100)
    es_timeout = models.IntegerField(default=30)


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]


    def __str__(self):
        return '{0} - {1}'.format(self.pk, self.description)


    def process(self):
        from toolkit.mlp.tasks import start_mlp_worker

        new_task = Task.objects.create(mlpworker=self, task_type=Task.TYPE_APPLY, status=Task.STATUS_CREATED)
        self.save()
        self.tasks.add(new_task)

        transaction.on_commit(lambda: start_mlp_worker.s(self.pk).apply_async(queue=CELERY_MLP_TASK_QUEUE))


class ApplyLangWorker(CommonModelMixin):
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    field = models.TextField()
    indices = models.ManyToManyField(Index)


    def process(self):
        from toolkit.mlp.tasks import apply_lang_on_indices

        new_task = Task.objects.create(applylangworker=self, task_type=Task.TYPE_APPLY, status=Task.STATUS_CREATED)
        self.save()
        self.tasks.add(new_task)

        # Run the task.
        apply_lang_on_indices.apply_async(args=(self.pk,), queue=CELERY_MLP_TASK_QUEUE)


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]
