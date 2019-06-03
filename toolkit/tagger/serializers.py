from rest_framework import serializers
from django.db.models import Avg

from toolkit.core.task.models import Task
from toolkit.tagger.models import Tagger, TaggerGroup

from toolkit.tagger.choices import (get_fact_names, 
                                    get_field_choices, get_classifier_choices, get_vectorizer_choices,
                                    DEFAULT_NEGATIVE_MULTIPLIER, DEFAULT_MAX_SAMPLE_SIZE, DEFAULT_MIN_SAMPLE_SIZE)

from toolkit.core.task.serializers import TaskSerializer
from toolkit.settings import URL_PREFIX


class TextSerializer(serializers.Serializer):
    text = serializers.CharField()


class DocSerializer(serializers.Serializer):
    doc = serializers.JSONField()


class TextGroupSerializer(serializers.Serializer):
    text = serializers.CharField()
    hybrid = serializers.BooleanField(default=True)


class DocGroupSerializer(serializers.Serializer):
    doc = serializers.JSONField()
    hybrid = serializers.BooleanField(default=True)


class TaggerSerializer(serializers.ModelSerializer):
    fields = serializers.MultipleChoiceField(choices=get_field_choices(), required=True)
    vectorizer = serializers.ChoiceField(choices=get_vectorizer_choices())
    classifier = serializers.ChoiceField(choices=get_classifier_choices())
    negative_multiplier = serializers.IntegerField(default=DEFAULT_NEGATIVE_MULTIPLIER,
                                                   help_text=f'Default: {DEFAULT_NEGATIVE_MULTIPLIER}')
    maximum_sample_size = serializers.IntegerField(default=DEFAULT_MAX_SAMPLE_SIZE,
                                                   help_text=f'Default: {DEFAULT_MAX_SAMPLE_SIZE}')

    task = TaskSerializer(read_only=True)

    class Meta:
        model = Tagger
        fields = ('url', 'id', 'description', 'project', 'author', 'query',
                  'fields', 'embedding', 'vectorizer', 'classifier', 'maximum_sample_size', 'negative_multiplier',
                  'location', 'precision', 'recall', 'f1_score', 'confusion_matrix', 'plot', 'task')

        read_only_fields = ('author', 'project', 'location',
                            'precision', 'recall', 'f1_score', 'confusion_matrix', 'plot')

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
        return '{0}/{1}'.format(URL_PREFIX, obj.plot)


class TaggerGroupSerializer(serializers.HyperlinkedModelSerializer):
    description = serializers.CharField()
    minimum_sample_size = serializers.IntegerField(default=DEFAULT_MIN_SAMPLE_SIZE, help_text=f'Default: {DEFAULT_MIN_SAMPLE_SIZE}')
    fact_name = serializers.ChoiceField(choices=get_fact_names())
    taggers = serializers.HyperlinkedRelatedField(read_only=True, many=True, view_name='tagger-detail')
    tagger = TaggerSerializer(write_only=True, remove_fields=['description', 'query'])
    tagger_status = serializers.SerializerMethodField()
    tagger_statistics = serializers.SerializerMethodField()

    class Meta:
        model = TaggerGroup
        fields = ('id', 'project', 'author', 'description', 'fact_name', 'minimum_sample_size', 
                  'taggers', 'tagger_status', 'tagger', 'tagger_statistics')
                  
        read_only_fields = ('author', 'project', 'taggers')

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
