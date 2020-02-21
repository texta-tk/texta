import json

from django.contrib.auth.models import User
from django.db import models
from django.db.models import signals
from multiselectfield import MultiSelectField

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.searcher import EMPTY_QUERY, ElasticSearcher
from toolkit.helper_functions import apply_celery_task
from toolkit.mlp.choices import MLP_ANALYZER_CHOICES


class MLPProcessor(models.Model):
    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    fields = models.TextField(default=json.dumps([]))
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)
    analyzers = MultiSelectField(default=MLP_ANALYZER_CHOICES[0])
    indices = models.TextField(default=json.dumps([]))


    def __str__(self):
        return self.description


    @classmethod
    def start_mlp_task(cls, sender, instance, created, **kwargs):
        if created:
            indices = json.loads(instance.indices)
            total = ElasticSearcher(query=instance.query, indices=indices).count()

            new_task = Task.objects.create(mlpprocessor=instance, status='created', total=total)
            instance.task = new_task
            instance.save()

            from toolkit.mlp.tasks import start_mlp
            apply_celery_task(start_mlp, instance.pk)


signals.post_save.connect(MLPProcessor.start_mlp_task, sender=MLPProcessor)
