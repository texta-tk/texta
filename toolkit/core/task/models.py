from django.db import models
from django.utils.timezone import now
from toolkit.constants import MAX_DESC_LEN

class Task(models.Model):
    STATUS_CREATED = 'created'
    STATUS_QUEUED = 'queued'
    STATUS_RUNNING = 'running'
    STATUS_UPDATING = 'updating'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_FAILED = 'failed'

    status = models.CharField(max_length=MAX_DESC_LEN)
    progress = models.FloatField(default=0.0)
    num_processed = models.IntegerField(default=0)
    step = models.CharField(max_length=MAX_DESC_LEN, default='')
    errors = models.CharField(max_length=MAX_DESC_LEN*100, default='')
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

    def update_process_iteration(self, total, step_prefix, num_processed=False):
        '''Step based process reporting'''
        # # Optionally override current num_processed
        # self.num_processed = num_processed if num_processed else self.num_processed
        # Update step
        self.num_processed += 1
        # Calculate percentage
        self.progress = (self.num_processed / total) * 100
        self.step = f'{step_prefix} (progress: {self.num_processed}/{total})'
        self.save()
