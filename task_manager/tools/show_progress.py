
from task_manager.models import Task


class ShowProgress(object):
    """ Show model training progress
    """

    def __init__(self, task_pk, multiplier=None):
        self.n_total = None
        self.n_count = 0
        self.task_pk = task_pk
        self.multiplier = multiplier

    def set_total(self, total):
        self.n_total = total
        if self.multiplier:
            self.n_total = self.multiplier * total

    def update(self, amount):
        if amount == 0:
            return
        self.n_count += amount
        percentage = (100.0 * self.n_count) / self.n_total
        self.update_view(percentage)

    def update_view(self, percentage):
        r = Task.get_by_id(self.task_pk)
        r.status = Task.STATUS_RUNNING
        progress_message = '{0:3.0f} %'.format(percentage)
        r.update_progress(percentage, progress_message)
