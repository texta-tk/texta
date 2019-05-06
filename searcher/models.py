from django.db import models
from django.contrib.auth.models import User

from permission_admin.models import Dataset

MAX_INT_LEN = 10
MAX_STR_LEN = 100


class Search(models.Model):
    search_content = models.TextField(default='') # JSON string
    description = models.CharField(max_length=MAX_STR_LEN)
    datasets = models.ManyToManyField(Dataset, blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    query = models.TextField(default='')

    def __str__(self):
        return self.query
