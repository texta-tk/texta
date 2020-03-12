import json
import re
from collections import OrderedDict

from rest_framework import serializers

from toolkit.core.project.models import Project


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
    ''' For serializers that need to override to_representation and parse fields
        Serializers overriden with FieldParseSerializer will validate, if field input                                                                                    '''


    def to_representation(self, instance):
        # self is the parent class obj in this case
        result = super(FieldParseSerializer, self).to_representation(instance)
        model_obj = self.Meta.model.objects.get(id=instance.id)
        fields_to_parse = self.Meta.fields_to_parse
        for field in fields_to_parse:
            if getattr(model_obj, field):
                result[field] = json.loads(getattr(model_obj, field))
        return OrderedDict([(key, result[key]) for key in result])


    def validate_fields(self, value):
        """ check if selected fields are present in the project and raise error on None
            if no "fields" field is declared in the serializer, no validation
            to write custom validation for serializers with FieldParseSerializer, simply override validate validate_fields in the project serializer"""
        project_obj = Project.objects.get(id=super(FieldParseSerializer, self).context['view'].kwargs['project_pk'])
        project_fields = set(project_obj.get_elastic_fields(path_list=True))
        if not value or not set(value).issubset(project_fields):
            raise serializers.ValidationError(f'Entered fields not in current project fields: {project_fields}')
        return value


class ProjectResourceBulkDeleteSerializer(serializers.Serializer):
    ids = serializers.JSONField(help_text='JSON list of ints. WARNING: use the "Raw data" form for proper JSON serialization.')


class GeneralTextSerializer(serializers.Serializer):
    text = serializers.CharField()


class ProjectResourceImportModelSerializer(serializers.Serializer):
    file = serializers.FileField()


class FeedbackSerializer(serializers.Serializer):
    feedback_id = serializers.CharField()
    correct_result = serializers.CharField()
