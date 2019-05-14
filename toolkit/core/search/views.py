from rest_framework import viewsets

from toolkit.core.search.models import Search
from toolkit.core.search.serializers import SearchSerializer


class SearchViewSet(viewsets.ModelViewSet):
    queryset = Search.objects.all()
    serializer_class = SearchSerializer
