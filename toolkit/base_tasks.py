import celery
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from toolkit.tools.logger import Logger


class BaseTask(celery.Task):
    """Usable for rewriting common Task logic. Reference in the base= parameter in the Task decorator"""


    def on_failure(self, exc, task_id, args, kwargs, einfo):
        Logger().error(f'Celery Task {task_id} failed', exc_info=exc)
        super(BaseTask, self).on_failure(exc, task_id, args, kwargs, einfo)


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


# TODO Make this into something more generic.
# Only logs the error message instead of the whole Traceback.
# At the moment only useable with MLPWorker.
class QuietTransactionAwareTask(TransactionAwareTask):
    exception_cache = set()


    def on_failure(self, exc, task_id, args, kwargs, einfo):

        # Deleting the MLP Worker Object is used to stop the task.
        # However, the default behavior is to log out every exception and every document in MLP produces it.
        # So we keep a count of which MLP worker id's we've seen so far, log out the first instance of failure
        # and ignore the rest.
        if isinstance(exc, ObjectDoesNotExist):
            mlp_id = kwargs.get("mlp_id", None)
            if mlp_id and mlp_id not in self.exception_cache:
                self.exception_cache.add(mlp_id)
                Logger().error(f'Celery Task {task_id} with kwargs {kwargs} failed with "{str(exc)}"! User deletion/cancellation likely, ignoring upcoming duplicate exceptions.')
                super(BaseTask, self).on_failure(exc, task_id, args, kwargs, einfo)
        else:
            Logger().error(f'Celery Task {task_id} failed with "{str(exc)}"!')
            super(BaseTask, self).on_failure(exc, task_id, args, kwargs, einfo)
