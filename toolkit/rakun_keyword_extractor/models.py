import json
import logging
from typing import List

import regex as re
from django.contrib.auth.models import User
from django.core import serializers
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import CheckConstraint, Q
from mrakun import RakunDetector

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.embedding.models import Embedding
from toolkit.helper_functions import load_stop_words
from toolkit.model_constants import CommonModelMixin, FavoriteModelMixin
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, FACEBOOK_MODEL_SUFFIX, INFO_LOGGER


class RakunDetectorWrapper(RakunDetector):
    """
    A wrapper to fix Rakun compatability with Gensim4.
    """


    def calculate_embedding_distance(self, key1, key2):
        return self.model.similarity(key1, key2)


class RakunExtractor(FavoriteModelMixin, CommonModelMixin):
    MODEL_TYPE = 'rakun_extractor'
    MODEL_JSON_NAME = "model.json"

    distance_method = models.CharField(default="editdistance", max_length=MAX_DESC_LEN)
    distance_threshold = models.FloatField(validators=[MinValueValidator(0.0)], default=2.0, null=True)
    num_keywords = models.IntegerField(default=25, null=True)
    pair_diff_length = models.IntegerField(default=2, null=True)
    stopwords = models.TextField(default="[]", null=True)
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


    def __str__(self):
        return self.description


    def to_json(self) -> dict:
        serialized = serializers.serialize('json', [self])
        json_obj = json.loads(serialized)
        return json_obj


    def apply_rakun(self):
        new_task = Task.objects.create(rakunextractor=self, status=Task.STATUS_CREATED, task_type=Task.TYPE_APPLY)
        self.save()

        self.tasks.add(new_task)
        from toolkit.rakun_keyword_extractor.tasks import start_rakun_task, apply_rakun_extractor_to_index
        logging.getLogger(INFO_LOGGER).info(f"Celery: Starting rakun keyword extractor: {self.to_json()}")
        chain = start_rakun_task.s() | apply_rakun_extractor_to_index.s()
        transaction.on_commit(lambda: chain.apply_async(args=(self.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE))


    @property
    def num_tokens(self):
        if int(self.min_tokens) == int(self.max_tokens):
            num_tokens = [int(self.min_tokens)]
        else:
            num_tokens = [int(self.min_tokens), int(self.max_tokens)]
        return num_tokens


    @property
    def get_facebook_model(self):
        # load embedding if any
        if self.fasttext_embedding:
            embedding_model_path = str(self.fasttext_embedding.embedding_model)
            gensim_embedding_model_path = embedding_model_path + "_" + FACEBOOK_MODEL_SUFFIX
        else:
            gensim_embedding_model_path = None
        return gensim_embedding_model_path


    @property
    def hyperparameters(self):
        stop_words = load_stop_words(self.stopwords)
        HYPERPARAMETERS = {"distance_threshold": self.distance_threshold,
                           "distance_method": self.distance_method,
                           "pretrained_embedding_path": self.get_facebook_model,
                           "num_keywords": self.num_keywords,
                           "pair_diff_length": self.pair_diff_length,
                           "stopwords": stop_words,
                           "bigram_count_threshold": self.bigram_count_threshold,
                           "num_tokens": self.num_tokens,
                           "max_similar": self.max_similar,
                           "max_occurrence": self.max_occurrence,
                           "lemmatizer": None}
        return HYPERPARAMETERS


    def load_rakun_keyword_detector(self):
        HYPERPARAMETERS = self.hyperparameters
        keyword_detector = RakunDetectorWrapper(HYPERPARAMETERS)
        return keyword_detector


    def get_rakun_keywords(self, keyword_detector: RakunDetectorWrapper, texts: List[str], field_path: str, fact_name: str = "", fact_value: str = "", add_spans: bool = False):
        new_facts = []
        for text in texts:
            results = keyword_detector.find_keywords(text, input_type="text")
            for result in results:
                rakun_keyword = result[0]
                probability = result[1]

                if add_spans:
                    # Find all positions of the keyword in text
                    spans = [[m.start(), m.end()] for m in
                             re.finditer(re.escape(rakun_keyword), text, re.IGNORECASE)]
                else:
                    spans = [[0, 0]]

                for span in spans:
                    new_rakun = {
                        "fact": fact_name,
                        "str_val": result[0],
                        "spans": json.dumps([span]),
                        "doc_path": field_path,
                        "probability": probability
                    }
                    new_facts.append(new_rakun)
        return new_facts
