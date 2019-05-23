from rest_framework import serializers
from toolkit.tagger.models import Tagger
from toolkit.tagger.serializers import SimpleTaggerSerializer
from toolkit.hybrid.models import HybridTagger


class HybridTaggerTextSerializer(serializers.Serializer):
    taggers = serializers.PrimaryKeyRelatedField(queryset=Tagger.objects.filter(task__status='completed'), many=True)
    text = serializers.CharField()
    hybrid_mode = serializers.BooleanField()


class HybridTaggerDocSerializer(serializers.Serializer):
    taggers = serializers.PrimaryKeyRelatedField(queryset=Tagger.objects.all(), many=True)
    doc = serializers.JSONField()


class HybridTaggerSerializer(serializers.HyperlinkedModelSerializer):
    taggers = serializers.PrimaryKeyRelatedField(read_only=True)
    #task = TaskSerializer(read_only=True)
    #fields = serializers.MultipleChoiceField(choices=get_field_choices())
    #num_dimensions = serializers.ChoiceField(choices=EMBEDDING_CHOICES['num_dimensions'])
    #max_vocab = serializers.ChoiceField(choices=EMBEDDING_CHOICES['max_vocab'])
    #min_freq = serializers.ChoiceField(choices=EMBEDDING_CHOICES['min_freq'])
    
    class Meta:
        model = HybridTagger
        fields = ('taggers',)
        #read_only_fields = ('vocab_size')
