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

    completed_taggers = serializers.SerializerMethodField()

    class Meta:
        model = HybridTagger
        fields = ('id', 'project', 'author', 'description', 'fact_name', 'minimum_sample_size', 'taggers', 'completed_taggers', 'tagger')
        read_only_fields = ('author', 'project', 'taggers', 'completed_taggers')
    
    def get_completed_taggers(self, obj):
        total_taggers = HybridTagger.objects.get(id=obj.id).taggers
        completed_taggers = total_taggers.filter(task__status='completed')
        return '{0}/{1}'.format(len(completed_taggers), len(total_taggers.all()))
