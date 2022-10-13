import json
from typing import List

from django.db import models
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.model_constants import CommonModelMixin
from toolkit.serializer_constants import BULK_SIZE_HELPTEXT, ES_TIMEOUT_HELPTEXT
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE


class DeleteFactsByQueryTask(CommonModelMixin):
    scroll_size = models.IntegerField(default=500, help_text=BULK_SIZE_HELPTEXT)
    es_timeout = models.IntegerField(default=15, help_text=ES_TIMEOUT_HELPTEXT)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    indices = models.ManyToManyField(Index)
    facts = models.TextField()


    def get_available_or_all_indices(self, indices: List[str] = None) -> List[str]:
        """
        Used in views where the user can select the indices they wish to use.
        Returns a list of index names from the ones that are in the project
        and in the indices parameter or all of the indices if it's None or empty.
        """
        if indices:
            indices = self.indices.filter(name__in=indices, is_open=True)
            if not indices:
                indices = self.project.indices.all()
        else:
            indices = self.indices.all()

        indices = [index.name for index in indices]
        indices = list(set(indices))  # Leave only unique names just in case.
        return indices


    def __str__(self):
        return '{0} - {1}'.format(self.pk, self.description)


    def process(self):
        from .tasks import start_fact_delete_query_task, fact_delete_query_task
        new_task = Task.objects.create(deletefactsbyquerytask=self, task_type=Task.TYPE_APPLY, status=Task.STATUS_CREATED)
        self.save()
        self.tasks.add(new_task)
        chain = start_fact_delete_query_task.s() | fact_delete_query_task.s()
        chain.apply_async(args=(self.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE)


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]


class EditFactsByQueryTask(CommonModelMixin):
    scroll_size = models.IntegerField(default=500, help_text=BULK_SIZE_HELPTEXT)
    es_timeout = models.IntegerField(default=15, help_text=ES_TIMEOUT_HELPTEXT)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    indices = models.ManyToManyField(Index)
    target_facts = models.TextField(help_text="Which facts to select for editing.")
    fact = models.TextField(help_text="End result of the selected facts.")


    def get_available_or_all_indices(self, indices: List[str] = None) -> List[str]:
        """
        Used in views where the user can select the indices they wish to use.
        Returns a list of index names from the ones that are in the project
        and in the indices parameter or all of the indices if it's None or empty.
        """
        if indices:
            indices = self.indices.filter(name__in=indices, is_open=True)
            if not indices:
                indices = self.project.indices.all()
        else:
            indices = self.indices.all()

        indices = [index.name for index in indices]
        indices = list(set(indices))  # Leave only unique names just in case.
        return indices


    def __str__(self):
        return '{0} - {1}'.format(self.pk, self.description)


    def process(self):
        from .tasks import start_fact_edit_query_task, fact_edit_query_task
        new_task = Task.objects.create(editfactsbyquerytask=self, task_type=Task.TYPE_APPLY, status=Task.STATUS_CREATED)
        self.save()
        self.tasks.add(new_task)
        chain = start_fact_edit_query_task.s() | fact_edit_query_task.s()
        chain.apply_async(args=(self.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE)


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]
