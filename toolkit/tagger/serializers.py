import json

from django.db.models import Avg, Sum
from rest_framework import serializers

from toolkit.core.task.serializers import TaskSerializer
from toolkit.serializer_constants import FieldParseSerializer, ProjectResourceUrlSerializer
from toolkit.tagger.choices import (DEFAULT_MAX_SAMPLE_SIZE, DEFAULT_MIN_SAMPLE_SIZE, DEFAULT_NEGATIVE_MULTIPLIER, DEFAULT_NUM_DOCUMENTS, DEFAULT_TAGGER_GROUP_FACT_NAME, get_classifier_choices, get_vectorizer_choices)
from toolkit.tagger.models import Tagger, TaggerGroup
from toolkit.tools.logger import Logger


class TaggerTagTextSerializer(serializers.Serializer):
    text = serializers.CharField()
    lemmatize = serializers.BooleanField(default=False, help_text='Use MLP lemmatizer if available. Use only if training data was lemmatized. Default: False')
    feedback_enabled = serializers.BooleanField(default=False, help_text='Stores tagged response in Elasticsearch and returns additional url for giving feedback to Tagger. Default: False')


class TaggerTagDocumentSerializer(serializers.Serializer):
    doc = serializers.JSONField()
    lemmatize = serializers.BooleanField(default=False, help_text=f'Use MLP lemmatizer if available. Use only if training data was lemmatized. Default: False')
    feedback_enabled = serializers.BooleanField(default=False, help_text='Stores tagged response in Elasticsearch and returns additional url for giving feedback to Tagger. Default: False')


class TaggerListFeaturesSerializer(serializers.Serializer):
    size = serializers.IntegerField(default=100, help_text='Default: 100')


class TaggerGroupTagTextSerializer(serializers.Serializer):
    text = serializers.CharField(help_text=f'Raw text input.')
    lemmatize = serializers.BooleanField(default=True, help_text=f'Use MLP lemmatizer to lemmatize input text. Use only if training data was lemmatized. Default: True')
    use_ner = serializers.BooleanField(default=True, help_text=f'Use MLP Named Entity Recognition to detect tag candidates. Default: True')
    n_similar_docs = serializers.IntegerField(default=DEFAULT_NUM_DOCUMENTS, help_text=f'Number of documents used in unsupervised prefiltering. Default: {DEFAULT_NUM_DOCUMENTS}')
    feedback_enabled = serializers.BooleanField(default=False, help_text='Stores tagged response in Elasticsearch and returns additional url for giving feedback to Tagger. Default: False')


class TaggerGroupTagDocumentSerializer(serializers.Serializer):
    doc = serializers.JSONField(help_text=f'Document in JSON format.')
    lemmatize = serializers.BooleanField(default=True, help_text=f'Use MLP lemmatizer if available. Use only if training data was lemmatized. Default: True')
    use_ner = serializers.BooleanField(default=True, help_text=f'Use MLP Named Entity Recognition to detect tag candidates. Default: True')
    n_similar_docs = serializers.IntegerField(default=DEFAULT_NUM_DOCUMENTS, help_text=f'Number of documents used in unsupervised prefiltering. Default: {DEFAULT_NUM_DOCUMENTS}')
    feedback_enabled = serializers.BooleanField(default=False, help_text='Stores tagged response in Elasticsearch and returns additional url for giving feedback to Tagger. Default: False')


