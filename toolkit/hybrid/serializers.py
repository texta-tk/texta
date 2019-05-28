from rest_framework import serializers
from toolkit.tagger.models import Tagger
from toolkit.tagger.serializers import TaggerSerializer
from toolkit.hybrid.models import HybridTagger
from toolkit.hybrid.choices import get_fact_names, HYBRID_TAGGER_CHOICES
from toolkit.tagger.choices import get_classifier_choices, get_vectorizer_choices, TAGGER_CHOICES

from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.embedding.models import Embedding


class HybridTaggerTextSerializer(serializers.Serializer):
    taggers = serializers.PrimaryKeyRelatedField(queryset=Tagger.objects.filter(task__status='completed'), many=True)
    text = serializers.CharField()
    hybrid_mode = serializers.BooleanField()


class HybridTaggerSerializer(serializers.HyperlinkedModelSerializer):
    description = serializers.CharField()
    minimum_sample_size = serializers.ChoiceField(choices=HYBRID_TAGGER_CHOICES['min_freq'])
    fact_name = serializers.ChoiceField(choices=get_fact_names())
    taggers = serializers.HyperlinkedRelatedField(read_only=True, many=True, view_name='tagger-detail')
    tagger = TaggerSerializer(write_only=True)
    tagger_status = serializers.SerializerMethodField()

    class Meta:
        model = HybridTagger
        fields = ('id', 'project', 'author', 'description', 'fact_name', 'minimum_sample_size', 'taggers', 'tagger_status', 'tagger')
        read_only_fields = ('author', 'project', 'taggers', 'tagger_status')


    def get_tagger_status(self, obj):
        tagger_objects = HybridTagger.objects.get(id=obj.id).taggers
        tagger_status = {'total': len(tagger_objects.all()),
                        'completed': len(tagger_objects.filter(task__status='completed')),
                        'training': len(tagger_objects.filter(task__status='running')),
                        'queued': len(tagger_objects.filter(task__status='created')),
                        'failed': len(tagger_objects.filter(task__status='failed'))}
        return tagger_status
