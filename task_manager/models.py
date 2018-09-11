from datetime import datetime

from django.db import models
from django.contrib.auth.models import User

MAX_INT_LEN = 10
MAX_STR_LEN = 100


class Task(models.Model):

    STATUS_CREATED = 'created'
    STATUS_QUEUED = 'queued'
    STATUS_RUNNING = 'running'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELED = 'canceled'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = (
        (STATUS_CREATED, 'Created'),
        (STATUS_QUEUED, 'Queued'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELED, 'Canceled'),
        (STATUS_FAILED, 'Failed'),
    )

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    description = models.CharField(max_length=MAX_STR_LEN, default=None)
    task_type = models.CharField(max_length=MAX_STR_LEN, default=None)
    parameters = models.TextField(default=None)
    result = models.TextField(default=None)
    status = models.CharField(choices=STATUS_CHOICES, max_length=MAX_STR_LEN)
    progress = models.FloatField(default=0.0)
    progress_message = models.CharField(max_length=MAX_STR_LEN, default='')
    time_started = models.DateTimeField()
    last_update = models.DateTimeField(null=True, blank=True, default=None)
    time_completed = models.DateTimeField(null=True, blank=True, default=None)

    @staticmethod
    def get_by_id(task_id):
        return Task.objects.get(pk=task_id)

    def update_status(self, status, set_time_completed=False):
        self.status = status
        self.last_update = datetime.now()
        if set_time_completed:
            self.time_completed = datetime.now()
        self.save()
