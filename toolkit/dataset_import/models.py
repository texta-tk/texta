import os

from django.contrib.auth.models import User
from django.db.models import signals
from django.dispatch import receiver
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
    separator = models.CharField(max_length=MAX_DESC_LEN, default=',')
    num_documents = models.IntegerField(default=0)
    num_documents_success = models.IntegerField(default=0)
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.description

    def start_import(self):
        new_task = Task.objects.create(datasetimport=self, status='created')
        self.task = new_task
        self.save()
        from toolkit.dataset_import.tasks import import_dataset
        apply_celery_task(import_dataset, self.pk)


@receiver(models.signals.post_delete, sender=DatasetImport)
def auto_delete_file_on_delete(sender, instance: DatasetImport, **kwargs):
    """
    Delete resources on the file-system upon DatasetImport deletion.
    Triggered on individual model object and queryset DatasetImport deletion.
    """
    if instance.file:
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)
