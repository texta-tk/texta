import rest_framework.filters as drf_filters
from django_filters import rest_framework as filters
from rest_framework import mixins, permissions, viewsets

# Create your views here.
from toolkit.annotator.models import Annotator
from toolkit.annotator.serializers import AnnotatorSerializer
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
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



    def get_queryset(self):
        return Annotator.objects.filter(project=self.kwargs['project_pk']).order_by('-id')
