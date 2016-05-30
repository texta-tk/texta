from django.db import models
from django.contrib.auth.models import User

from ..permission_admin.models import Dataset

MAX_INT_LEN = 10
MAX_STR_LEN = 100


class Search(models.Model):
    description = models.CharField(max_length=MAX_STR_LEN)
    dataset = models.ForeignKey(Dataset)
    author = models.ForeignKey(User)
    query = models.TextField()

    def __str__(self):
        return self.query
