from typing import List

from django.contrib.auth.models import User
from django.db import models
from rest_framework.exceptions import ValidationError

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


    def filter_from_indices(self, indices: List[str] = None) -> List[str]:
        """
        Used in views where the user can select the indices they wish to use.
        Returns a list of index names from the ones that are in the project
        and in the indices parameter or all of the indices if it's None or empty.
        """
        if indices:
            legit_indices = self.indices.filter(name__in=indices)
            if not legit_indices:
                raise ValidationError(f"Inserted indices {indices} are not available to you.")

            indices = [index.name for index in legit_indices]
            return indices

        else:
            indices = self.indices.all()
            indices = [index.name for index in indices]
            return indices
