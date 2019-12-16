from django.db import models
from django.contrib.auth.models import User
import json

from toolkit.constants import MAX_DESC_LEN
from toolkit.elastic.core import ElasticCore
from toolkit.multiselectfield import PatchedMultiSelectField as MultiSelectField


class Project(models.Model):
    title = models.CharField(max_length=MAX_DESC_LEN)
    users = models.ManyToManyField(User, related_name="project_users")
    indices = MultiSelectField(default=None)

    def __str__(self):
        return self.title

    def get_elastic_fields(self, path_list=False):
        """
        Method for retrieving all valid Elasticsearch fields for a given project.
        """
        if not self.indices:
            return []
        field_data = ElasticCore().get_fields(indices=self.indices)
        if path_list:
            field_data = [field["path"] for field in field_data]
        return field_data

    def save(self, add_indices=False, *args, **kwargs):
        if add_indices:
            self.indices = add_indices
        super(Project, self).save(*args, **kwargs)
