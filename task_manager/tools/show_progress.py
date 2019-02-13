
from task_manager.models import Task
from .data_manager import TaskCanceledException


class ShowProgress(object):
    """ Show model training progress
    """

    def __init__(self, task_pk, multiplier=None):
        self.n_total = None
        self.n_count = 0
        self.task_pk = task_pk
        self.multiplier = multiplier
        self.step = None

    def set_total(self, total):
        self.n_total = total
        if self.multiplier:
            self.n_total = self.multiplier * total

    def update_step(self, step):
        self.step = step

    def update(self, amount):
        if amount == 0:
            return
        self.n_count += amount
        percentage = (100.0 * self.n_count) / self.n_total
        self.update_view(percentage)

    def update_view(self, percentage):
        r = Task.get_by_id(self.task_pk)
        # Check if task was canceled
        if r.status == Task.STATUS_CANCELED:
            raise TaskCanceledException()
        r.status = Task.STATUS_RUNNING
        progress_message = '{0:3.0f} %'.format(percentage)
        if self.step:
            progress_message = '{1}: {0}'.format(progress_message, self.step)
        r.update_progress(percentage, progress_message)
