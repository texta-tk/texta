import json

from django.db import models, transaction
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.model_constants import CommonModelMixin
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE


class SearchQueryTagger(CommonModelMixin):
    indices = models.ManyToManyField(Index)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    fields = models.TextField(default=json.dumps([]))
    fact_name = models.TextField()
    fact_value = models.TextField()
    bulk_size = models.IntegerField(default=100)
    es_timeout = models.IntegerField(default=10)


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]


    def __str__(self):
        return self.description


    def process(self):
        from toolkit.elastic.search_tagger.tasks import start_search_query_tagger_worker, apply_search_query_tagger_on_index, end_search_query_tagger_task

        new_task = Task.objects.create(searchquerytagger=self, status=Task.STATUS_CREATED, task_type=Task.TYPE_APPLY)
        self.save()
        self.tasks.add(new_task)

        chain = start_search_query_tagger_worker.s() | apply_search_query_tagger_on_index.s() | end_search_query_tagger_task.s()
        transaction.on_commit(lambda: chain.apply_async(args=(self.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE))


class SearchFieldsTagger(CommonModelMixin):
    indices = models.ManyToManyField(Index)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    fields = models.TextField(default=json.dumps([]))
    fact_name = models.TextField()
    use_breakup = models.BooleanField(default=True)
    breakup_character = models.TextField(default="\n")

    bulk_size = models.IntegerField(default=100)
    es_timeout = models.IntegerField(default=10)


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]


    def __str__(self):
        return self.description


    def process(self):
        from toolkit.elastic.search_tagger.tasks import start_search_fields_tagger_worker, apply_search_fields_tagger_on_index, end_search_fields_tagger_task

        new_task = Task.objects.create(searchfieldstagger=self, status=Task.STATUS_CREATED, task_type=Task.TYPE_APPLY)
        self.save()
        self.tasks.add(new_task)

        chain = start_search_fields_tagger_worker.s() | apply_search_fields_tagger_on_index.s() | end_search_fields_tagger_task.s()
        chain.apply_async(args=(self.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE)
