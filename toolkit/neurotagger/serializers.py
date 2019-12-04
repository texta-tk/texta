import json
import re

from rest_framework import serializers
from django.db.models import Avg

from . import choices
from .models import Neurotagger
from toolkit.constants import get_field_choices
from toolkit.core.task.serializers import TaskSerializer
from toolkit.core.project.models import Project
from . import views
from toolkit.serializer_constants import ProjectResourceUrlSerializer, FieldParseSerializer



class NeurotaggerSerializer(FieldParseSerializer, serializers.HyperlinkedModelSerializer, ProjectResourceUrlSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.', write_only=True)
    fact_name = serializers.CharField(help_text=
        'Fact name used to train a multilabel model, with fact values as classes.',
        required=False,
        allow_blank=True
    )

    model_architecture = serializers.ChoiceField(choices=choices.model_arch_choices)
    seq_len = serializers.IntegerField(default=choices.DEFAULT_SEQ_LEN, help_text=f'Default: {choices.DEFAULT_SEQ_LEN}')
    vocab_size = serializers.IntegerField(default=choices.DEFAULT_VOCAB_SIZE, help_text=f'Default: {choices.DEFAULT_VOCAB_SIZE}')
    num_epochs = serializers.IntegerField(default=choices.DEFAULT_NUM_EPOCHS, help_text=f'Default: {choices.DEFAULT_NUM_EPOCHS}')
    validation_split = serializers.FloatField(default=choices.DEFAULT_VALIDATION_SPLIT, help_text=f'Default: {choices.DEFAULT_VALIDATION_SPLIT}')
    score_threshold = serializers.IntegerField(default=choices.DEFAULT_SCORE_THRESHOLD, help_text=f'Default: {choices.DEFAULT_SCORE_THRESHOLD}')

    negative_multiplier = serializers.FloatField(default=choices.DEFAULT_NEGATIVE_MULTIPLIER, help_text=f'Default: {choices.DEFAULT_NEGATIVE_MULTIPLIER}')
    maximum_sample_size = serializers.IntegerField(default=choices.DEFAULT_MAX_SAMPLE_SIZE,help_text=f'Default: {choices.DEFAULT_MAX_SAMPLE_SIZE}')
    max_fact_doc_count = serializers.IntegerField(default=None, allow_null=True, help_text=
    f'Maximum number of documents required per fact to train a multilabel model.')
    min_fact_doc_count = serializers.IntegerField(default=choices.DEFAULT_MIN_FACT_DOC_COUNT, help_text=
    f'Minimum number of documents required per fact to train a multilabel model. Default: {choices.DEFAULT_MIN_FACT_DOC_COUNT}')

    task = TaskSerializer(read_only=True)
    plot = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()


    class Meta:
        model = Neurotagger
        fields = ('id', 'url', 'author_username', 'description', 'project', 'author', 'validation_split', 'score_threshold',
                  'fields', 'model_architecture', 'seq_len', 'maximum_sample_size', 'negative_multiplier',
                  'location', 'num_epochs', 'vocab_size', 'plot', 'task', 'validation_accuracy', 'training_accuracy', 'fact_values',
                  'training_loss', 'validation_loss', 'result_json', 'fact_name', 'min_fact_doc_count', 'max_fact_doc_count')

        read_only_fields = ('author', 'project', 'location', 'accuracy', 'loss', 'plot',
                            'result_json', 'validation_accuracy', 'training_accuracy',
                            'training_loss', 'validation_loss', 'fact_values', 'classification_report'
                            )
        fields_to_parse = ('fields',)


    def validate_fields(self, value):
        """ raise error on neurotagger empty fields """
        project_obj = Project.objects.get(id=self.context['view'].kwargs['project_pk'])
        project_fields = set(project_obj.get_elastic_fields(path_list=True))
        if not value:
            raise serializers.ValidationError(f'entered fields not in current project fields: {project_fields}')
        return value

    def validate(self, data):
        """ validate if tags are retrievable with serializer input """
        if data['fact_name'] and 'fact_name' in data:
            project_obj = Project.objects.get(id=self.context['view'].kwargs['project_pk'])
            # Retrieve tags/fact values and create queries to build models. Every tag will be a class.
            tags = views.NeurotaggerViewSet().get_tags(data['fact_name'],
                                                     project_obj,
                                                     min_count=data['min_fact_doc_count'],
                                                     max_count=data['max_fact_doc_count'])
            # Check if any tags were found
            if not tags:
                raise serializers.ValidationError(f'found no tags for fact name: {fact_name}')
        else:
            raise serializers.ValidationError("Tag name must be included!")
        return data


    def __init__(self, *args, **kwargs):
        '''
        Add the ability to pass extra arguments such as "remove_fields".
        Useful for the Serializer eg in another Serializer, without making a new one.
        '''
        remove_fields = kwargs.pop('remove_fields', None)
        super(NeurotaggerSerializer, self).__init__(*args, **kwargs)

        if remove_fields:
            # for multiple fields in a list
            for field_name in remove_fields:
                self.fields.pop(field_name)


class NeuroTaggerTagDocumentSerializer(serializers.Serializer):
    doc = serializers.JSONField()
    threshold = serializers.FloatField(default=0.3, help_text=f'Filter out tags with a lower than threshold probaility. Default: {choices.DEFAULT_THRESHOLD_VALUE}')

class NeuroTaggerTagTextSerializer(serializers.Serializer):
    text = serializers.CharField()
    threshold = serializers.FloatField(default=0.3, help_text=f'Filter out tags with a lower than threshold probaility. Default: {choices.DEFAULT_THRESHOLD_VALUE}')
