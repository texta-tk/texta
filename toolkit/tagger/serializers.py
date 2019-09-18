import json
import re
from rest_framework import serializers
from django.db.models import Avg

from toolkit.tagger.models import Tagger, TaggerGroup

from toolkit.tagger.choices import (get_field_choices, get_classifier_choices, get_vectorizer_choices, get_feature_selector_choices,
                                    get_tokenizer_choices, DEFAULT_NEGATIVE_MULTIPLIER, DEFAULT_MAX_SAMPLE_SIZE, DEFAULT_MIN_SAMPLE_SIZE,
                                    DEFAULT_NUM_DOCUMENTS, DEFAULT_TAGGER_GROUP_FACT_NAME)

from toolkit.core.task.serializers import TaskSerializer
from toolkit.settings import URL_PREFIX
from toolkit.serializer_constants import ProjectResourceUrlSerializer


class TextSerializer(serializers.Serializer):
    text = serializers.CharField()
    lemmatize = serializers.BooleanField(default=False,
        help_text=f'Use MLP lemmatizer if available. Use only if training data was lemmatized. Default: False')


class DocSerializer(serializers.Serializer):
    doc = serializers.JSONField()
    lemmatize = serializers.BooleanField(default=False,
        help_text=f'Use MLP lemmatizer if available. Use only if training data was lemmatized. Default: False')


class FeatureListSerializer(serializers.Serializer):
    size = serializers.IntegerField(default=100, help_text='Default: 100')


class TextGroupSerializer(serializers.Serializer):
    text = serializers.CharField(help_text=f'Raw text input.')
    lemmatize = serializers.BooleanField(default=False,
        help_text=f'Use MLP lemmatizer if available. Use only if training data was lemmatized. Default: False')
    show_candidates = serializers.BooleanField(default=False, 
        help_text=f'Show tagger candidates prior to supervised filtering. Default: False')
    n_similar_docs = serializers.IntegerField(default=DEFAULT_NUM_DOCUMENTS, 
        help_text=f'Number of documents used in unsupervised prefiltering. Default: {DEFAULT_NUM_DOCUMENTS}')


class DocGroupSerializer(serializers.Serializer):
    doc = serializers.JSONField(help_text=f'Document in JSON format.')
    lemmatize = serializers.BooleanField(default=False,
        help_text=f'Use MLP lemmatizer if available. Use only if training data was lemmatized. Default: False')
    hybrid = serializers.BooleanField(default=True, 
        help_text=f'Use hybrid tagging. Default: True')
    show_candidates = serializers.BooleanField(default=False, 
        help_text=f'Show tagger candidates prior to supervised filtering. Default: False')
    n_similar_docs = serializers.IntegerField(default=DEFAULT_NUM_DOCUMENTS, 
        help_text=f'Number of documents used in unsupervised prefiltering. Default: {DEFAULT_NUM_DOCUMENTS}')


class TaggerSerializer(serializers.ModelSerializer, ProjectResourceUrlSerializer):
    description = serializers.CharField(help_text=f'Description for the Tagger. Will be used as tag.')
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.', write_only=True)
    vectorizer = serializers.ChoiceField(choices=get_vectorizer_choices(),
        help_text=f'Vectorizer algorithm to create document vectors. NB! HashingVectorizer does not support feature name extraction!')
    classifier = serializers.ChoiceField(choices=get_classifier_choices(), 
        help_text=f'Classification algorithm used in the model.')
    negative_multiplier = serializers.IntegerField(default=DEFAULT_NEGATIVE_MULTIPLIER,
        help_text=f'Multiplies the size of positive samples to determine negative example set size. Default: {DEFAULT_NEGATIVE_MULTIPLIER}')
    maximum_sample_size = serializers.IntegerField(default=DEFAULT_MAX_SAMPLE_SIZE,
        help_text=f'Maximum number of documents used to build a model. Default: {DEFAULT_MAX_SAMPLE_SIZE}')
    task = TaskSerializer(read_only=True)
    plot = serializers.SerializerMethodField()
    stop_words = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    fields_parsed = serializers.SerializerMethodField()
    query = serializers.JSONField(help_text='Query in JSON format')
    url = serializers.SerializerMethodField()

    class Meta:
        model = Tagger
        fields = ('id', 'url', 'description', 'query', 'fields', 'embedding', 'vectorizer', 'classifier', 'stop_words', 'fields_parsed',
                  'maximum_sample_size', 'negative_multiplier', 'location', 'precision', 'recall', 'f1_score', 'num_features', 'plot', 'task')
        read_only_fields = ('precision', 'recall', 'f1_score', 'num_features')

    def __init__(self, *args, **kwargs):
        '''
        Add the ability to pass extra arguments such as "remove_fields".
        Useful for the Serializer eg in another Serializer, without making a new one.
        '''
        remove_fields = kwargs.pop('remove_fields', None)
        super(TaggerSerializer, self).__init__(*args, **kwargs)

        if remove_fields:
            # for multiple fields in a list
            for field_name in remove_fields:
                self.fields.pop(field_name)
    
    def get_plot(self, obj):
        if obj.plot:
            return '{0}/{1}'.format(URL_PREFIX, obj.plot)
        return None

    def get_stop_words(self, obj):
        if obj.stop_words:
            return json.loads(obj.stop_words)
        return None

    def get_location(self, obj):
        if obj.location:
            return json.loads(obj.location)
        return None

    def get_fields_parsed(self, obj):
        if obj.fields:
            return json.loads(obj.fields)
        return None


class TaggerGroupSerializer(serializers.ModelSerializer, ProjectResourceUrlSerializer):
    description = serializers.CharField(help_text=f'Description for the Tagger Group.')
    minimum_sample_size = serializers.IntegerField(default=DEFAULT_MIN_SAMPLE_SIZE, help_text=f'Minimum number of documents required to train a model. Default: {DEFAULT_MIN_SAMPLE_SIZE}')
    fact_name = serializers.CharField(default=DEFAULT_TAGGER_GROUP_FACT_NAME, help_text=f'Fact name used to filter tags (fact values). Default: {DEFAULT_TAGGER_GROUP_FACT_NAME}')
    tagger = TaggerSerializer(write_only=True, remove_fields=['description', 'query'])
    tagger_status = serializers.SerializerMethodField()
    tagger_statistics = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = TaggerGroup
        fields = ('id', 'url', 'description', 'fact_name', 'minimum_sample_size', 
                  'tagger_status', 'tagger', 'tagger_statistics')

    def get_tagger_status(self, obj):
        tagger_objects = TaggerGroup.objects.get(id=obj.id).taggers
        tagger_status = {'total': len(tagger_objects.all()),
                         'completed': len(tagger_objects.filter(task__status='completed')),
                         'training': len(tagger_objects.filter(task__status='running')),
                         'created': len(tagger_objects.filter(task__status='created')),
                         'failed': len(tagger_objects.filter(task__status='failed'))}
        return tagger_status

    def get_tagger_statistics(self, obj):
        tagger_objects = TaggerGroup.objects.get(id=obj.id).taggers
        tagger_stats = {'avg_precision': tagger_objects.aggregate(Avg('precision'))['precision__avg'],
                        'avg_recall': tagger_objects.aggregate(Avg('recall'))['recall__avg'],
                        'avg_f1_score': tagger_objects.aggregate(Avg('f1_score'))['f1_score__avg']}
        return tagger_stats
