from celery.decorators import task

from .dataset import Dataset
from .models import DatasetImport
from toolkit.core.task.models import Task
from toolkit.tools.show_progress import ShowProgress
from toolkit.base_task import BaseTask


@task(name="import_dataset", base=BaseTask)
def import_dataset(dataset_import_id):
    # retrieve object & task
    import_object = DatasetImport.objects.get(pk=dataset_import_id)
    task_object = import_object.task
    # create progress
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('importing dataset')
    show_progress.update_view(0)
    try:
        # retrieve file path from object
        file_path = import_object.file.path
        ds = Dataset(file_path, import_object.index)
        errors = ds.import_dataset()
        if errors:
            show_progress.update_errors(errors)
            task_object.update_status(Task.STATUS_FAILED)
            return False
        # declare the job done
        show_progress.update_step('')
        show_progress.update_view(100.0)
        task_object.update_status(Task.STATUS_COMPLETED, set_time_completed=True)
        return True
    except Exception as e:
        # declare the job failed
        show_progress.update_errors(e)
        task_object.update_status(Task.STATUS_FAILED)
        raise
