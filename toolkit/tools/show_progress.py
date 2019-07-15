from toolkit.core.task.models import Task
import json


class ShowProgress(object):
    """ Show model training progress
    """

    def __init__(self, task, multiplier=None):
        self.n_total = None
        self.n_count = 0
        self.task = task
        self.multiplier = multiplier
        self.step = ''

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
        if self.task.status != self.task.STATUS_RUNNING:
            self.task.update_status(self.task.STATUS_RUNNING)
        self.task.update_progress(percentage, self.step)

    def update_errors(self, error):
        try:
            errors_json = json.loads(self.task.errors)
        except:
            errors_json = []
        errors_json.append('Error at {0}: {1}'.format(self.step, error))
        self.task.errors = json.dumps(errors_json)
