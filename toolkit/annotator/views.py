import rest_framework.filters as drf_filters
from django_filters import rest_framework as filters
from rest_framework import mixins, permissions, status, viewsets
# Create your views here.
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.annotator.models import Annotator, AnnotatorGroup, Comment, Labelset, Record
from toolkit.annotator.serializers import AnnotatorProjectSerializer, AnnotatorGroupSerializer, AnnotatorSerializer, BinaryAnnotationSerializer, CommentSerializer, DocumentEditSerializer, DocumentIDSerializer, EntityAnnotationSerializer, LabelsetSerializer, MultilabelAnnotationSerializer, RecordSerializer, \
    ValidateDocumentSerializer
from texta_elastic.core import ElasticCore
from texta_elastic.document import ElasticDocument
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
from toolkit.serializer_constants import EmptySerializer
from toolkit.settings import TEXTA_ANNOTATOR_KEY
from toolkit.view_constants import BulkDelete


class RecordViewset(mixins.ListModelMixin, viewsets.GenericViewSet, BulkDelete):
    serializer_class = RecordSerializer
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)


    def get_queryset(self):
        return Record.objects.filter().order_by('-id')


class LabelsetViewset(mixins.CreateModelMixin,
                      mixins.ListModelMixin,
                      mixins.RetrieveModelMixin,
                      mixins.DestroyModelMixin,
                      viewsets.GenericViewSet,
                      BulkDelete):
    serializer_class = LabelsetSerializer
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)


    def get_queryset(self):
        return Labelset.objects.filter(project=self.kwargs['project_pk']).order_by('-id')


