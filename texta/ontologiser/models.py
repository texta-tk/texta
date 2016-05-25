from django.db import models
from django.contrib.auth.models import User

from ..conceptualiser.models import Concept

MAX_STR_LEN = 100


class Relation(models.Model):
    type = models.CharField(max_length=MAX_STR_LEN)
    source = models.ForeignKey(Concept,related_name='source_relation_set')
    target = models.ForeignKey(Concept,related_name='target_relation_set')
    author = models.ForeignKey(User,related_name='relation_author_relation_set') 