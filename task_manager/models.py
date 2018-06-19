from django.db import models
from django.contrib.auth.models import User

MAX_INT_LEN = 10
MAX_STR_LEN = 100


class Task(models.Model):
    id             = models.AutoField(primary_key=True)
    user           = models.ForeignKey(User, on_delete=models.CASCADE)
    description    = models.CharField(max_length=MAX_STR_LEN, default=None)
    task_type      = models.CharField(max_length=MAX_STR_LEN, default=None)
    parameters     = models.TextField(default=None)
    result         = models.TextField(default=None)
    status         = models.CharField(max_length=MAX_STR_LEN)
    time_started   = models.DateTimeField()
    time_completed = models.DateTimeField(null=True, blank=True, default=None)
    

