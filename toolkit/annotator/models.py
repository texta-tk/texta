import json
from datetime import datetime
from typing import List, Optional

from django.contrib.auth.models import User
from django.db import models
from django.db.models import signals

from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from texta_elastic.document import ESDocObject
from toolkit.model_constants import TaskModel
from toolkit.settings import DESCRIPTION_CHAR_LIMIT, CELERY_LONG_TERM_TASK_QUEUE


# Create your models here.


ANNOTATION_CHOICES = (
    ("binary", "binary"),
    ("multilabel", "multilabel"),
    ("entity", "entity")
)


class Category(models.Model):
    value = models.CharField(max_length=DESCRIPTION_CHAR_LIMIT, unique=True)


    def __str__(self):
        return self.value


class Label(models.Model):
    value = models.CharField(max_length=DESCRIPTION_CHAR_LIMIT, unique=True)


    def __str__(self):
        return self.value


class Labelset(models.Model):
    indices = models.ManyToManyField(Index)
    fact_names = models.TextField(null=True)
    value_limit = models.IntegerField(null=True)
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

    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)

    add_facts_mapping = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    modified_at = models.DateTimeField(auto_now=True, null=True)
    completed_at = models.DateTimeField(null=True, default=None)

    total = models.IntegerField(default=0, help_text="How many documents are going to be annotated.")
    validated = models.IntegerField(default=0, help_text="How many documents of the total have been validated.")

    target_field = models.CharField(max_length=DESCRIPTION_CHAR_LIMIT, default='', help_text="Which Elasticsearch document field you use base the annotation on.")

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


    @property
    def annotated(self):
        restraint = Record.objects.filter(annotated_utc__isnull=False, skipped_utc__isnull=True, annotation_job=self)
        return restraint.count()


    @property
    def skipped(self):
        restraint = Record.objects.filter(annotated_utc__isnull=True, skipped_utc__isnull=False, annotation_job=self)
        return restraint.count()

    def create_annotator_task(self):
        new_task = Task.objects.create(annotator=self, status='created')
        self.task = new_task
        self.save()

        from toolkit.annotator.tasks import annotator_task
        annotator_task.apply_async(args=(self.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE)


    def add_pos_label(self, document_id: str, index: str, user):
        """
        Adds a positive label to the Elasticsearch document for Binary annotation.
        :param user_pk:
        :param index: Which index does said Elasticsearch document reside in.
        :param document_id: Elasticsearch document ID of the comment in question.
        :return:
        """
        ed = ESDocObject(document_id=document_id, index=index)
        fact = ed.add_fact(fact_value=self.binary_configuration.pos_value, fact_name=self.binary_configuration.fact_name, doc_path=self.target_field)
        ed.add_annotated(annotator_model=self, user=user)
        ed.update()
        self.generate_record(document_id, index=index, user_pk=user.pk, fact=fact, do_annotate=True, fact_id=fact["id"])


    def generate_record(self, document_id, index, user_pk, fact=None, fact_id=None, do_annotate=False, do_skip=False):
        user = User.objects.get(pk=user_pk)
        record, is_created = Record.objects.get_or_create(document_id=document_id, index=index, user=user, annotation_job=self)
        if do_annotate:
            record.skipped_utc = None
            record.fact = json.dumps(fact)
            record.fact_id = fact_id
            record.annotated_utc = datetime.utcnow()
        if do_skip:
            record.annotated_utc = None
            record.skipped_utc = datetime.utcnow()
        record.save()


    def add_neg_label(self, document_id: str, index: str, user):
        """
        Adds a negative label to the Elasticsearch document for Binary annotation.
        :param index: Which index does said Elasticsearch document reside in.
        :param document_id: Elasticsearch document ID of the comment in question.
        :return:
        """
        ed = ESDocObject(document_id=document_id, index=index)
        fact = ed.add_fact(fact_value=self.binary_configuration.neg_value, fact_name=self.binary_configuration.fact_name, doc_path=self.target_field)
        ed.add_annotated(self, user)
        ed.update()
        self.generate_record(document_id, index=index, user_pk=user.pk, fact=fact, do_annotate=True, fact_id=fact["id"])


    def add_labels(self, document_id: str, labels: List[str], index: str, user):
        """
        Adds a label to Elasticsearch documents during multilabel annotations.
        :param index:
        :param document_id: Elasticsearch document ID of the comment in question.
        :param labels: Which labels to add into the document.
        :return:
        """
        ed = ESDocObject(document_id=document_id, index=index)
        for label in labels:
            ed.add_fact(fact_value=label, fact_name=self.multilabel_configuration.labelset.category.value, doc_path=self.target_field)
        ed.add_annotated(self, user)
        ed.update()


    def __split_fact(self, fact: dict):
        fact_name, value, spans, field, fact_id = fact["fact"], fact.get("str_val") or fact.get("num_val"), fact.get("spans"), fact.get("doc_path"), fact.get("id", "")
        return fact_name, value, spans, field, fact_id


    def add_entity(self, document_id: str, spans: List, fact_name: str, field: str, fact_value: str, index: str, user):
        """
        Adds an entity label to Elasticsearch documents during entity annotations.
        :param index:
        :param field: Which field was used to annotate.
        :param document_id: Elasticsearch document ID of the comment in question.
        :param spans: At which position in the text does the label belong to.
        :param fact_name: Which fact name to give to the Elasticsearch document.
        :param fact_value: Which fact value to give to the Elasticsearch document.
        :return:
        """
        ed = ESDocObject(document_id=document_id, index=index)
        first, last = spans
        ed.add_fact(fact_value=fact_value, fact_name=fact_name, doc_path=field, spans=json.dumps([first, last]))
        ed.add_annotated(self, user)
        ed.update()


    def pull_document(self) -> Optional[dict]:
        """
        Function for returning a new Elasticsearch document for annotation.
        :return:
        """
        from texta_elastic.core import ElasticCore

        ec = ElasticCore()
        json_query = json.loads(self.query)
        indices = self.get_indices()
        query = ec.get_annotation_query(json_query, job_pk=self.pk)
        document = ESDocObject.random_document(indices=indices, query=query)
        # At one point in time, the documents will rune out.
        if document:
            return document.document
        else:
            return None


    def skip_document(self, document_id: str, index: str, user) -> bool:
        """
        Add the skip label to the document and update the progress accordingly.
        :param user:
        :param index:
        :param document_id: Elasticsearch document ID of the comment in question.
        :return:
        """
        ed = ESDocObject(document_id=document_id, index=index)
        ed.add_skipped(self, user)
        ed.update()
        self.generate_record(document_id, index=index, user_pk=user.pk, do_skip=True)

        return True


    def add_comment(self, document_id: str, comment: str, user: User) -> bool:
        """
        Adds an annotators comment into the document in question.
        :param user: Django user who did the comment.
        :param comment: Comment to be stores inside the Elasticsearch document.
        :param document_id: Elasticsearch document ID of the comment in question.
        :return:
        """
        Comment.objects.create(annotation_job=self, text=comment, document_id=document_id, user=user)
        return True


    def pull_skipped_document(self):
        """
        Returns all the documents that are marked for skipping.
        :return:
        """
        from texta_elastic.core import ElasticCore

        ec = ElasticCore()
        json_query = json.loads(self.query)
        indices = self.get_indices()
        query = ec.get_skipped_annotation_query(json_query, self.pk)
        document = ESDocObject.random_document(indices=indices, query=query)
        # At one point in time, the documents will rune out.
        if document:
            return document.document
        else:
            return None


    def pull_annotated_document(self) -> Optional[dict]:
        """
        Returns an already annotated document for validation purposes.
        :return:
        """
        from texta_elastic.core import ElasticCore

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
        from texta_elastic.core import ElasticCore

        ec = ElasticCore()
        for index in indices:
            ec.add_annotator_mapping(index)


class Comment(models.Model):
    text = models.TextField()
    document_id = models.CharField(max_length=DESCRIPTION_CHAR_LIMIT)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    annotation_job = models.ForeignKey(Annotator, on_delete=models.SET_NULL, null=True)


    def __str__(self):
        return f"{self.user.username}: {self.text} @{str(self.created_at)}"


class Record(models.Model):
    document_id = models.CharField(max_length=DESCRIPTION_CHAR_LIMIT, db_index=True)
    index = models.CharField(max_length=DESCRIPTION_CHAR_LIMIT)
    fact_id = models.TextField(default=None, null=True, db_index=True)

    fact = models.TextField(default=json.dumps({}))

    annotated_utc = models.DateTimeField(default=None, null=True)
    skipped_utc = models.DateTimeField(default=None, null=True)

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    annotation_job = models.ForeignKey(Annotator, on_delete=models.SET_NULL, null=True)
