import json

from django.db import models
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.model_constants import CommonModelMixin
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE


class ApplyESAnalyzerWorker(CommonModelMixin):
    MAX_DESC_LEN = 1000

    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    fields = models.TextField(default=json.dumps([]))
    indices = models.ManyToManyField(Index)

    analyzers = models.TextField(default=json.dumps([]))

    strip_html = models.BooleanField(default=True)
    tokenizer = models.CharField(max_length=100, default="standard")
    stemmer_lang = models.CharField(max_length=100, null=True)
    detect_lang = models.BooleanField(default=False)
    es_timeout = models.IntegerField(default=15, help_text="How many minutes should there be between scroll requests before triggering a timeout.")
    bulk_size = models.IntegerField(default=100, help_text="How many documents should be returned by Elasticsearch with each request.")


    def process(self):
        from toolkit.elastic.analyzers.tasks import apply_analyzers_on_indices

        new_task = Task.objects.create(applyesanalyzerworker=self, status=Task.STATUS_CREATED, task_type=Task.TYPE_APPLY)
        self.save()

        self.tasks.add(new_task)
        # Run the task.
        apply_analyzers_on_indices.apply_async(args=(self.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE)


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]
