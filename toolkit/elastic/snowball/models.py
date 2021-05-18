import json

from django.contrib.auth.models import User
from django.db import models

from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.elastic.tools.searcher import EMPTY_QUERY
from toolkit.settings import CELERY_MLP_TASK_QUEUE


class ApplyStemmerWorker(models.Model):
    MAX_DESC_LEN = 1000

    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    stemmer_lang = models.CharField(max_length=MAX_DESC_LEN, null=True)
    fields = models.TextField(default=json.dumps([]))
    detect_lang = models.BooleanField()
    indices = models.ManyToManyField(Index)
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)
    es_timeout = models.IntegerField(default=15, help_text="How many minutes should there be between scroll requests before triggering a timeout.")
    bulk_size = models.IntegerField(default=100, help_text="How many documents should be returned by Elasticsearch with each request.")


    def process(self):
        from toolkit.elastic.snowball.tasks import apply_snowball_on_indices

        new_task = Task.objects.create(applystemmerworker=self, status='created')
        self.task = new_task
        self.save()

        # Run the task.
        apply_snowball_on_indices.apply_async(args=(self.pk,), queue=CELERY_MLP_TASK_QUEUE)


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]
