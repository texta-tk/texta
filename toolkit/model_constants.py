import json
from typing import List

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.serializer_constants import BULK_SIZE_HELPTEXT, ES_TIMEOUT_HELPTEXT, INDICES_HELPTEXT
from toolkit.settings import DESCRIPTION_CHAR_LIMIT, ES_BULK_SIZE_MAX, ES_TIMEOUT_MAX


class CommonModelMixin(models.Model):
    description = models.CharField(max_length=DESCRIPTION_CHAR_LIMIT)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    tasks = models.ManyToManyField(Task)


    class Meta:
        abstract = True


class TaskModel(CommonModelMixin):
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    indices = models.ManyToManyField(Index, default=[], help_text=INDICES_HELPTEXT)
    fields = models.TextField(default=json.dumps([]))

    bulk_size = models.IntegerField(default=100, help_text=BULK_SIZE_HELPTEXT, validators=[MinValueValidator(1), MaxValueValidator(ES_BULK_SIZE_MAX)])
    es_timeout = models.IntegerField(default=10, help_text=ES_TIMEOUT_HELPTEXT, validators=[MinValueValidator(1), MaxValueValidator(ES_TIMEOUT_MAX)])


    class Meta:
        abstract = True


    def get_available_or_all_indices(self, indices: List[str] = None) -> List[str]:
        """
        Used in views where the user can select the indices they wish to use.
        Returns a list of index names from the ones that are in the project
        and in the indices parameter or all of the indices if it's None or empty.
        """
        if indices:
            indices = self.indices.filter(name__in=indices, is_open=True)
            if not indices:
                indices = self.project.indices.all()
        else:
            indices = self.indices.all()

        indices = [index.name for index in indices]
        indices = list(set(indices))  # Leave only unique names just in case.
        return indices


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]


    def __str__(self):
        return '{0} - {1}'.format(self.pk, self.description)


class FavoriteModelMixin(models.Model):
    favorited_users = models.ManyToManyField(User, related_name="%(app_label)s_%(class)s_favorited_user")


    class Meta:
        abstract = True
