from django.db import models
from django.contrib.auth.models import User

from searcher.models import Search

MAX_STR_LEN = 200
MAX_INT_LEN = 10


class ModelRun(models.Model):
    id = models.AutoField(primary_key=True)
    run_description   = models.CharField(max_length=MAX_STR_LEN)
    num_dimensions    = models.IntegerField()
    num_workers       = models.IntegerField()
    min_freq          = models.IntegerField()
    run_status        = models.CharField(max_length=MAX_STR_LEN)
    run_started       = models.DateTimeField()
    run_completed     = models.DateTimeField(null=True,blank=True)
    lexicon_size      = models.IntegerField(null=True,blank=True)
    search            = models.TextField(null=True,blank=True)
    fields            = models.CharField(max_length=MAX_STR_LEN)
    user              = models.ForeignKey(User, on_delete=models.CASCADE) # NEW PY REQUIREMENT
