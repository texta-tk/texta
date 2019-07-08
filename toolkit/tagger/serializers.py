import json
from rest_framework import serializers
from django.db.models import Avg

from toolkit.tagger.models import Tagger, TaggerGroup

from toolkit.tagger.choices import (get_field_choices, get_classifier_choices, get_vectorizer_choices, get_feature_selector_choices,
                                    DEFAULT_NEGATIVE_MULTIPLIER, DEFAULT_MAX_SAMPLE_SIZE, DEFAULT_MIN_SAMPLE_SIZE,
                                    DEFAULT_NUM_CANDIDATES, DEFAULT_TAGGER_GROUP_FACT_NAME)

from toolkit.core.task.serializers import TaskSerializer
from toolkit.settings import URL_PREFIX


class TextSerializer(serializers.Serializer):
    text = serializers.CharField()


class DocSerializer(serializers.Serializer):
    doc = serializers.JSONField()


class FeatureListSerializer(serializers.Serializer):
    size = serializers.IntegerField(default=100, help_text='Default: 100')


class TextGroupSerializer(serializers.Serializer):
    text = serializers.CharField(help_text=f'Raw text input.')
    hybrid = serializers.BooleanField(default=True, 
                                      help_text=f'Use hybrid tagging. Default: True')
    show_candidates = serializers.BooleanField(default=False, 
                                      help_text=f'Show tagger candidates prior to supervised filtering. Default: False')
    num_candidates = serializers.IntegerField(default=DEFAULT_NUM_CANDIDATES, 
                                            help_text=f'Number of candidates used in unsupervised prefiltering. Default: {DEFAULT_NUM_CANDIDATES}')


class DocGroupSerializer(serializers.Serializer):
    doc = serializers.JSONField(help_text=f'Document in JSON format.')
    hybrid = serializers.BooleanField(default=True, 
                                      help_text=f'Use hybrid tagging. Default: True')
    show_candidates = serializers.BooleanField(default=False, 
                                      help_text=f'Show tagger candidates prior to supervised filtering. Default: False')
    num_candidates = serializers.IntegerField(default=DEFAULT_NUM_CANDIDATES, 
                                            help_text=f'Number of candidates used in unsupervised prefiltering. Default: {DEFAULT_NUM_CANDIDATES}')


class TaggerSerializer(serializers.ModelSerializer):
    description = serializers.CharField(help_text=f'Description for the Tagger. Will be used as tag.')
    fields = serializers.MultipleChoiceField(choices=get_field_choices(), required=True, help_text=f'Fields used to build the model.')
    vectorizer = serializers.ChoiceField(choices=get_vectorizer_choices(), help_text=f'Vectorizer algorithm to create document vectors. NB! HashingVectorizer does not support feature name extraction!')
    classifier = serializers.ChoiceField(choices=get_classifier_choices(),help_text=f'Classification algorithm used in the model.')
    negative_multiplier = serializers.IntegerField(default=DEFAULT_NEGATIVE_MULTIPLIER,
                                                   help_text=f'Multiplies the size of positive samples to determine negative example set size. Default: {DEFAULT_NEGATIVE_MULTIPLIER}')
    maximum_sample_size = serializers.IntegerField(default=DEFAULT_MAX_SAMPLE_SIZE,
                                                   help_text=f'Maximum number of documents used to build a model. Default: {DEFAULT_MAX_SAMPLE_SIZE}')
    feature_selector = serializers.ChoiceField(choices=get_feature_selector_choices(),
                                               help_text=f'Feature selection algorithm to decrease the number of features.')
    task = TaskSerializer(read_only=True)
    plot = serializers.SerializerMethodField()
    stop_words = serializers.SerializerMethodField()


    class Meta:
        model = Tagger
        fields = ('id', 'description', 'query', 'fields', 'embedding', 'vectorizer', 'classifier', 'feature_selector', 'stop_words',
                  'maximum_sample_size', 'negative_multiplier', 'location', 'precision', 'recall', 'f1_score', 'num_features', 'plot', 'task')
        read_only_fields = ('location', 'stop_words', 'precision', 'recall', 'f1_score', 'num_features', 'plot')

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
        else:
            return None
    
    def get_stop_words(self, obj):
        return json.loads(obj.stop_words)



class TaggerGroupSerializer(serializers.ModelSerializer):
    description = serializers.CharField(help_text=f'Description for the Tagger Group.')
    minimum_sample_size = serializers.IntegerField(default=DEFAULT_MIN_SAMPLE_SIZE, help_text=f'Minimum number of documents required to train a model. Default: {DEFAULT_MIN_SAMPLE_SIZE}')
    fact_name = serializers.CharField(default=DEFAULT_TAGGER_GROUP_FACT_NAME, help_text=f'Fact name used to filter tags (fact values). Default: {DEFAULT_TAGGER_GROUP_FACT_NAME}')
    taggers = serializers.PrimaryKeyRelatedField(read_only=True, many=True)
    tagger = TaggerSerializer(write_only=True, remove_fields=['description', 'query'])
    tagger_status = serializers.SerializerMethodField()
    tagger_statistics = serializers.SerializerMethodField()

    class Meta:
        model = TaggerGroup
        fields = ('id', 'description', 'fact_name', 'minimum_sample_size', 
                  'taggers', 'tagger_status', 'tagger', 'tagger_statistics')
                  
        read_only_fields = ('taggers',)

    def get_tagger_status(self, obj):
        tagger_objects = TaggerGroup.objects.get(id=obj.id).taggers
        tagger_status = {'total': len(tagger_objects.all()),
                         'completed': len(tagger_objects.filter(task__status='completed')),
                         'training': len(tagger_objects.filter(task__status='running')),
                         'queued': len(tagger_objects.filter(task__status='created')),
                         'failed': len(tagger_objects.filter(task__status='failed'))}
        return tagger_status

    def get_tagger_statistics(self, obj):
        tagger_objects = TaggerGroup.objects.get(id=obj.id).taggers
        tagger_stats = {'avg_precision': tagger_objects.aggregate(Avg('precision'))['precision__avg'],
                        'avg_recall': tagger_objects.aggregate(Avg('recall'))['recall__avg'],
                        'avg_f1_score': tagger_objects.aggregate(Avg('f1_score'))['f1_score__avg']}
        return tagger_stats
