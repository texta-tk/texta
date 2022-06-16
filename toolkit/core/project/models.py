import json
from typing import List

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Count
from rest_framework.exceptions import ValidationError
from texta_elastic.core import ElasticCore

from toolkit.constants import MAX_DESC_LEN


class Project(models.Model):
    from toolkit.elastic.index.models import Index

    title = models.CharField(max_length=MAX_DESC_LEN)
    author = models.ForeignKey(User, on_delete=models.CASCADE, default=1)
    users = models.ManyToManyField(User, related_name="project_users")
    indices = models.ManyToManyField(Index, default=None)
    administrators = models.ManyToManyField(User, related_name="administrators")
    scopes = models.TextField(default=json.dumps([]))


    def get_indices(self) -> List[str]:
        indices = self.indices.filter(is_open=True)
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


    def get_available_or_all_project_indices(self, indices: List[str] = None) -> List[str]:
        """
        Used in views where the user can select the indices they wish to use.
        Returns a list of index names from the ones that are in the project
        and in the indices parameter or all of the indices if it's None or empty.

        If all the indices in question are closed, then it will also raise an error,
        otherwise it will return ONLY open indices.
        """
        if indices:
            indices = self.indices.filter(name__in=indices, is_open=True)
            if not indices:
                raise ValidationError(f"Inserted indices {indices} are not available to you.")
        else:
            indices = self.indices.all()

        indices = [index.name for index in indices]
        indices = list(set(indices))  # Leave only unique names just in case.
        return indices


    def get_resource_counts(self):
        set_names = {
            "lexicon", "torchtagger", "tagger", "taggergroup", "embedding", "clusteringresult", "regextagger", "regextaggergroup",
            "mlpworker", "reindexer", "anonymizer", "datasetimport", "berttagger", "indexsplitter", "evaluator", "applylangworker",
            "summarizer", "searchquerytagger", "searchfieldstagger", "applyesanalyzerworker", "crfextractor", "annotator", "rakunextractor",
        }

        # To avoid spamming singular count requests, we put all of them into a single aggregation.
        p = Project.objects.annotate(
            *[Count(app) for app in set_names]
        ).get(pk=self.pk)

        return {
            'num_lexicons': p.lexicon__count,
            'num_torchtaggers': p.torchtagger__count,
            'num_taggers': p.tagger__count,
            'num_tagger_groups': p.taggergroup__count,
            'num_embeddings': p.embedding__count,
            'num_clusterings': p.clusteringresult__count,
            'num_regex_taggers': p.regextagger__count,
            'num_regex_tagger_groups': p.regextaggergroup__count,
            'num_anonymizers': p.anonymizer__count,
            'num_mlp_workers': p.mlpworker__count,
            'num_reindexers': p.reindexer__count,
            'num_dataset_importers': p.datasetimport__count,
            'num_bert_taggers': p.berttagger__count,
            'num_index_splitters': p.indexsplitter__count,
            'num_evaluators': p.evaluator__count,
            'num_lang_detectors': p.applylangworker__count,
            'num_summarizers': p.summarizer__count,
            'num_search_query_taggers': p.searchquerytagger__count,
            'num_search_fields_taggers': p.searchfieldstagger__count,
            'num_elastic_analyzers': p.applyesanalyzerworker__count,
            'num_rakun_keyword_extractors': p.rakunextractor__count,
            'num_crf_extractors': p.crfextractor__count,
            'num_annotators': p.annotator__count
        }
