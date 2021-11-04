import json

from django.contrib.auth.models import User
from django.db import models
from django.db.models import signals

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from texta_elastic.searcher import EMPTY_QUERY
from toolkit.elastic.choices import LABEL_DISTRIBUTION
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE


class IndexSplitter(models.Model):
    from toolkit.core.project.models import Project

    description = models.CharField(max_length=MAX_DESC_LEN, default="")
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    scroll_size = models.IntegerField(default=500)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    indices = models.ManyToManyField(Index)
    fields = models.TextField(default=json.dumps([]))
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)

    train_index = models.CharField(max_length=MAX_DESC_LEN, default="")
    test_index = models.CharField(max_length=MAX_DESC_LEN, default="")
    fact = models.CharField(max_length=MAX_DESC_LEN, default="")
    str_val = models.CharField(max_length=MAX_DESC_LEN, default="")

    test_size = models.IntegerField(default=20)
    distribution = models.TextField(default=LABEL_DISTRIBUTION[0][0])
    custom_distribution = models.TextField(default=json.dumps({}))

    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]

    def get_query(self):
        return json.loads(self.query)

    def get_custom_distribution(self):
        return json.loads(self.custom_distribution)

    def start_task(self):
        new_task = Task.objects.create(indexsplitter=self, status='created')
        self.task = new_task
        self.save()
        from toolkit.elastic.index_splitter.tasks import index_splitting_task
        index_splitting_task.apply_async(args=(self.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE)