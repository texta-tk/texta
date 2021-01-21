from rest_framework import serializers

from toolkit.core.task.serializers import TaskSerializer
from toolkit.elastic.serializers import IndexSerializer
from toolkit.serializer_constants import FieldParseSerializer, ProjectResourceUrlSerializer
from toolkit.bert_tagger import choices
from toolkit.bert_tagger.models import BertTagger
import json

class EpochReportSerializer(serializers.Serializer):
    ignore_fields = serializers.ListField(child=serializers.CharField(), default=choices.DEFAULT_REPORT_IGNORE_FIELDS, required=False, help_text=f'Fields to exclude from the output. Default = {choices.DEFAULT_REPORT_IGNORE_FIELDS}')
    # TODO: add fields validation

class BertTagTextSerializer(serializers.Serializer):
    text = serializers.CharField()
    feedback_enabled = serializers.BooleanField(default=False, help_text='Stores tagged response in Elasticsearch and returns additional url for giving feedback to Tagger. Default: False')

class TagRandomDocSerializer(serializers.Serializer):
    indices = IndexSerializer(many=True, default=[])
    fields = serializers.ListField(child=serializers.CharField(), required=True, allow_empty=False)


class BertTaggerSerializer(FieldParseSerializer, serializers.ModelSerializer, ProjectResourceUrlSerializer):
    # TODO: Review
    # TODO: HELPTEXTS!!
    author_username = serializers.CharField(source='author.username', read_only=True)
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.')
    query = serializers.JSONField(help_text='Query in JSON format', required=False)
    indices = IndexSerializer(many=True, default=[])
    fact_name = serializers.CharField(default=None, required=False, help_text=f'Fact name used to filter tags (fact values). Default: None')

    maximum_sample_size = serializers.IntegerField(default=choices.DEFAULT_MAX_SAMPLE_SIZE, required=False, help_text=f'Maximum number of positive examples. Default = {choices.DEFAULT_MAX_SAMPLE_SIZE}')
    minimum_sample_size = serializers.IntegerField(default=choices.DEFAULT_MIN_SAMPLE_SIZE, required=False, help_text=f'Minimum number of negative examples. Default = {choices.DEFAULT_MIN_SAMPLE_SIZE}')
    negative_multiplier = serializers.FloatField(default=choices.DEFAULT_NEGATIVE_MULTIPLIER, required=False, help_text=f'Default={choices.DEFAULT_NEGATIVE_MULTIPLIER}')

    # BERT params
    num_epochs = serializers.IntegerField(default=choices.DEFAULT_NUM_EPOCHS, required=False, help_text=f'Number of training epochs. Default = {choices.DEFAULT_NUM_EPOCHS}')
    bert_model = serializers.CharField(default=choices.DEFAULT_BERT_MODEL, required=False, help_text=f'Pretrained BERT model to use. Default = {choices.DEFAULT_BERT_MODEL}')
    max_length = serializers.IntegerField(default=choices.DEFAULT_MAX_LENGTH, required=False, help_text=f'Maximum sequence length of BERT tokenized input text used for training. Default = {choices.DEFAULT_MAX_LENGTH}')
    batch_size = serializers.IntegerField(default=choices.DEFAULT_BATCH_SIZE, required=False, help_text=f'Batch size used for training. NB! Autoscaled based on max length if too large. Default = {choices.DEFAULT_BATCH_SIZE}')
    split_ratio = serializers.FloatField(default=choices.DEFAULT_TRAINING_SPLIT, required=False, help_text=f'Proportion of documents used for training; others are used for validation. Default = {choices.DEFAULT_TRAINING_SPLIT}')
    learning_rate = serializers.FloatField(default=choices.DEFAULT_LEARNING_RATE, required=False, help_text=f'Learning rate used while training. Default = {choices.DEFAULT_LEARNING_RATE}')
    eps = serializers.FloatField(default=choices.DEFAULT_EPS, help_text=f'Default = {choices.DEFAULT_EPS}')


    task = TaskSerializer(read_only=True)
    plot = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()


    class Meta:
        # TODO: check fields
        model = BertTagger
        fields = (
            'url',
            'author_username',
            'id',
            'description',
            'query',
            'fields',
            'f1_score',
            'precision',
            'recall',
            'accuracy',
            'validation_loss',
            'training_loss',
            'maximum_sample_size',
            'minimum_sample_size',
            'num_epochs',
            'plot',
            'task',
            'fact_name',
            'indices',
            'bert_model',
            'learning_rate',
            'eps',
            'max_length',
            'batch_size',
            'split_ratio',
            'negative_multiplier'
        )
        read_only_fields = (
            'project',
            'fields',
            'f1_score',
            'precision',
            'recall',
            'accuracy',
            'validation_loss',
            'training_loss',
            'plot',
            'task',
            'fact_name'
        )
        fields_to_parse = ['fields']
