import logging
import celery
from toolkit.settings import ERROR_LOGGER

class BaseTask(celery.Task):
    '''Usable for rewriting common Task logic. Reference in the base= parameter in the Task decorator'''

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logging.getLogger(ERROR_LOGGER).error(f'Celery Task {task_id} failed'.format(task_id), exc_info=exc)
