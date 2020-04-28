# Create your models here.
import json
import os
import secrets
from typing import List

from django.contrib.auth.models import User
from django.db import models
from django.dispatch import receiver

from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.document import ElasticDocument
from toolkit.elastic.models import Index
from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.settings import MODELS_DIR
from toolkit.topic_analyzer.choices import CLUSTERING_ALGORITHMS, VECTORIZERS
from toolkit.tools.text_processor import StopWords


class Cluster(models.Model):
    cluster_id = models.TextField()
    document_ids = models.TextField(default="[]")
    fields = models.TextField(default="[]")
    display_fields = models.TextField(default="[]")
    indices = models.TextField(default="[]")
    significant_words = models.TextField(default="[]")
    intracluster_similarity = models.FloatField()

    @staticmethod
    def get_significant_words(indices: List[str], fields: List[str], document_ids: List[str], stop_words: List = None):
        """
        This is a helper function to parse all the given fields and use the document_ids
        as input to make a significant_words aggregation.
        Args:
            stop_words: Optional parameter to remove stopwords from the results.
            indices: Indices from which to perform the aggregation.
            fields: From which fields can you get the text content needed for comparison.
            document_ids: IDs of the documents you want to use as baseline for the aggregation.

        Returns: List of dictionaries with the signifanct word and how many times it occurs in the documents.

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
                sw = ea.get_significant_words(document_ids=unique_ids, field=field, stop_words=stop_words)
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


    def generate_name(self, name="document_embedding"):
        return os.path.join(MODELS_DIR, 'embedding', f'{name}_{str(self.pk)}_{secrets.token_hex(10)}')


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]


    def train(self):
        from toolkit.topic_analyzer.tasks import train_cluster

        new_task = Task.objects.create(clusteringresult=self, status='created')
        self.task = new_task
        self.save()

        train_cluster(self.id)


@receiver(models.signals.post_delete, sender=ClusteringResult)
def auto_delete_file_on_delete(sender, instance: ClusteringResult, **kwargs):
    """
    Delete resources on the file-system upon tagger deletion.
    Triggered on individual-queryset Tagger deletion and the deletion
    of a TaggerGroup.
    """
    if instance.vector_model:
        if os.path.isfile(instance.vector_model.path):
            os.remove(instance.vector_model.path)
