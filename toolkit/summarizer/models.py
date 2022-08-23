import json

from django.contrib.auth.models import User
from django.db import models, transaction
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.model_constants import CommonModelMixin
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE


class Summarizer(CommonModelMixin):
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    indices = models.ManyToManyField(Index)
    fields = models.TextField(default=json.dumps([]))
    algorithm = models.TextField(default=json.dumps([]))
    ratio = models.DecimalField(max_digits=3, decimal_places=1)


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]


    def __str__(self):
        return '{0} - {1}'.format(self.pk, self.description)


    def process(self):
        from toolkit.summarizer.tasks import apply_summarizer_on_index, start_summarizer_worker, end_summarizer_task

        new_task = Task.objects.create(summarizer=self, status=Task.STATUS_CREATED, task_type=Task.TYPE_APPLY)
        self.save()

        self.tasks.add(new_task)

        chain = start_summarizer_worker.s() | apply_summarizer_on_index.s() | end_summarizer_task.s()
        transaction.on_commit(lambda: chain.apply_async(args=(self.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE))
