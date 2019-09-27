from django.db import models
from django.contrib.auth.models import User

from toolkit.core.project.models import Project
from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.constants import MAX_DESC_LEN

# Create your models here.
class Search(models.Model):
    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    # TextField saving JSON for saving front-end state
    query_constraints = models.TextField()

    def __str__(self):
        return self.query
