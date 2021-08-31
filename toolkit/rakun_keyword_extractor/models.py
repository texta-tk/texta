from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import CheckConstraint, Q
from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from django.contrib.auth.models import User
from toolkit.embedding.models import Embedding


class RakunExtractor(models.Model):
    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    distance_threshold = models.FloatField(validators=[MinValueValidator(0.0)], default=2.0, null=True)
    num_keywords = models.IntegerField(default=25, null=True)
    pair_diff_length = models.IntegerField(default=2, null=True)
    stopwords = models.CharField(default=[], null=True, max_length=MAX_DESC_LEN)
    bigram_count_threshold = models.IntegerField(default=2, null=True)
    min_tokens = models.IntegerField(default=1, null=True)
    max_tokens = models.IntegerField(default=1, null=True)
    max_similar = models.IntegerField(default=3, null=True)
    max_occurrence = models.IntegerField(default=3, null=True)
    fasttext_embedding = models.ForeignKey(Embedding, on_delete=models.SET_NULL, null=True, default=None)

    class Meta:
        constraints = (
            # for checking in the DB
            CheckConstraint(
                check=Q(distance_threshold__gte=0.0),
                name='distance_threshold_min'),
        )
