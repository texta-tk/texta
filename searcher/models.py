from django.db import models
from django.contrib.auth.models import User

from permission_admin.models import Dataset

MAX_INT_LEN = 10
MAX_STR_LEN = 100


class Search(models.Model):
    id = models.AutoField(primary_key=True)
    search_content = models.TextField(default='')
    description = models.CharField(max_length=MAX_STR_LEN)
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE) # NEW PY REQUIREMENT
    author = models.ForeignKey(User, on_delete=models.CASCADE) # NEW PY REQUIREMENT
    query = models.TextField(default='')

    def __str__(self):
        return self.query

