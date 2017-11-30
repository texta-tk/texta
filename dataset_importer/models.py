# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.contrib.auth.models import User


class DatasetImport(models.Model):
    source_type = models.CharField(max_length=32)
    source_name = models.CharField(max_length=256)
    elastic_index = models.CharField(max_length=64)
    elastic_mapping = models.CharField(max_length=64)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True)
    user = models.ForeignKey(User, related_name='dataset_import_user_relation_set')
    status = models.CharField(max_length=32)
    processed_documents = models.BigIntegerField(default=0)
    total_documents = models.BigIntegerField(default=0)
    finished = models.BooleanField(default=False)
