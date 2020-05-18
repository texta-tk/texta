import celery
from django.db import transaction

from toolkit.tools.logger import Logger


class BaseTask(celery.Task):
    """Usable for rewriting common Task logic. Reference in the base= parameter in the Task decorator"""


    def on_failure(self, exc, task_id, args, kwargs, einfo):
        Logger().error(f'Celery Task {task_id} failed', exc_info=exc)


class TransactionAwareTask(BaseTask):
    """
    Task class which is aware of django db transactions and only executes tasks
    after transaction has been committed
    """
    abstract = True


    def apply_async(self, *args, **kwargs):
        """
        Unlike the default task in celery, this task does not return an async
        result
        """
        with transaction.atomic():
            transaction.on_commit(
                lambda: super(TransactionAwareTask, self).apply_async(
                    *args, **kwargs))
