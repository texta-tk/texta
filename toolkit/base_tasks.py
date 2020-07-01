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
    after transaction has been committed.
    """
    abstract = True


    def apply_async(self, *args, **kwargs):
        """
        NOTES:
        * Unlike the default task in celery, this task does not return an async
        result.
        * When calling out a task that has this class set as its base_class, all the parameters
        of apply_async will be passed here, including the args, kwargs and queue values.
        * When a task that subclasses this is part of the chain, this transaction will not apply on them
        which is why it would be recommended to run chains through the on_commit transaction to avoid situations
        where Celery starts a task before a DB record is actually saved into the database resulting in "Object with ID not found etc"
        """
        with transaction.atomic():
            transaction.on_commit(
                lambda: super(TransactionAwareTask, self).apply_async(
                    *args, **kwargs))
