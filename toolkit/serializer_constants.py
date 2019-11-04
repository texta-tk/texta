import re
from rest_framework import serializers

class ProjectResourceUrlSerializer():
    '''For project serializers which need to construct the HyperLinked URL'''

    def get_url(self, obj):
        request = self.context['request']
        path = re.sub(r'\d+\/*$', '', request.path)
        resource_url = request.build_absolute_uri(f'{path}{obj.id}/')
        return resource_url
    
    def get_plot(self, obj):
        request = self.context['request']
        resource_url = request.build_absolute_uri(f'/{obj.plot}')
        return resource_url        


class ProjectResourceBulkDeleteSerializer(serializers.Serializer):
    ids = serializers.JSONField(help_text='JSON list of ints. WARNING: use the "Raw data" form for proper JSON serialization.')


class GeneralTextSerializer(serializers.Serializer):
    text = serializers.CharField()


class ProjectResourceImportModelSerializer(serializers.Serializer):
    file = serializers.FileField()
