import os

from django.contrib.auth.models import User
from django.db import models, transaction
from django.dispatch import receiver

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.model_constants import CommonModelMixin
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE


class DatasetImport(CommonModelMixin):
    index = models.CharField(max_length=MAX_DESC_LEN)
    file = models.FileField(upload_to='data/upload')
    separator = models.CharField(max_length=MAX_DESC_LEN, default=',')
    num_documents = models.IntegerField(default=0)
    num_documents_success = models.IntegerField(default=0)


    def __str__(self):
        return self.description


    def start_import(self):
        new_task = Task.objects.create(datasetimport=self, status=Task.STATUS_CREATED, task_type=Task.TYPE_IMPORT)
        self.save()
        self.tasks.add(new_task)
        from toolkit.dataset_import.tasks import import_dataset
        transaction.on_commit(lambda: import_dataset.apply_async(args=(self.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE))


@receiver(models.signals.post_delete, sender=DatasetImport)
def auto_delete_file_on_delete(sender, instance: DatasetImport, **kwargs):
    """
    Delete resources on the file-system upon DatasetImport deletion.
    Triggered on individual model object and queryset DatasetImport deletion.
    """
    if instance.file:
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)

    if instance.tasks.last() != Task.STATUS_COMPLETED:
        instance.project.indices.filter(name=instance.index).delete()
