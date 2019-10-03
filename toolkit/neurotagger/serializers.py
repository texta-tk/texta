import json
import re

from rest_framework import serializers
from django.db.models import Avg

from . import choices
from .models import Neurotagger
from toolkit.constants import get_field_choices
from toolkit.core.task.serializers import TaskSerializer
from toolkit.settings import URL_PREFIX
from toolkit.serializer_constants import ProjectResourceUrlSerializer



class NeurotaggerSerializer(serializers.HyperlinkedModelSerializer, ProjectResourceUrlSerializer):
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.', write_only=True)
    fields_parsed = serializers.SerializerMethodField()
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
    model_plot = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()


    class Meta:
        model = Neurotagger
        fields = ('url', 'id', 'description', 'project', 'author', 'validation_split', 'score_threshold',
                  'fields', 'fields_parsed', 'model_architecture', 'seq_len', 'maximum_sample_size', 'negative_multiplier',
                  'location', 'num_epochs', 'vocab_size', 'plot', 'task', 'validation_accuracy', 'training_accuracy', 'fact_values',
                  'training_loss', 'validation_loss', 'model_plot', 'result_json', 'fact_name', 'min_fact_doc_count', 'max_fact_doc_count')

        read_only_fields = ('author', 'project', 'location', 'accuracy', 'loss', 'plot',
                            'model_plot', 'result_json', 'validation_accuracy', 'training_accuracy',
                            'training_loss', 'validation_loss', 'fact_values', 'classification_report'
                            )
        

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
    

    def get_plot(self, obj):
        if obj.plot:
            return '{0}/{1}'.format(URL_PREFIX, obj.plot)
        else:
            return None

    def get_model_plot(self, obj):
        if obj.model_plot:
            return '{0}/{1}'.format(URL_PREFIX, obj.model_plot)
        else:
            return None

    def get_fields_parsed(self, obj):
        if obj.fields:
            return json.loads(obj.fields)
        return None


class NeuroTaggerTagDocumentSerializer(serializers.Serializer):
    doc = serializers.JSONField()
    threshold = serializers.FloatField(default=0.3, help_text=f'Filter out tags with a lower than threshold probaility. Default: {choices.DEFAULT_THRESHOLD_VALUE}')

class NeuroTaggerTagTextSerializer(serializers.Serializer):
    text = serializers.CharField()
    threshold = serializers.FloatField(default=0.3, help_text=f'Filter out tags with a lower than threshold probaility. Default: {choices.DEFAULT_THRESHOLD_VALUE}')
