from django.db import models

from toolkit.constants import MAX_DESC_LEN


class EnvironmentVariable(models.Model):
    name = models.CharField(max_length=MAX_DESC_LEN)
    value = models.CharField(max_length=MAX_DESC_LEN)
