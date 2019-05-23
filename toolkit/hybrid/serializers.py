from rest_framework import serializers
from toolkit.tagger.models import Tagger
from toolkit.tagger.serializers import TaggerSerializer
from toolkit.hybrid.models import HybridTagger
from toolkit.hybrid.choices import get_fact_names, HYBRID_TAGGER_CHOICES
from toolkit.tagger.choices import get_classifier_choices, get_vectorizer_choices, TAGGER_CHOICES

from toolkit.embedding.models import Embedding


class HybridTaggerTextSerializer(serializers.Serializer):
    taggers = serializers.PrimaryKeyRelatedField(queryset=Tagger.objects.filter(task__status='completed'), many=True)
    text = serializers.CharField()
    hybrid_mode = serializers.BooleanField()


class HybridTaggerSerializer(serializers.HyperlinkedModelSerializer):
    description = serializers.CharField()

    minimum_sample_size = serializers.ChoiceField(choices=HYBRID_TAGGER_CHOICES['min_freq'])
    fact_name = serializers.ChoiceField(choices=get_fact_names())
    taggers = serializers.StringRelatedField(read_only=True)

    tagger = TaggerSerializer(write_only=True)

    class Meta:
        model = HybridTagger
        fields = ('project', 'author', 'description', 'fact_name', 'minimum_sample_size', 'taggers', 'tagger')
        read_only_fields = ('author', 'project', 'taggers')

    def create(self, validated_data):
        tagger_data = validated_data.pop('tagger')

        hybrid_tagger = HybridTagger.objects.create(**validated_data)
        #for tagger_data in taggers_data:
        #    Tagger.objects.create(**tagger_data)
        return hybrid_tagger
