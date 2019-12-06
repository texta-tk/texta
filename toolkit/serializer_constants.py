import re
import json
from rest_framework import serializers
from collections import OrderedDict


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


class FieldParseSerializer():
    ''' For serializers that need to override to_representation and parse fields '''

    def to_representation(self, instance):
        # self is the parent class obj in this case
        result = super(FieldParseSerializer, self).to_representation(instance)
        model_obj = self.Meta.model.objects.get(id=instance.id)
        fields_to_parse = self.Meta.fields_to_parse
        for field in fields_to_parse:
            if getattr(model_obj, field):
                result[field] = json.loads(getattr(model_obj, field))
        return OrderedDict([(key, result[key]) for key in result])


class ProjectResourceBulkDeleteSerializer(serializers.Serializer):
    ids = serializers.JSONField(help_text='JSON list of ints. WARNING: use the "Raw data" form for proper JSON serialization.')


class GeneralTextSerializer(serializers.Serializer):
    text = serializers.CharField()


class ProjectResourceImportModelSerializer(serializers.Serializer):
    file = serializers.FileField()


class FeedbackSerializer(serializers.Serializer):
    feedback_id = serializers.CharField()
    correct_prediction = serializers.CharField()
