
from task_manager.models import Task
from .data_manager import TaskCanceledException


class ShowSteps(object):
    """ Show model training progress
    """

    def __init__(self, model_pk, steps):
        self.step_messages = steps
        self.n_total = len(steps)
        self.n_step = 0
        self.model_pk = model_pk

    def update(self, step):
        self.n_step = step
        self.update_view()

    def update_view(self):
        i = self.n_step
        percentage = (100.0 * i) / self.n_total
        r = Task.get_by_id(self.model_pk)
        # Check if task was canceled
        if r.status == Task.STATUS_CANCELED:
            raise TaskCanceledException()
        r.status = Task.STATUS_RUNNING
        progress_message = '{0} [{1}/{2}]'.format(self.step_messages[i], i + 1, self.n_total)
        r.update_progress(percentage, progress_message)
