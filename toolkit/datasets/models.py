from django.db import models
from django.contrib.auth.models import User
from toolkit.core.models import Project


MAX_INT_LEN = 10
MAX_STR_LEN = 100


class Dataset(models.Model):
    id = models.AutoField(primary_key=True)
    index = models.CharField(max_length=MAX_STR_LEN)
    mapping = models.CharField(max_length=MAX_STR_LEN)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)


class DatasetImport(models.Model):
    source_type = models.CharField(max_length=32)
    source_name = models.CharField(max_length=256)
    elastic_index = models.CharField(max_length=64)
    elastic_mapping = models.CharField(max_length=64)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dataset_import_user_relation_set') 
    status = models.CharField(max_length=32)
    processed_documents = models.BigIntegerField(default=0)
    total_documents = models.BigIntegerField(default=0)
    finished = models.BooleanField(default=False)
    must_sync = models.BooleanField(default=False)
    json_parameters = models.CharField(max_length=1024, default='')
    errors = models.CharField(max_length=1024, default='')

    def __str__(self):
        return self.source_name
