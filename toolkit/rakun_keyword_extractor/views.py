from rest_framework import permissions, status, viewsets
from toolkit.view_constants import BulkDelete
from .serializers import RakunExtractorSerializer
import rest_framework.filters as drf_filters
from django_filters import rest_framework as filters
from toolkit.rakun_keyword_extractor.models import RakunExtractor
from toolkit.core.project.models import Project
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
from toolkit.elastic.index.models import Index


class RakunExtractorViewSet(viewsets.ModelViewSet, BulkDelete):
    serializer_class = RakunExtractorSerializer
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    ordering_fields = ('id', 'author__username', 'description')

    def get_queryset(self):
        return RakunExtractor.objects.filter(project=self.kwargs['project_pk']).order_by('-id')

    def perform_create(self, serializer: RakunExtractorSerializer):
        project = Project.objects.get(id=self.kwargs['project_pk'])
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project.get_available_or_all_project_indices(indices)

        serializer.validated_data.pop("indices")

        rakun: RakunExtractor = serializer.save(
            author=self.request.user,
            project=project
        )

        for index in Index.objects.filter(name__in=indices, is_open=True):
            rakun.indices.add(index)

        rakun.apply_rakun()
