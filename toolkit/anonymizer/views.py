import json
import os

from rest_framework import permissions, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
import rest_framework.filters as drf_filters
from django.http import HttpResponse
from django_filters import rest_framework as filters

from texta_anonymizer.anonymizer import Anonymizer as NameAnonymizer

from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.view_constants import BulkDelete
from toolkit.core.project.models import Project
from .serializers import (
    AnonymizerSerializer,
    AnonymizerAnonymizeTextSerializer,
    AnonymizerAnonymizeTextsSerializer
)
from toolkit.serializer_constants import ProjectResourceImportModelSerializer
from .models import Anonymizer


class AnonymizerFilter(filters.FilterSet):
    description = filters.CharFilter('description', lookup_expr='icontains')

    class Meta:
        model = Anonymizer
        fields = []


class AnonymizerViewSet(viewsets.ModelViewSet, BulkDelete):
    serializer_class = AnonymizerSerializer
    permission_classes = (
        ProjectResourceAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = AnonymizerFilter
    ordering_fields = ('id', 'author__username', 'description')


    def get_queryset(self):
        return Anonymizer.objects.filter(project=self.kwargs['project_pk'])


    def perform_create(self, serializer):
        project = Project.objects.get(id=self.kwargs['project_pk'])
        anonymizer: Anonymizer = serializer.save(
            author=self.request.user,
            project=project
        )

    @action(detail=True, methods=['post'], serializer_class=AnonymizerAnonymizeTextSerializer)
    def anonymize_text(self, request, pk=None, project_pk=None):
        serializer = AnonymizerAnonymizeTextSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # retrieve anonymizer object
        anonymizer_object = self.get_object()
        # load anonymizer
        anonymizer = self._load_anonymizer(anonymizer_object)
        # anonymize text
        result = anonymizer.anonymize(serializer.validated_data['text'], serializer.validated_data['names'])
        return Response(result, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=AnonymizerAnonymizeTextsSerializer)
    def anonymize_texts(self, request, pk=None, project_pk=None):
        serializer = AnonymizerAnonymizeTextsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # retrieve anonymizer object
        anonymizer_object = self.get_object()
        # load anonymizer
        anonymizer = self._load_anonymizer(anonymizer_object)
        # anonymize texts
        result = []
        for text in serializer.validated_data['texts']:
            anon_text = anonymizer.anonymize(text, serializer.validated_data['names'])
            result.append(anon_text)

        return Response(result, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get'])
    def export_model(self, request, pk=None, project_pk=None):
        """Returns model as zip file."""
        zip_name = f'anonymizer_model_{pk}.zip'
        anonymizer_object: Anonymizer = self.get_object()
        data = anonymizer_object.export_resources()
        response = HttpResponse(data)
        response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(zip_name)
        return response


    @action(detail=False, methods=["post"], serializer_class=ProjectResourceImportModelSerializer)
    def import_model(self, request, pk=None, project_pk=None):
        serializer = ProjectResourceImportModelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded_file = serializer.validated_data['file']
        tagger_id = Anonymizer.import_resources(uploaded_file, request, project_pk)
        return Response({"id": tagger_id, "message": "Successfully imported model."}, status=status.HTTP_201_CREATED)


    @staticmethod
    def _load_anonymizer(anonymizer_object):
        # create anonymizer
        anonymizer = NameAnonymizer(
            allow_fuzzy_matching = anonymizer_object.allow_fuzzy_matching,
            extract_single_last_names = anonymizer_object.extract_single_last_names,
            extract_single_first_names = anonymizer_object.extract_single_last_names,
            fuzzy_threshold = anonymizer_object.fuzzy_threshold,
            mimic_casing = anonymizer_object.mimic_casing,
        )
        return anonymizer
