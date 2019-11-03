from rest_framework import serializers

from toolkit.core.search.models import Search
from toolkit.serializer_constants import ProjectResourceUrlSerializer

class SearchSerializer(serializers.HyperlinkedModelSerializer, ProjectResourceUrlSerializer):    
    query_constraints = serializers.JSONField(help_text='External searcher state JSON')
    query = serializers.JSONField(help_text='JSON Elasticsearch query')
    url = serializers.SerializerMethodField()

    class Meta:
        model = Search
        fields = ('url', 'id', 'description', 'query_constraints', 'author', 'project', 'query')
        read_only_fields = ('url', 'author', 'project',)
