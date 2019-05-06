from picklefield.fields import PickledObjectField
from datetime import datetime
from django.db import models
from django.contrib.auth.models import User
import json
import uuid

MAX_INT_LEN = 10
MAX_STR_LEN = 100


class Task(models.Model):

    STATUS_CREATED = 'created'
    STATUS_QUEUED = 'queued'
    STATUS_RUNNING = 'running'
    STATUS_UPDATING = 'updating'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELED = 'canceled'
    STATUS_FAILED = 'failed'

    STATUS_DICT = {
        'STATUS_CREATED': 'created',
        'STATUS_QUEUED': 'queued',
        'STATUS_RUNNING': 'running',
        'STATUS_UPDATING': 'updating',
        'STATUS_COMPLETED': 'completed',
        'STATUS_CANCELED': 'canceled',
        'STATUS_FAILED': 'failed',
    }

    STATUS_CHOICES = (
        (STATUS_CREATED, 'Created'),
        (STATUS_QUEUED, 'Queued'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_UPDATING, 'Updating'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELED, 'Canceled'),
        (STATUS_FAILED, 'Failed'),
    )

    unique_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
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
    resources = PickledObjectField(null=True, default=None)

    @staticmethod
    def get_by_id(task_id):
        return Task.objects.get(pk=task_id)

    def update_status(self, status, set_time_completed=False):
        self.status = status
        self.last_update = datetime.now()
        if set_time_completed:
            self.time_completed = datetime.now()
        self.save()

    def is_running(self):
        return self.status == Task.STATUS_RUNNING

    def requeue_task(self):
        self.status = Task.STATUS_QUEUED
        self.progress = 0.0
        self.result = ''
        self.progress_message = ''
        self.time_completed = None
        self.last_update = datetime.now()
        self.save()

    def update_progress(self, progress, progress_message):
        self.progress = progress
        self.progress_message = progress_message
        self.last_update = datetime.now()
        self.save()

    def to_json(self):
        data = {
            'task_id': self.id,
            'user': self.user.username,
            'description': self.description,
            'task_type': self.task_type,
            'parameters': self.parameters,
            'result': self.result,
            'status': self.status,
            'progress': self.progress,
            'progress_message': self.progress_message,
            'time_started': str(self.time_started),
            'last_update': str(self.last_update),
            'time_completed': str(self.time_completed)
        }
        return data



class TagFeedback(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    document = models.TextField()
    tagger = models.ForeignKey(Task,on_delete=models.CASCADE)
    prediction = models.IntegerField(default=None)
    in_dataset = models.IntegerField(default=0)
    time_updated = models.DateTimeField(null=True, blank=True, default=None)

    @staticmethod
    def create(user, text_dict, tagger_id, prediction):
        feedback_log = TagFeedback()
        feedback_log.user = user
        feedback_log.document = json.dumps(text_dict)
        feedback_log.tagger = Task.objects.get(pk = int(tagger_id))
        feedback_log.prediction = prediction
        feedback_log.time_updated = datetime.now()
        feedback_log.save()
        return feedback_log
    
    @staticmethod
    def update(user, decision_id, prediction):
        feedback_log = TagFeedback.objects.get(pk = int(decision_id))
        feedback_log.user = user
        feedback_log.prediction = int(prediction)
        feedback_log.time_updated = datetime.now()
        feedback_log.save()
        return feedback_log

    def to_json(self):
        data = {
            'feedback_id': self.id,
            'user': self.user.username,
            'dataset_id': self.dataset_id,
            'document_id': self.document_id,
            'field': self.field,
            'tag': self.tag,
            'value': self.value,
            'last_update': str(self.time_updated)
        }
        return data