class AnnotatorViewset(mixins.CreateModelMixin,
                       mixins.ListModelMixin,
                       mixins.RetrieveModelMixin,
                       mixins.DestroyModelMixin,
                       mixins.UpdateModelMixin,
                       viewsets.GenericViewSet,
                       BulkDelete):
    serializer_class = AnnotatorSerializer
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    http_method_names = ["get", "post", "patch", "delete", "options"]

    def _enrich_document_with_meta(self, document: dict, annotator: Annotator):

        # Add comment count to the elastic document
        document_id = document["_id"]
        meta_list = document["_source"].get(TEXTA_ANNOTATOR_KEY, [])
        job_list = [document for document in meta_list if document["job_id"] == annotator.pk]
        meta_dict = job_list[0] if len(job_list) > 0 else {}
        meta_dict["comment_count"] = Comment.objects.filter(document_id=document_id).count()

        # Add counts of things to the document.
        meta_dict["total_count"] = annotator.total
        meta_dict["annotated_count"] = annotator.annotated
        meta_dict["skipped_count"] = annotator.skipped
        meta_dict["validated_count"] = annotator.validated
        document["_source"][TEXTA_ANNOTATOR_KEY] = meta_dict
        return document


    def _flatten_document(self, document):
        ec = ElasticCore()
        source = document.get("_source")
        annotator_meta = source.pop(TEXTA_ANNOTATOR_KEY)
        flattened_source = ec.flatten(source)
        # Skip the annotator meta when flattening and then attach it back.
        flattened_source[TEXTA_ANNOTATOR_KEY] = annotator_meta
        document["_source"] = flattened_source
        return document


    def _process_document_output(self, document, annotator):
        document = self._enrich_document_with_meta(document, annotator)
        document = self._flatten_document(document)
        return document


    @action(detail=True, methods=["POST"], serializer_class=EmptySerializer)
    def pull_document(self, request, pk=None, project_pk=None):
        annotator: Annotator = self.get_object()
        document = annotator.pull_document()
        if document:
            document = self._process_document_output(document, annotator)
            return Response(document)
        else:
            return Response({"detail": "No more documents left!"}, status=status.HTTP_404_NOT_FOUND)


    # TODO Put the functional logic inside the model for a more common standard.
    @action(detail=True, methods=["POST"], serializer_class=DocumentIDSerializer)
    def pull_document_by_id(self, request, pk=None, project_pk=None):
        annotator: Annotator = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ed = ElasticDocument(index=annotator.get_indices())
        document_id = serializer.validated_data["document_id"]
        document = ed.get(document_id)
        if document:
            document = self._process_document_output(document, annotator)
            return Response(document)
        else:
            return Response({"message": "No such document!"}, status=status.HTTP_404_NOT_FOUND)


    @action(detail=True, methods=["POST"], serializer_class=EmptySerializer)
    def pull_annotated(self, request, pk=None, project_pk=None):
        annotator: Annotator = self.get_object()
        document = annotator.pull_annotated_document()
        if document:
            document = self._process_document_output(document, annotator)
            return Response(document)
        else:
            return Response({"detail": "No more documents left!"}, status=status.HTTP_404_NOT_FOUND)


    @action(detail=True, methods=["POST"], serializer_class=EmptySerializer)
    def pull_skipped(self, request, pk=None, project_pk=None):
        annotator: Annotator = self.get_object()
        document = annotator.pull_skipped_document()
        if document:
            document = self._process_document_output(document, annotator)
            return Response(document)
        else:
            return Response({"detail": "No more documents left!"}, status=status.HTTP_404_NOT_FOUND)


    @action(detail=True, methods=["POST"], serializer_class=DocumentEditSerializer)
    def skip_document(self, request, pk=None, project_pk=None):
        serializer: DocumentIDSerializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        annotator: Annotator = self.get_object()

        ed = ElasticDocument(index=annotator.get_indices())
        document_id = serializer.validated_data["document_id"]
        document = ed.get(document_id)
        texta_annotations = document["_source"].get("texta_annotator", [])

        processed_timestamp = None
        if texta_annotations:
            for texta_annotation in texta_annotations:
                processed_timestamp = texta_annotation.get("processed_timestamp_utc", None)

                if processed_timestamp:
                    return Response(
                        {"detail": f"Document with ID: {serializer.validated_data['document_id']} is already annotated"})

            annotator.skip_document(serializer.validated_data["document_id"], serializer.validated_data["index"],
                                    user=request.user)
            return Response({"detail": f"Skipped document with ID: {serializer.validated_data['document_id']}"})
        else:
            annotator.skip_document(serializer.validated_data["document_id"], serializer.validated_data["index"],
                                    user=request.user)
            return Response({"detail": f"Skipped document with ID: {serializer.validated_data['document_id']}"})


    @action(detail=True, methods=["POST"], serializer_class=ValidateDocumentSerializer)
    def validate_document(self, request, pk=None, project_pk=None):
        serializer: ValidateDocumentSerializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        annotator: Annotator = self.get_object()
        annotator.validate_document(
            document_id=serializer.validated_data["document_id"],
            facts=serializer.validated_data["facts"],
            is_valid=serializer.validated_data["is_valid"]
        )
        return Response({"detail": f"Validated document with ID: {serializer.validated_data['document_id']}"})


    @action(detail=True, methods=["POST"], serializer_class=EntityAnnotationSerializer)
    def annotate_entity(self, request, pk=None, project_pk=None):
        serializer: EntityAnnotationSerializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        annotator: Annotator = self.get_object()
        annotator.add_entity(
            document_id=serializer.validated_data["document_id"],
            texta_facts=serializer.validated_data["texta_facts"],
            index=serializer.validated_data["index"],
            user=request.user
        )
        return Response({"detail": f"Annotated document with ID: {serializer.validated_data['document_id']}"})


    @action(detail=True, methods=["POST"], serializer_class=BinaryAnnotationSerializer)
    def annotate_binary(self, request, pk=None, project_pk=None):
        serializer: BinaryAnnotationSerializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        annotator: Annotator = self.get_object()
        choice = serializer.validated_data["annotation_type"]
        index = serializer.validated_data["index"]

        if choice == "pos":
            annotator.add_pos_label(serializer.validated_data["document_id"], index=index, user=request.user)
            return Response({"detail": f"Annotated document with ID: {serializer.validated_data['document_id']} with the pos label '{annotator.binary_configuration.pos_value}'"})

        elif choice == "neg":
            annotator.add_neg_label(serializer.validated_data["document_id"], index=index, user=request.user)
            return Response({"detail": f"Annotated document with ID: {serializer.validated_data['document_id']} with the neg label '{annotator.binary_configuration.neg_value}'"})


    @action(detail=True, methods=["POST"], serializer_class=MultilabelAnnotationSerializer)
    def annotate_multilabel(self, request, pk=None, project_pk=None):
        serializer: MultilabelAnnotationSerializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        annotator: Annotator = self.get_object()
        annotator.add_labels(serializer.validated_data["document_id"], serializer.validated_data["labels"], index=serializer.validated_data["index"], user=request.user)
        return Response({"detail": f"Annotated document with ID: {serializer.validated_data['document_id']}"})


    @action(detail=True, methods=["POST"], serializer_class=CommentSerializer)
    def add_comment(self, request, pk=None, project_pk=None):
        serializer: CommentSerializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        annotator: Annotator = self.get_object()
        document_id = serializer.validated_data["document_id"]
        annotator.add_comment(document_id=document_id, comment=serializer.validated_data["text"], user=request.user)
        return Response({"detail": f"Successfully added comment to the document for document with ID: {document_id}."})


    @action(detail=True, methods=["POST"], serializer_class=DocumentIDSerializer)
    def get_comments(self, request, pk=None, project_pk=None):
        serializer: DocumentIDSerializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document_id = serializer.validated_data["document_id"]
        comments = Comment.objects.filter(document_id=document_id).order_by("-created_at")[:10]
        data = CommentSerializer(comments, many=True).data
        return Response({"count": len(data), "results": data})


    def get_queryset(self):
        return Annotator.objects.filter(project=self.kwargs['project_pk']).order_by('-id')


class AnnotatorProjectViewset(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = AnnotatorProjectSerializer
    permission_classes = (
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)


    def get_queryset(self):
        return Annotator.objects.filter(annotator_users=self.request.user).order_by('-id')


class AnnotatorGroupViewset(mixins.CreateModelMixin,
                       mixins.ListModelMixin,
                       mixins.RetrieveModelMixin,
                       mixins.DestroyModelMixin,
                       mixins.UpdateModelMixin,
                       viewsets.GenericViewSet,
                       BulkDelete):
    serializer_class = AnnotatorGroupSerializer
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)

    def get_queryset(self):
        return AnnotatorGroup.objects.filter(project=self.kwargs['project_pk']).order_by('-id')
