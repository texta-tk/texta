from rest_framework import permissions, status, viewsets
from toolkit.view_constants import BulkDelete
from .serializers import RakunExtractorSerializer
import rest_framework.filters as drf_filters
from django_filters import rest_framework as filters
from toolkit.rakun_keyword_extractor.models import RakunExtractor


class RakunExtractorViewSet(viewsets.ModelViewSet, BulkDelete):
    serializer_class = RakunExtractorSerializer
    permission_classes = (
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    ordering_fields = ('id', 'author__username', 'description')

    def get_queryset(self):
        return RakunExtractor.objects.filter(project=self.kwargs['project_pk']).order_by('-id')
