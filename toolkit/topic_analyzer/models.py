# Create your models here.
import json
import logging
import os
import pathlib
import secrets
from typing import List

from django.contrib.auth.models import User
from django.db import models, transaction
from django.dispatch import receiver

from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.document import ElasticDocument
from toolkit.elastic.models import Index
from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.embedding.models import Embedding
from toolkit.settings import BASE_DIR, ERROR_LOGGER, RELATIVE_MODELS_PATH
from toolkit.tools.text_processor import StopWords
from toolkit.topic_analyzer.choices import CLUSTERING_ALGORITHMS, VECTORIZERS


class Cluster(models.Model):
    cluster_id = models.TextField()
    document_ids = models.TextField(default="[]")
    fields = models.TextField(default="[]")
    display_fields = models.TextField(default="[]")
    indices = models.TextField(default="[]")
    significant_words = models.TextField(default="[]")
    intracluster_similarity = models.FloatField()


    @staticmethod
    def get_significant_words(indices: List[str], fields: List[str], document_ids: List[str], stop_words: List = None, exclude=""):
        """
        This is a helper function to parse all the given fields and use the document_ids
        as input to make a significant_words aggregation.
        Args:
            exclude: Regex compatible string for which words to exclude, uses the exclude parameter of Elasticsearch aggregations.
            stop_words: Optional parameter to remove stopwords from the results.
            indices: Indices from which to perform the aggregation.
            fields: From which fields can you get the text content needed for comparison.
            document_ids: IDs of the documents you want to use as baseline for the aggregation.

        Returns: List of dictionaries with the signifcant word and how many times it occurs in the documents.

        """
        ed = ElasticDocument("*")
        ea = ElasticAggregator(indices=indices)

        stop_words = StopWords._get_stop_words(custom_stop_words=stop_words)
        # Validate that those documents exist.
        validated_docs: List[dict] = ed.get_bulk(document_ids)
        if validated_docs:
            unique_ids = list(set([index["_id"] for index in validated_docs]))
            significant_words = []
            for field in fields:
                sw = ea.get_significant_words(document_ids=unique_ids, field=field, stop_words=stop_words, exclude=exclude)
                significant_words += sw

            return significant_words
        else:
            return []


    def get_document_count(self):
        documents = json.loads(self.document_ids)
        return len(documents)


class ClusteringResult(models.Model):
    description = models.TextField()
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    clustering_algorithm = models.CharField(max_length=100, default=CLUSTERING_ALGORITHMS[0][0])
    fields = models.TextField(default="[]")
    display_fields = models.TextField(default="[]")
    vectorizer = models.TextField(default=VECTORIZERS[0][0])
    embedding = models.ForeignKey(Embedding, on_delete=models.SET_NULL, null=True, default=None)

    num_topics = models.IntegerField(default=50)
    num_cluster = models.IntegerField(default=10)
    num_dims = models.IntegerField(default=1000)
    document_limit = models.IntegerField(default=100)

    use_lsi = models.BooleanField(default=False)

    # JSON parsable fields.
    stop_words = models.TextField(default="[]")
    ignored_ids = models.TextField(default="[]")

    cluster_result = models.ManyToManyField(Cluster)
    indices = models.ManyToManyField(Index)
    vector_model = models.FileField(null=True, verbose_name='', default=None)

    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)

    significant_words_filter = models.CharField(max_length=100, default="[0-9]+")


    def generate_name(self, name="document_embedding"):
        """
        Do not change this carelessly as import/export functionality depends on this.
        Returns full and relative filepaths for the intended models.
        Args:
            name: Name for the model to distinguish itself from others in the same directory.

        Returns: Full and relative file paths, full for saving the model object and relative for actual DB storage.
        """
        model_file_name = f'{name}_{str(self.pk)}_{secrets.token_hex(10)}'
        full_path = pathlib.Path(BASE_DIR) / RELATIVE_MODELS_PATH / "embedding" / model_file_name
        relative_path = pathlib.Path(RELATIVE_MODELS_PATH) / "embedding" / model_file_name
        return str(full_path), str(relative_path)


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]


    def train(self):
        # Ensure nothing is saved into the DB if anything within this
        # context manager throws an exception.
        with transaction.atomic():
            from toolkit.helper_functions import apply_celery_task
            from toolkit.topic_analyzer.tasks import start_clustering_task, perform_data_clustering, save_clustering_results, finish_clustering_task

            new_task = Task.objects.create(clusteringresult=self, status='created')
            self.task = new_task
            self.save()

            # To avoid Celery race conditions in which the task is started in celery
            # BEFORE the actual record is saved into the database as it is not automatically
            # waited for.
            chain = start_clustering_task.s() | perform_data_clustering.s() | save_clustering_results.s() | finish_clustering_task.s()
            transaction.on_commit(
                lambda: apply_celery_task(chain, self.id)
            )


@receiver(models.signals.post_delete, sender=ClusteringResult)
def auto_delete_file_on_delete(sender, instance: ClusteringResult, **kwargs):
    """
    Delete resources on the file-system upon cluster deletion.

    """
    try:
        if instance.vector_model:
            if os.path.isfile(instance.vector_model.path):
                os.remove(instance.vector_model.path)
    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
