import celery
from toolkit.tools.logger import Logger

class BaseTask(celery.Task):
    '''Usable for rewriting common Task logic. Reference in the base= parameter in the Task decorator'''

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        Logger().error(f'Celery Task {task_id} failed', exc_info=exc)
