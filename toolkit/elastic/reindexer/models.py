import json

from django.contrib.auth.models import User
from django.db import models
from django.db.models import signals

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.task.models import Task
from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.elastic.choices import LABEL_DISTRIBUTION
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE

class Reindexer(models.Model):
    from toolkit.core.project.models import Project

    description = models.CharField(max_length=MAX_DESC_LEN, default="")
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    scroll_size = models.IntegerField(default=500)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    indices = models.TextField(default=json.dumps([]))
    fields = models.TextField(default=json.dumps([]))
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)
    new_index = models.CharField(max_length=MAX_DESC_LEN, default="")
    random_size = models.IntegerField(default=0)
    field_type = models.TextField(default=json.dumps([]))
    add_facts_mapping = models.BooleanField(default=False)


    def __str__(self):
        return self.description


    @classmethod
    def create_reindexer_model(cls, sender, instance, created, **kwargs):
        if created:
            new_task = Task.objects.create(reindexer=instance, status='created')
            instance.task = new_task
            instance.save()

            from toolkit.elastic.tasks import reindex_task
            reindex_task.apply_async(args=(instance.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE)


signals.post_save.connect(Reindexer.create_reindexer_model, sender=Reindexer)