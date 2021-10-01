import rest_framework.filters as drf_filters
from django_filters import rest_framework as filters
from rest_framework import mixins, permissions, status, viewsets
# Create your views here.
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.annotator.models import Annotator
from toolkit.annotator.serializers import AnnotatorSerializer, SkipDocumentSerializer
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
from toolkit.serializer_constants import EmptySerializer
from toolkit.view_constants import BulkDelete


class AnnotatorViewset(mixins.CreateModelMixin,
                       mixins.ListModelMixin,
                       mixins.RetrieveModelMixin,
                       mixins.DestroyModelMixin,
                       viewsets.GenericViewSet,
                       BulkDelete):
    queryset = Annotator.objects.all()
    serializer_class = AnnotatorSerializer
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)


    @action(detail=True, methods=["POST"], serializer_class=EmptySerializer)
    def pull_document(self, request, pk=None, project_pk=None):
        annotator: Annotator = self.get_object()
        document = annotator.pull_document()
        if document:
            return Response(document)
        else:
            return Response({"detail": "No more documents left!"}, status=status.HTTP_404_NOT_FOUND)


    @action(detail=True, methods=["POST"], serializer_class=SkipDocumentSerializer)
    def skip_document(self, request, pk=None, project_pk=None):
        serializer: SkipDocumentSerializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        annotator: Annotator = self.get_object()
        annotator.skip_document(serializer.validated_data["document_id"])
        return Response({"detail": f"Skipped document with ID: {serializer.validated_data['document_id']}"})


    def get_queryset(self):
        return Annotator.objects.filter(project=self.kwargs['project_pk']).order_by('-id')
