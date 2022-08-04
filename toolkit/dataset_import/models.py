import os
from django.contrib.auth.models import User
from django.db import models
from django.dispatch import receiver

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE


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
        new_task = Task.objects.create(datasetimport=self, status=Task.STATUS_CREATED, task_type=Task.TYPE_IMPORT)
        self.task = new_task
        self.save()
        from toolkit.dataset_import.tasks import import_dataset
        import_dataset.apply_async(args=(self.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE)


@receiver(models.signals.post_delete, sender=DatasetImport)
def auto_delete_file_on_delete(sender, instance: DatasetImport, **kwargs):
    """
    Delete resources on the file-system upon DatasetImport deletion.
    Triggered on individual model object and queryset DatasetImport deletion.
    """
    if instance.file:
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)

    if instance.task != Task.STATUS_COMPLETED:
        instance.project.indices.filter(name=instance.index).delete()
