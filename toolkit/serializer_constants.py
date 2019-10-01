import re
from rest_framework import serializers

class ProjectResourceUrlSerializer():
    '''For project serializers which need to construct the HyperLinked URL'''

    def get_url(self, obj):
        request = self.context['request']
        path = re.sub(r'\d+\/*$', '', request.path)
        resource_url = request.build_absolute_uri(f'{path}{obj.id}/')
        return resource_url 


class BulkDeleteSerializer(serializers.Serializer):
    ids = serializers.JSONField(help_text='JSON list of ints. WARNING: use the "Raw data" form for proper JSON serialization.')
