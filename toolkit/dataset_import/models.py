from django.contrib.auth.models import User
from django.db.models import signals
from django.db import models

from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.constants import MAX_DESC_LEN
from toolkit.helper_functions import apply_celery_task

class DatasetImport(models.Model):
    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    index = models.CharField(max_length=MAX_DESC_LEN)
    file = models.FileField(upload_to='data/upload')
    num_documents = models.IntegerField(default=0)
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.description
    
    @classmethod
    def start_import_job(cls, sender, instance, created, **kwargs):
        if created:
            new_task = Task.objects.create(datasetimport=instance, status=Task.STATUS_CREATED)
            instance.task = new_task
            instance.save()
            from toolkit.dataset_import.tasks import import_dataset
            apply_celery_task(import_dataset, instance.pk)

signals.post_save.connect(DatasetImport.start_import_job, sender=DatasetImport)
