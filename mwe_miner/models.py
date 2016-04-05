from django.db import models
from django.contrib.auth.models import User

MAX_STR_LEN = 200
MAX_INT_LEN = 10

class Run(models.Model):
    minimum_frequency = models.IntegerField()
    maximum_length    = models.IntegerField()
    minimum_length    = models.IntegerField()
    run_status        = models.CharField(max_length=MAX_STR_LEN)
    run_started       = models.DateTimeField()
    run_completed     = models.DateTimeField(null=True, blank=True)
    user              = models.ForeignKey(User)
    description       = models.CharField(max_length=MAX_STR_LEN)
    results           = models.TextField()
