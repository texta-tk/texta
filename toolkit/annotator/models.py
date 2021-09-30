import json
from typing import List

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
# Create your models here.
from django.db.models import F

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from toolkit.elastic.index.models import Index
from toolkit.elastic.tools.document import ESDocObject
from toolkit.elastic.tools.searcher import EMPTY_QUERY
from toolkit.serializer_constants import BULK_SIZE_HELPTEXT, DESCRIPTION_HELPTEXT, ES_TIMEOUT_HELPTEXT, INDICES_HELPTEXT, PROJECT_HELPTEXT, QUERY_HELPTEXT


ANNOTATION_CHOICES = (
    ("binary", "binary"),
    ("multilabel", "multilabel"),
    ("entity", "entity")
)

CHAR_LIMIT = 100
ES_TIMEOUT_MAX = 100
ES_BULK_SIZE_MAX = 500


class Label(models.Model):
    value = models.CharField(max_length=CHAR_LIMIT)


class LabelValue(models.Model):
    value = models.CharField(max_length=CHAR_LIMIT)


class Labelset(models.Model):
    label = models.ForeignKey(Label, on_delete=models.CASCADE)
    values = models.ManyToManyField(LabelValue)


class BinaryAnnotatorConfiguration(models.Model):
    fact_name = models.CharField(max_length=CHAR_LIMIT)
    pos_value = models.CharField(max_length=CHAR_LIMIT)
    neg_value = models.CharField(max_length=CHAR_LIMIT)


class EntityAnnotatorConfiguration(models.Model):
    fact_name = models.CharField(max_length=CHAR_LIMIT, help_text="Name of the fact which will be added.")


class MultilabelAnnotatorConfiguration(models.Model):
    labelset = models.ForeignKey(Labelset, on_delete=models.CASCADE)


