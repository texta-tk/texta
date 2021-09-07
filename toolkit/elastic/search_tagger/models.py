import json

from django.contrib.auth.models import User
from django.db import models, transaction

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.elastic.tools.searcher import EMPTY_QUERY
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE


class SearchQueryTagger(models.Model):
    description = models.CharField(max_length=MAX_DESC_LEN, default="")
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    indices = models.ManyToManyField(Index)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    fields = models.TextField(default=json.dumps([]))
    fact_name = models.TextField()
    fact_value = models.TextField()
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)
    bulk_size = models.IntegerField(default=100)
    es_timeout = models.IntegerField(default=10)


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]


    def __str__(self):
        return self.description


    def process(self):
        from toolkit.elastic.search_tagger.tasks import start_search_query_tagger_worker, apply_search_query_tagger_on_index, end_search_query_tagger_task

        new_task = Task.objects.create(searchquerytagger=self, status='created')
        self.task = new_task
        self.save()

        chain = start_search_query_tagger_worker.s() | apply_search_query_tagger_on_index.s() | end_search_query_tagger_task.s()
        transaction.on_commit(lambda: chain.apply_async(args=(self.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE))


class SearchFieldsTagger(models.Model):
    description = models.CharField(max_length=MAX_DESC_LEN, default="")
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    indices = models.ManyToManyField(Index)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    fields = models.TextField(default=json.dumps([]))
    fact_name = models.TextField()
    use_breakup = models.BooleanField(default=True)
    breakup_character = models.TextField(default="\n")
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)

    bulk_size = models.IntegerField(default=100)
    es_timeout = models.IntegerField(default=10)


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]


    def __str__(self):
        return self.description


    def process(self):
        from toolkit.elastic.search_tagger.tasks import start_search_fields_tagger_worker, apply_search_fields_tagger_on_index, end_search_fields_tagger_task

        new_task = Task.objects.create(searchfieldstagger=self, status='created')
        self.task = new_task
        self.save()

        chain = start_search_fields_tagger_worker.s() | apply_search_fields_tagger_on_index.s() | end_search_fields_tagger_task.s()
        chain.apply_async(args=(self.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE)
