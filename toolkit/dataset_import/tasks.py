import logging

from celery.decorators import task

from toolkit.base_tasks import TransactionAwareTask
from toolkit.elastic.index.models import Index
from toolkit.tools.show_progress import ShowProgress
from .dataset import Dataset
from .models import DatasetImport
from ..settings import ERROR_LOGGER, INFO_LOGGER


@task(name="import_dataset", base=TransactionAwareTask)
def import_dataset(dataset_import_id):
    # retrieve object & task
    import_object = DatasetImport.objects.get(pk=dataset_import_id)
    task_object = import_object.tasks.last()
    logger = logging.getLogger(INFO_LOGGER)
    logger.info(f"Starting import with ID {import_object.pk} with description: {import_object.description}!")

    # create progress
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('importing dataset')
    show_progress.update_view(0)
    try:
        # retrieve file path from object
        file_path = import_object.file.path
        ds = Dataset(file_path, import_object.index, show_progress=show_progress, separator=import_object.separator, meta=import_object)
        errors = ds.import_dataset()
        # update errors
        if errors:
            logging.getLogger(ERROR_LOGGER).exception(errors)
            show_progress.update_errors(errors)

        # update num_documents
        import_object.num_documents = ds.num_records
        import_object.num_documents_success = ds.num_records_success
        import_object.save()

        # add imported index to project indices
        logger.info(f"Creating index records for the database for task ID: '{import_object.pk}' with description: '{import_object.description}'!")
        project_obj = import_object.project
        index, is_created = Index.objects.get_or_create(name=import_object.index, defaults={"added_by": import_object.author.username})
        project_obj.indices.add(index)
        project_obj.save()
        # declare the job done
        task_object.complete()
        return True

    except Exception as e:
        # declare the job failed
        task_object.handle_failed_task(e)
        raise e
