import json
import uuid

from django.db import models
from django.utils.timezone import now

from toolkit.constants import MAX_DESC_LEN
from toolkit.helper_functions import avoid_db_timeout


class Task(models.Model):
    STATUS_CREATED = 'created'
    STATUS_QUEUED = 'queued'
    STATUS_RUNNING = 'running'
    STATUS_UPDATING = 'updating'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_FAILED = 'failed'

    TYPE_TRAIN = 'train'
    TYPE_APPLY = 'apply'
    TYPE_IMPORT = 'import'

    task_type = models.CharField(max_length=MAX_DESC_LEN, default=TYPE_TRAIN)
    status = models.CharField(max_length=MAX_DESC_LEN)
    num_processed = models.IntegerField(default=0)
    total = models.IntegerField(default=0, help_text="Total amount of documents/items that are tracked with this model.")
    step = models.CharField(max_length=MAX_DESC_LEN, default='')
    errors = models.TextField(default='[]')
    time_started = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(null=True, auto_now=True)
    time_completed = models.DateTimeField(null=True, blank=True, default=None)
    authtoken_hash = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)


    @property
    def progress(self):
        progress = self.num_processed / self.total if self.total != 0 else 0
        progress = progress * 100
        return round(progress, 2)


    @avoid_db_timeout
    def update_status(self, status: str):
        self.status = status
        self.save()


    @avoid_db_timeout
    def update_step(self, step: str):
        self.step = step
        self.save()


    @avoid_db_timeout
    def add_error(self, error: str):
        errors = json.loads(self.errors)
        errors = errors + [error]
        unique_errors = list(set(errors))
        self.errors = json.dumps(unique_errors, ensure_ascii=False)
        self.save()


    @avoid_db_timeout
    def complete(self):
        self.status = Task.STATUS_COMPLETED
        self.time_completed = now()
        self.step = ""
        self.save()
