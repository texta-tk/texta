from django.db import models
from django.contrib.auth.models import User

MAX_INT_LEN = 10
MAX_STR_LEN = 100

class Dataset(models.Model):
    index = models.CharField(max_length=MAX_STR_LEN)
    mapping = models.CharField(max_length=MAX_STR_LEN)
    author = models.ForeignKey(User)
    daterange = models.TextField()
