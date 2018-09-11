
from task_manager.models import Task


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
		r = Task.objects.get(pk=self.model_pk)
		r.status = Task.STATUS_RUNNING
		r.progress = percentage
		r.progress_message = '{0} [{1}/{2}]'.format(self.step_messages[i], i + 1, self.n_total)
		r.save()
