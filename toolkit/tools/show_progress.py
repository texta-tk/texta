from django.db.models import F

from toolkit.core.task.models import Task
from toolkit.helper_functions import avoid_db_timeout


class ShowProgress(object):
    """ Show model training progress"""


    def __init__(self, task: Task, multiplier=None):
        self.n_total = None
        self.n_count = 0
        self.task_id = task.id
        self.multiplier = multiplier
        self.step = ''


    @avoid_db_timeout
    def set_total(self, total: int):
        task: Task = Task.objects.select_for_update().get(pk=self.task_id)
        self.n_total = total
        task.total = total
        task.save()


    # This function only exists for backwards compatibility reasons, since
    # it's used in multiple packages like ElasticSearcher in texta-elastic-tools.
    # Meant to increase the count in ShowProgress while also saving it to the DB.
    def update(self, amount: int):
        self.add_progress(amount)


    # This function only exists for backwards compatibility reasons, since
    # it's used in multiple packages like ElasticSearcher in texta-elastic-tools.
    # Meant to zero out progress in most places.
    def update_view(self, percentage: int):
        amount = int(percentage)
        self.n_count = amount
        self.set_progress(amount)


    @avoid_db_timeout
    def update_step(self, step: str):
        task: Task = Task.objects.select_for_update().get(pk=self.task_id)
        task.step = step
        task.save()


    @avoid_db_timeout
    def add_progress(self, count: int):
        task: Task = Task.objects.select_for_update().get(pk=self.task_id)
        if task.status != task.STATUS_RUNNING:
            task.update_status(task.STATUS_RUNNING)

        # Using F() makes the addition on the DB side.
        task.num_processed = F('num_processed') + count
        self.n_count += count
        task.save()


    @avoid_db_timeout
    def set_progress(self, amount: int = 0):
        """Sets the progress in the task to zero when starting a new step."""
        task: Task = Task.objects.select_for_update().get(pk=self.task_id)
        task.num_processed = amount
        self.n_count = amount
        task.save()
