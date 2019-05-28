from django.db import models
from django.utils.timezone import now
from toolkit.core.constants import MAX_STR_LEN

class Task(models.Model):
    STATUS_CREATED = 'created'
    STATUS_QUEUED = 'queued'
    STATUS_RUNNING = 'running'
    STATUS_UPDATING = 'updating'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_FAILED = 'failed'

    status = models.CharField(max_length=MAX_STR_LEN)
    progress = models.FloatField(default=0.0)
    step = models.CharField(max_length=MAX_STR_LEN, default='')
    time_started = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(null=True, blank=True, default=None)
    time_completed = models.DateTimeField(null=True, blank=True, default=None)

    def update_status(self, status, set_time_completed=False):
        self.status = status
        self.last_update = now()
        if set_time_completed:
            self.time_completed = now()
        self.save()

    def update_progress(self, progress, step):
        self.progress = progress
        self.step = step
        self.last_update = now()
        self.save()
