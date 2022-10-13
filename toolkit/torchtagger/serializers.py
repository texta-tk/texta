import json

from rest_framework import serializers
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.embedding.models import Embedding
from toolkit.serializer_constants import (CommonModelSerializerMixin, ElasticScrollMixIn, FavoriteModelSerializerMixin, FieldParseSerializer, IndicesSerializerMixin, ProjectFilteredPrimaryKeyRelatedField, ProjectResourceUrlSerializer)
from toolkit.torchtagger import choices
from toolkit.torchtagger.models import TorchTagger
from toolkit.validator_constants import validate_pos_label


class ApplyTaggerSerializer(FieldParseSerializer, IndicesSerializerMixin, ElasticScrollMixIn):
    description = serializers.CharField(required=True, help_text="Text for distinguishing this task from others.")
    new_fact_name = serializers.CharField(required=True, help_text="Used as fact name when applying the tagger.")
    new_fact_value = serializers.CharField(required=False, default="", help_text="NB! Only applicable for binary taggers! Used as fact value when applying the tagger. Defaults to tagger description (binary) / tagger result (multiclass).")
    fields = serializers.ListField(required=True, child=serializers.CharField(), help_text="Which fields to extract the text from.")
    query = serializers.JSONField(help_text="Filter the documents which to scroll and apply to.", default=EMPTY_QUERY)


class EpochReportSerializer(serializers.Serializer):
    ignore_fields = serializers.ListField(child=serializers.CharField(), default=choices.DEFAULT_REPORT_IGNORE_FIELDS, required=False, help_text=f'Fields to exclude from the output. Default = {choices.DEFAULT_REPORT_IGNORE_FIELDS}')


class TagRandomDocSerializer(IndicesSerializerMixin):
    pass


class TorchTaggerSerializer(FieldParseSerializer, serializers.ModelSerializer, CommonModelSerializerMixin, IndicesSerializerMixin, ProjectResourceUrlSerializer, FavoriteModelSerializerMixin):
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.')
    query = serializers.JSONField(help_text='Query in JSON format', required=False, default=json.dumps(EMPTY_QUERY))
    fact_name = serializers.CharField(default=None, required=False, help_text=f'Fact name used to filter tags (fact values). Default: None')
    pos_label = serializers.CharField(default="", required=False, allow_blank=True, help_text=f'Fact value used as positive label while evaluating the results. This is needed only, if the selected fact has exactly two possible values. Default = ""')
    model_architecture = serializers.ChoiceField(choices=choices.MODEL_CHOICES)
    maximum_sample_size = serializers.IntegerField(default=choices.DEFAULT_MAX_SAMPLE_SIZE, required=False)
    minimum_sample_size = serializers.IntegerField(default=choices.DEFAULT_MIN_SAMPLE_SIZE, required=False)
    num_epochs = serializers.IntegerField(default=choices.DEFAULT_NUM_EPOCHS, required=False)
    embedding = ProjectFilteredPrimaryKeyRelatedField(queryset=Embedding.objects, many=False, read_only=False, required=True, help_text=f'Embedding to use, usage mandatory.')

    balance = serializers.BooleanField(default=choices.DEFAULT_BALANCE, required=False, help_text=f'Balance sample sizes of different classes. Only applicable for multiclass taggers. Default = {choices.DEFAULT_BALANCE}')
    use_sentence_shuffle = serializers.BooleanField(default=choices.DEFAULT_USE_SENTENCE_SHUFFLE, required=False, help_text=f'Shuffle sentences in added examples. NB! Only applicable for multiclass taggers with balance=True. Default = {choices.DEFAULT_USE_SENTENCE_SHUFFLE}')
    balance_to_max_limit = serializers.BooleanField(default=choices.DEFAULT_BALANCE_TO_MAX_LIMIT, required=False,
                                                    help_text=f'If enabled, the number of samples for each class is set to `maximum_sample_size`. Otherwise, it is set to max class size. NB! Only applicable for multiclass taggers with balance == True. Default = {choices.DEFAULT_BALANCE_TO_MAX_LIMIT}')

    plot = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()


    def validate(self, data):
        # use custom validation for pos label as some other serializer fields are also required
        data = validate_pos_label(data)
        return data


    class Meta:
        model = TorchTagger
        fields = (
            'url', 'author', 'id', 'description', 'query', 'fields', 'embedding', 'f1_score', 'precision', 'recall', 'accuracy',
            'model_architecture', 'maximum_sample_size', 'minimum_sample_size', 'is_favorited', 'num_epochs', 'plot', 'tasks', 'fact_name', 'indices', 'confusion_matrix', 'num_examples', 'balance', 'use_sentence_shuffle', 'balance_to_max_limit', 'pos_label', 'classes'
        )
        read_only_fields = ('project', 'fields', 'f1_score', 'precision', 'recall', 'accuracy', 'plot', 'task', 'confusion_matrix', 'num_examples', 'classes')
        fields_to_parse = ['fields', 'classes']
