from django.contrib.auth.models import User
from django.db import models

from toolkit.constants import MAX_DESC_LEN
from toolkit.elastic.core import ElasticCore


class Project(models.Model):
    from toolkit.elastic.models import Index

    title = models.CharField(max_length=MAX_DESC_LEN)
    users = models.ManyToManyField(User, related_name="project_users")
    indices = models.ManyToManyField(Index, default=None)


    def get_indices(self):
        indices = self.indices.all()
        return [index.name for index in indices]


    def __str__(self):
        return self.title


    def get_elastic_fields(self, path_list=False):
        """
        Method for retrieving all valid Elasticsearch fields for a given project.
        """
        if not self.get_indices():
            return []
        field_data = ElasticCore().get_fields(indices=self.get_indices())
        if path_list:
            field_data = [field["path"] for field in field_data]
        return field_data
