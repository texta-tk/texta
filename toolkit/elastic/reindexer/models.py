import json

from django.db import models
from django.db.models import signals
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.task.models import Task
from toolkit.model_constants import CommonModelMixin
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE


class Reindexer(CommonModelMixin):
    scroll_size = models.IntegerField(default=500)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    indices = models.TextField(default=json.dumps([]))
    fields = models.TextField(default=json.dumps([]))
    new_index = models.CharField(max_length=MAX_DESC_LEN, default="")
    random_size = models.IntegerField(default=0)
    field_type = models.TextField(default=json.dumps([]))
    add_facts_mapping = models.BooleanField(default=False)


    def __str__(self):
        return self.description


    @classmethod
    def create_reindexer_model(cls, sender, instance, created, **kwargs):
        if created:
            new_task = Task.objects.create(reindexer=instance, status=Task.STATUS_CREATED, task_type=Task.TYPE_APPLY)
            instance.tasks.add(new_task)

            from toolkit.elastic.reindexer.tasks import reindex_task
            reindex_task.apply_async(args=(instance.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE)


signals.post_save.connect(Reindexer.create_reindexer_model, sender=Reindexer)
