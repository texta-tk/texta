import json
import logging
from django.db import models, transaction
from django.core import serializers
from django.core.validators import MinValueValidator
from django.db.models import CheckConstraint, Q
from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from django.contrib.auth.models import User
from toolkit.embedding.models import Embedding
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.elastic.tools.searcher import EMPTY_QUERY
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, INFO_LOGGER


class RakunExtractor(models.Model):
    MODEL_TYPE = 'rakun_extractor'
    MODEL_JSON_NAME = "model.json"

    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    indices = models.ManyToManyField(Index)
    fields = models.TextField(default=json.dumps([]))
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
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
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)

    class Meta:
        constraints = (
            # for checking in the DB
            CheckConstraint(
                check=Q(distance_threshold__gte=0.0),
                name='distance_threshold_min'),
        )

    def __str__(self):
        return self.description

    def to_json(self) -> dict:
        serialized = serializers.serialize('json', [self])
        json_obj = json.loads(serialized)[0]["fields"]
        del json_obj["project"]
        del json_obj["author"]
        del json_obj["task"]
        return json_obj

    def apply_rakun(self):
        new_task = Task.objects.create(rakunextractor=self, status='created')
        self.task = new_task
        self.save()
        from toolkit.rakun_keyword_extractor.tasks import start_rakun_task, apply_rakun_extractor_to_index
        logging.getLogger(INFO_LOGGER).info(f"Celery: Starting rakun keyword extractor: {self.to_json()}")
        chain = start_rakun_task.s() | apply_rakun_extractor_to_index.s()
        transaction.on_commit(lambda: chain.apply_async(args=(self.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE))