class TaggerSerializer(FieldParseSerializer, serializers.ModelSerializer, ProjectResourceUrlSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    description = serializers.CharField(help_text=f'Description for the Tagger. Will be used as tag.')
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.')
    vectorizer = serializers.ChoiceField(choices=get_vectorizer_choices(), help_text=f'Vectorizer algorithm to create document vectors. NB! HashingVectorizer does not support feature name extraction!')
    classifier = serializers.ChoiceField(choices=get_classifier_choices(), help_text=f'Classification algorithm used in the model.')
    negative_multiplier = serializers.IntegerField(default=DEFAULT_NEGATIVE_MULTIPLIER, help_text=f'Multiplies the size of positive samples to determine negative example set size. Default: {DEFAULT_NEGATIVE_MULTIPLIER}')
    maximum_sample_size = serializers.IntegerField(default=DEFAULT_MAX_SAMPLE_SIZE, help_text=f'Maximum number of documents used to build a model. Default: {DEFAULT_MAX_SAMPLE_SIZE}')
    task = TaskSerializer(read_only=True)
    plot = serializers.SerializerMethodField()
    query = serializers.JSONField(help_text='Query in JSON format', required=False)
    url = serializers.SerializerMethodField()


    class Meta:
        model = Tagger
        fields = ('id', 'url', 'author_username', 'description', 'query', 'fields', 'embedding', 'vectorizer', 'classifier', 'stop_words',
                  'maximum_sample_size', 'negative_multiplier', 'precision', 'recall', 'f1_score', 'num_features', 'plot', 'task')
        read_only_fields = ('precision', 'recall', 'f1_score', 'num_features', 'stop_words')
        fields_to_parse = ('fields',)


    def __init__(self, *args, **kwargs):
        """
        Add the ability to pass extra arguments such as "remove_fields".
        Useful for the Serializer eg in another Serializer, without making a new one.
        """
        remove_fields = kwargs.pop('remove_fields', None)
        super(TaggerSerializer, self).__init__(*args, **kwargs)

        if remove_fields:
            # for multiple fields in a list
            for field_name in remove_fields:
                self.fields.pop(field_name)


class TaggerGroupSerializer(serializers.ModelSerializer, ProjectResourceUrlSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    description = serializers.CharField(help_text=f'Description for the Tagger Group.')
    minimum_sample_size = serializers.IntegerField(default=DEFAULT_MIN_SAMPLE_SIZE, help_text=f'Minimum number of documents required to train a model. Default: {DEFAULT_MIN_SAMPLE_SIZE}')
    fact_name = serializers.CharField(default=DEFAULT_TAGGER_GROUP_FACT_NAME, help_text=f'Fact name used to filter tags (fact values). Default: {DEFAULT_TAGGER_GROUP_FACT_NAME}')
    tagger = TaggerSerializer(write_only=True, remove_fields=['description', 'query'])
    num_tags = serializers.IntegerField(read_only=True)
    tagger_status = serializers.SerializerMethodField()
    tagger_statistics = serializers.SerializerMethodField()
    tagger_params = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()


    class Meta:
        model = TaggerGroup
        fields = ('id', 'url', 'author_username', 'description', 'fact_name', 'num_tags', 'minimum_sample_size',
                  'tagger_status', 'tagger_params', 'tagger', 'tagger_statistics')


    def get_tagger_status(self, obj):
        tagger_objects = obj.taggers
        tagger_status = {
            'total': obj.num_tags,
            'completed': len(tagger_objects.filter(task__status='completed')),
            'training': len(tagger_objects.filter(task__status='running')),
            'created': len(tagger_objects.filter(task__status='created')),
            'failed': len(tagger_objects.filter(task__status='failed'))
        }
        return tagger_status


    def get_tagger_statistics(self, obj):
        tagger_objects = obj.taggers
        if tagger_objects.exists():
            try:
                tagger_size_sum = round(tagger_objects.filter(model_size__isnull=False).aggregate(Sum('model_size'))['model_size__sum'], 1)
            except TypeError as e:
                Logger().error(str(e), exc_info=True)
                tagger_size_sum = 0
            tagger_stats = {
                'avg_precision': tagger_objects.aggregate(Avg('precision'))['precision__avg'],
                'avg_recall': tagger_objects.aggregate(Avg('recall'))['recall__avg'],
                'avg_f1_score': tagger_objects.aggregate(Avg('f1_score'))['f1_score__avg'],
                'sum_size': tagger_size_sum
            }
            return tagger_stats


    def get_tagger_params(self, obj):
        if obj.taggers.exists():
            first_tagger = obj.taggers.first()
            params = {
                'fields': json.loads(first_tagger.fields),
                'vectorizer': first_tagger.vectorizer,
                'classifier': first_tagger.classifier
            }
            return params
