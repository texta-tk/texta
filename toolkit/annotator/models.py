import json
from typing import List, Optional

from django.contrib.auth.models import User
from django.db import models
# Create your models here.
from django.db.models import F

from toolkit.core.project.models import Project
from toolkit.elastic.index.models import Index
from toolkit.elastic.tools.document import ESDocObject
from toolkit.model_constants import TaskModel
from toolkit.settings import DESCRIPTION_CHAR_LIMIT


ANNOTATION_CHOICES = (
    ("binary", "binary"),
    ("multilabel", "multilabel"),
    ("entity", "entity")
)


class Category(models.Model):
    value = models.CharField(max_length=DESCRIPTION_CHAR_LIMIT)


class Label(models.Model):
    value = models.CharField(max_length=DESCRIPTION_CHAR_LIMIT)


class Labelset(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    values = models.ManyToManyField(Label)


class MultilabelAnnotatorConfiguration(models.Model):
    labelset = models.ForeignKey(Labelset, on_delete=models.CASCADE)


class BinaryAnnotatorConfiguration(models.Model):
    fact_name = models.CharField(max_length=DESCRIPTION_CHAR_LIMIT, help_text="Sets the value for the fact name for all annotated documents.")
    # Change these to a Label value.
    pos_value = models.CharField(max_length=DESCRIPTION_CHAR_LIMIT, help_text="Sets the name for a fact value for positive documents.")
    neg_value = models.CharField(max_length=DESCRIPTION_CHAR_LIMIT, help_text="Sets the name for a fact value for negative documents.")


class EntityAnnotatorConfiguration(models.Model):
    fact_name = models.CharField(max_length=DESCRIPTION_CHAR_LIMIT, help_text="Name of the fact which will be added.")


class Annotator(TaskModel):
    annotation_type = models.CharField(max_length=DESCRIPTION_CHAR_LIMIT, choices=ANNOTATION_CHOICES, help_text="Which type of annotation does the user wish to perform")

    annotator_users = models.ManyToManyField(User, default=None, related_name="annotators", help_text="Who are the users who will be annotating.")

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    modified_at = models.DateTimeField(auto_now=True, null=True)
    completed_at = models.DateTimeField(null=True, default=None)

    total = models.IntegerField(default=0, help_text="How many documents are going to be annotated.")
    annotated = models.IntegerField(default=0, help_text="How many documents of the total have been annotated.")
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


    def add_pos_label(self, document_id: str):
        """
        Adds a positive label to the Elasticsearch document for Binary annotation.
        :param document_id: Elasticsearch document ID of the comment in question.
        :return:
        """
        indices = self.get_indices()
        ed = ESDocObject(document_id=document_id, index=indices)
        ed.add_fact(fact_value=self.binary_configuration.pos_value, fact_name=self.binary_configuration.fact_name, doc_path=self.field)
        ed.add_annotated()
        ed.update()
        self.update_progress()


    def add_neg_label(self, document_id: str):
        """
        Adds a negative label to the Elasticsearch document for Binary annotation.
        :param document_id: Elasticsearch document ID of the comment in question.
        :return:
        """
        indices = self.get_indices()
        ed = ESDocObject(document_id=document_id, index=indices)
        ed.add_fact(fact_value=self.binary_configuration.neg_value, fact_name=self.binary_configuration.fact_name, doc_path=self.field)
        ed.add_annotated()
        ed.update()
        self.update_progress()


    def add_labels(self, document_id: str, labels: List[str]):
        """
        Adds a label to Elasticsearch documents during multilabel annotations.
        :param document_id: Elasticsearch document ID of the comment in question.
        :param labels: Which labels to add into the document.
        :return:
        """
        indices = self.get_indices()
        ed = ESDocObject(document_id=document_id, index=indices)
        for label in labels:
            ed.add_fact(fact_value=label, fact_name=self.multilabel_configuration.labelset.category.value, doc_path=self.field)
        ed.add_annotated()
        ed.update()
        self.update_progress()


    def validate_document(self, document_id: str) -> bool:
        """
        Edits the Elasticsearch documents validation timestamp and the progress in the model.
        :param document_id: Elasticsearch document ID of the comment in question.
        :return:
        """
        indices = self.get_indices()
        ed = ESDocObject(document_id=document_id, index=indices)
        ed.add_validated()
        ed.update()
        self.skipped = F('validated') + 1
        self.save(update_fields=["validated"])
        return True


    def add_entity(self, document_id: str, spans: List, fact_name: str, fact_value: str):
        """
        Adds an entity label to Elasticsearch documents during entity annotations.
        :param document_id: Elasticsearch document ID of the comment in question.
        :param spans: At which position in the text does the label belong to.
        :param fact_name: Which fact name to give to the Elasticsearch document.
        :param fact_value: Which fact value to give to the Elasticsearch document.
        :return:
        """
        indices = self.get_indices()
        ed = ESDocObject(document_id=document_id, index=indices)
        first, last = spans
        ed.add_fact(fact_value=fact_value, fact_name=fact_name, doc_path=self.field, spans=json.dumps([first, last]))
        ed.add_annotated()
        ed.update()
        self.update_progress()


    def pull_document(self) -> Optional[bool]:
        """
        Function for returning a new Elasticsearch document for annotation.
        :return:
        """
        from toolkit.elastic.tools.core import ElasticCore

        ec = ElasticCore()
        json_query = json.loads(self.query)
        indices = self.get_indices()
        query = ec.get_annotation_query(json_query)
        document = ESDocObject.random_document(indices=indices, query=query)
        # At one point in time, the documents will rune out.
        if document:
            return document.document
        else:
            return None


    def skip_document(self, document_id: str) -> bool:
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


    def add_comment(self, document_id: str, comment: str) -> bool:
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


    def update_progress(self):
        """
        Wrapper function for updating the progress after each annotation.
        :return:
        """
        self.annotated = F('annotated') + 1
        self.save(update_fields=["annotated"])


    def pull_skipped_documents(self):
        """
        Returns all the documents that are marked for skipping.
        :return:
        """
        pass


    def pull_annotated_document(self) -> Optional[dict]:
        """
        Returns an already annotated document for validation purposes.
        :return:
        """
        from toolkit.elastic.tools.core import ElasticCore

        ec = ElasticCore()
        json_query = json.loads(self.query)
        indices = self.get_indices()
        query = ec.get_annotation_validation_query(json_query)
        document = ESDocObject.random_document(indices=indices, query=query)
        # At one point in time, the documents will rune out.
        if document:
            return document.document
        else:
            return None


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
        from toolkit.elastic.tools.core import ElasticCore

        ec = ElasticCore()
        for index in indices:
            ec.add_annotator_mapping(index)