class Annotator(models.Model):
    description = models.CharField(max_length=MAX_DESC_LEN, help_text=DESCRIPTION_HELPTEXT)

    project = models.ForeignKey(Project, on_delete=models.CASCADE, help_text=PROJECT_HELPTEXT)
    query = models.TextField(default=json.dumps(EMPTY_QUERY), help_text=QUERY_HELPTEXT)
    field = models.TextField(default=None, help_text="Which field to parse the content from.")
    indices = models.ManyToManyField(Index, default=None, help_text=INDICES_HELPTEXT)
    annotation_type = models.CharField(max_length=CHAR_LIMIT, choices=ANNOTATION_CHOICES, help_text="Which type of annotation does the user wish to perform")

    annotator_users = models.ManyToManyField(User, default=None, related_name="annotators", help_text="Who are the users who will be annotating.")
    author = models.ForeignKey(User, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    modified_at = models.DateTimeField(auto_now=True, null=True)
    completed_at = models.DateTimeField(null=True, default=None)

    total = models.IntegerField(default=0, help_text="How many documents are going to be annotated.")
    num_processed = models.IntegerField(default=0, help_text="How many documents of the total have been annotated.")
    skipped = models.IntegerField(default=0, help_text="How many documents of the total have been skipped.")
    validated = models.IntegerField(default=0, help_text="How many documents of the total have been validated.")

    binary_configuration = models.ForeignKey(
        BinaryAnnotatorConfiguration,
        on_delete=models.SET_NULL,
        null=True,
        default=None,
        help_text="Settings for binary type annotations."
    )
    multilabel_configuration = models.ForeignKey(
        MultilabelAnnotatorConfiguration,
        on_delete=models.SET_NULL,
        null=True,
        default=None,
        help_text="Settings for multilabel type annotations."
    )
    entity_configuration = models.ForeignKey(
        EntityAnnotatorConfiguration,
        on_delete=models.SET_NULL,
        null=True,
        default=None,
        help_text="Settings for entity type annotations."
    )

    bulk_size = models.IntegerField(default=100, help_text=BULK_SIZE_HELPTEXT, validators=[MinValueValidator(0), MaxValueValidator(ES_BULK_SIZE_MAX)])
    es_timeout = models.IntegerField(default=10, help_text=ES_TIMEOUT_HELPTEXT, validators=[MinValueValidator(0), MaxValueValidator(ES_TIMEOUT_MAX)])


    def get_available_or_all_indices(self, indices: List[str] = None) -> List[str]:
        """
        Used in views where the user can select the indices they wish to use.
        Returns a list of index names from the ones that are in the project
        and in the indices parameter or all of the indices if it's None or empty.
        """
        if indices:
            indices = self.indices.filter(name__in=indices, is_open=True)
            if not indices:
                indices = self.project.indices.all()
        else:
            indices = self.indices.all()

        indices = [index.name for index in indices]
        indices = list(set(indices))  # Leave only unique names just in case.
        return indices


    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]


    def add_pos_label(self, document_id: str):
        """
        Adds a positive label to the Elasticsearch document for Binary annotation.
        :param document_id: Elasticsearch document ID of the comment in question.
        :return:
        """
        pass


    def add_neg_label(self, document_id: str):
        """
        Adds a negative label to the Elasticsearch document for Binary annotation.
        :param document_id: Elasticsearch document ID of the comment in question.
        :return:
        """
        pass


    def add_label(self, document_id: str, label: str):
        """
        Adds a label to Elasticsearch documents during multilabel annotations.
        :param document_id: Elasticsearch document ID of the comment in question.
        :param label: Which label to add into the document.
        :return:
        """
        pass


    def add_entity(self, document_id: str, spans: List, fact_name: str, fact_value: str):
        """
        Adds an entity label to Elasticsearch documents during entity annotations.
        :param document_id: Elasticsearch document ID of the comment in question.
        :param spans: At which position in the text does the label belong to.
        :param fact_name: Which fact name to give to the Elasticsearch document.
        :param fact_value: Which fact value to give to the Elasticsearch document.
        :return:
        """
        pass


    def pull_document(self):
        """
        Function for returning a new Elasticsearch document to the for annotation.
        :return:
        """
        pass


    def skip_document(self, document_id: str):
        """
        Add the skip label to the document and update the progress accordingly.
        :param document_id: Elasticsearch document ID of the comment in question.
        :return:
        """
        indices = self.get_indices()
        ed = ESDocObject(document_id=document_id, index=indices)
        ed.add_skipped()
        ed.update()
        self.skipped = F('skipped') + 1
        self.save(update_fields=["skipped"])
        return True


    def add_comment(self, document_id: str, comment: str):
        """
        Adds an annotators comment into the document in question.
        :param comment: Comment to be stores inside the Elasticsearch document.
        :param document_id: Elasticsearch document ID of the comment in question.
        :return:
        """
        indices = self.get_indices()
        ed = ESDocObject(document_id=document_id, index=indices)
        ed.add_comment(comment)
        ed.update()
        return True


    def pull_skipped_documents(self):
        """
        Returns all the documents that are marked for skipping.
        :return:
        """
        pass


    def pull_annotated_document(self):
        """
        Returns an already annotated document for validation purposes.
        :return:
        """
        pass


    def reset_processed_records(self, indices: List[str], query: dict):
        """
        Resets the timestamp for all documents matching the query that have the "processed" timestamp.
        :param indices: Which indices to target for the rest.
        :param query: Elasticsearch query to subset the documents of the indices for the reset.
        :return:
        """
        pass


    @staticmethod
    def add_annotation_mapping(indices: List[str]):
        """
        Adds the mapping for the annotator into indices to ensure smooth sailing.
        :param indices: Which indices to target for the schemas.
        :return:
        """
        # TODO Should this be a nested field? Every user has their own annotation record to differentiate who did who inside the document itself.
        mapping = {
            "texta_annotator": {
                "processed_timestamp_utc": "date",
                "skipped_timestamp_utc": "date",
                "validated_timestamp_utc": "date",
                "comments": "list_of_strings",
            }
        }
        pass
