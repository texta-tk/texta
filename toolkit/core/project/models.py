import json
from typing import List

from django.contrib.auth.models import User
from django.db import models
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

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    modified_at = models.DateTimeField(auto_now=True, null=True)


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
        proj = self
        return {
            'num_lexicons': proj.lexicon_set.count(),
            'num_torchtaggers': proj.torchtagger_set.count(),
            'num_taggers': proj.tagger_set.count(),
            'num_tagger_groups': proj.taggergroup_set.count(),
            'num_embeddings': proj.embedding_set.count(),
            'num_clusterings': proj.clusteringresult_set.count(),
            'num_regex_taggers': proj.regextagger_set.count(),
            'num_regex_tagger_groups': proj.regextaggergroup_set.count(),
            'num_anonymizers': proj.anonymizer_set.count(),
            'num_mlp_workers': proj.mlpworker_set.count(),
            'num_reindexers': proj.reindexer_set.count(),
            'num_dataset_importers': proj.datasetimport_set.count(),
            'num_bert_taggers': proj.berttagger_set.count(),
            'num_index_splitters': proj.indexsplitter_set.count(),
            'num_evaluators': proj.evaluator_set.count(),
            'num_lang_detectors': proj.applylangworker_set.count(),
            'num_summarizers': proj.summarizer_set.count(),
            'num_search_query_taggers': proj.searchquerytagger_set.count(),
            'num_search_fields_taggers': proj.searchfieldstagger_set.count(),
            'num_elastic_analyzers': proj.applyesanalyzerworker_set.count(),
            'num_rakun_keyword_extractors': proj.rakunextractor_set.count(),
            'num_crf_extractors': proj.crfextractor_set.count(),
            'num_annotators': proj.annotator_set.count()
        }
