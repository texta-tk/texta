import json
import logging

from toolkit.core.task.models import Task
from toolkit.settings import ERROR_LOGGER


class ShowProgress(object):
    """ Show model training progress
    """


    def __init__(self, task, multiplier=None):
        self.n_total = None
        self.n_count = 0
        self.task_id = task.id
        self.multiplier = multiplier
        self.step = ''


    def set_total(self, total):
        self.n_count = 0
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
        task = Task.objects.get(pk=self.task_id)
        if task.status != task.STATUS_RUNNING:
            task.update_status(task.STATUS_RUNNING)
        task.update_progress(percentage, self.step)


    def update_errors(self, error):
        task = Task.objects.get(pk=self.task_id)

        try:
            errors_json = json.loads(task.errors)
        except Exception as e:
            logging.getLogger(ERROR_LOGGER).exception(e)
            errors_json = []

        errors_json.append('Error at {0}: {1}'.format(self.step, error))
        task.errors = json.dumps(errors_json)
        task.save()
