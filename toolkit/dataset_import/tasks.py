from celery.decorators import task

from .dataset import Dataset
from .models import DatasetImport
from toolkit.core.task.models import Task
from toolkit.tools.show_progress import ShowProgress
from toolkit.base_task import BaseTask


@task(name="import_dataset", base=BaseTask)
def import_dataset(dataset_import_id):
    import_object = DatasetImport.objects.get(pk=dataset_import_id)
    task_object = import_object.task

    ds = Dataset()
    ds.import_dataset(import_object)

