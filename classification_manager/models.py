from django.db import models
from django.contrib.auth.models import User

from corpus_tool.models import Search

MAX_STR_LEN = 200
MAX_INT_LEN = 10


class ModelClassification(models.Model):

    run_description = models.CharField(max_length=MAX_STR_LEN)
    run_status = models.CharField(max_length=MAX_STR_LEN)
    run_started = models.DateTimeField()
    run_completed = models.DateTimeField(null=True,blank=True)
    search = models.TextField(null=True, blank=True)
    fields = models.CharField(max_length=MAX_STR_LEN)
    user = models.ForeignKey(User)
    clf_arch = models.TextField(null=True, blank=True)
    score = models.TextField(null=True, blank=True)
    tag_label = models.CharField(max_length=MAX_STR_LEN)
    train_summary = models.CharField(max_length=MAX_STR_LEN)
    dataset_pk = models.CharField(max_length=MAX_STR_LEN)
