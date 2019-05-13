from rest_framework import viewsets

from toolkit.core.search.models import Search
from toolkit.core.search.serializers import SearchSerializer

# Create your views here.
class SearchViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows sear4ches to be viewed or edited.
    """
    queryset = Search.objects.all()
    serializer_class = SearchSerializer
