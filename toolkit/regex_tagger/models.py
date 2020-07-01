from django.contrib.auth.models import User
from django.db import models

from toolkit.core.project.models import Project
from toolkit.constants import MAX_DESC_LEN
from .choices import OPERATOR_CHOICES, MATCH_TYPE_CHOICES


class RegexTagger(models.Model):
    MODEL_TYPE = 'regex_tagger'
    #MODEL_JSON_NAME = "model.json"

    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)

    lexicon = models.TextField(default='')
    counter_lexicon = models.TextField(default='')
    operator = models.CharField(max_length=25, default=OPERATOR_CHOICES[0][0])
    match_type = models.CharField(max_length=25, default=MATCH_TYPE_CHOICES[0][0])
    required_words = models.FloatField(default=0.0)
    phrase_slop = models.IntegerField(default=0)
    counter_slop = models.IntegerField(default=0)
    return_fuzzy_match = models.BooleanField(default=True)
