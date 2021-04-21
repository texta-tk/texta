import json

from rest_framework import serializers
from toolkit.helper_functions import get_downloaded_bert_models
from toolkit.core.task.serializers import TaskSerializer
from toolkit.elastic.index.serializers import IndexSerializer
from toolkit.elastic.tools.searcher import EMPTY_QUERY
from toolkit.serializer_constants import FieldParseSerializer, ProjectResourceUrlSerializer
from toolkit.bert_tagger import choices
from toolkit.bert_tagger.models import BertTagger
from toolkit.settings import BERT_PRETRAINED_MODEL_DIRECTORY, ALLOW_BERT_MODEL_DOWNLOADS

class ApplyTaggerSerializer(FieldParseSerializer, serializers.Serializer):
    description = serializers.CharField(required=True, help_text="Text for distinguishing this task from others.")
    new_fact_name = serializers.CharField(required=True, help_text="Used as fact name when applying the tagger.")
    new_fact_value = serializers.CharField(required=False, default="", help_text="NB! Only applicable for binary taggers! Used as fact value when applying the tagger. Defaults to tagger description (binary) / tagger result (multiclass).")
    indices = IndexSerializer(many=True, default=[], help_text="Which indices in the project to apply this to.")
    fields = serializers.ListField(required=True, child=serializers.CharField(), help_text="Which fields to extract the text from.")
    query = serializers.JSONField(help_text="Filter the documents which to scroll and apply to.", default=EMPTY_QUERY)
    es_timeout = serializers.IntegerField(default=choices.DEFAULT_ES_TIMEOUT, help_text=f"Elasticsearch scroll timeout in minutes. Default = {choices.DEFAULT_ES_TIMEOUT}.")
    bulk_size = serializers.IntegerField(min_value=1, max_value=10000, default=choices.DEFAULT_BULK_SIZE, help_text=f"How many documents should be sent towards Elasticsearch at once. Default = {choices.DEFAULT_BULK_SIZE}.")
    max_chunk_bytes = serializers.IntegerField(min_value=1, default=choices.DEFAULT_MAX_CHUNK_BYTES, help_text=f"Data size in bytes that Elasticsearch should accept to prevent Entity Too Large errors. Default = {choices.DEFAULT_MAX_CHUNK_BYTES}.")


class BertDownloaderSerializer(serializers.Serializer):
    bert_model = serializers.CharField(required=True, help_text=f'BERT model to download.')


class EpochReportSerializer(serializers.Serializer):
    ignore_fields = serializers.ListField(child=serializers.CharField(), default=choices.DEFAULT_REPORT_IGNORE_FIELDS, required=False, help_text=f'Fields to exclude from the output. Default = {choices.DEFAULT_REPORT_IGNORE_FIELDS}')


class BertTagTextSerializer(serializers.Serializer):
    text = serializers.CharField()
    feedback_enabled = serializers.BooleanField(default=False, help_text='Stores tagged response in Elasticsearch and returns additional url for giving feedback to Tagger. Default: False')


class TagRandomDocSerializer(serializers.Serializer):
    indices = IndexSerializer(many=True, default=[])
    fields = serializers.ListField(child=serializers.CharField(), default=[], required=False, allow_empty=True, help_text = 'Fields to apply the tagger. By default, the tagger is applied to the same fields it was trained on.')


class BertTaggerSerializer(FieldParseSerializer, serializers.ModelSerializer, ProjectResourceUrlSerializer):

    author_username = serializers.CharField(source='author.username', read_only=True)
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.')
    query = serializers.JSONField(required=False, help_text='Query in JSON format')
    indices = IndexSerializer(many=True, default=[])
    fact_name = serializers.CharField(default=None, required=False, help_text=f'Fact name used to filter tags (fact values). Default: None')

    maximum_sample_size = serializers.IntegerField(default=choices.DEFAULT_MAX_SAMPLE_SIZE, required=False, help_text=f'Maximum number of positive examples. Default = {choices.DEFAULT_MAX_SAMPLE_SIZE}')
    minimum_sample_size = serializers.IntegerField(default=choices.DEFAULT_MIN_SAMPLE_SIZE, required=False, help_text=f'Minimum number of negative examples. Default = {choices.DEFAULT_MIN_SAMPLE_SIZE}')
    negative_multiplier = serializers.FloatField(default=choices.DEFAULT_NEGATIVE_MULTIPLIER, required=False, help_text=f'Default={choices.DEFAULT_NEGATIVE_MULTIPLIER}')

    bert_model = serializers.CharField(default=choices.DEFAULT_BERT_MODEL, required=False, help_text=f'Pretrained BERT model to use. Default = {choices.DEFAULT_BERT_MODEL}')
    num_epochs = serializers.IntegerField(default=choices.DEFAULT_NUM_EPOCHS, required=False, help_text=f'Number of training epochs. Default = {choices.DEFAULT_NUM_EPOCHS}')
    max_length = serializers.IntegerField(default=choices.DEFAULT_MAX_LENGTH, required=False, min_value = 1, max_value = 512, help_text=f'Maximum sequence length of BERT tokenized input text used for training. Default = {choices.DEFAULT_MAX_LENGTH}')
    batch_size = serializers.IntegerField(default=choices.DEFAULT_BATCH_SIZE, required=False, help_text=f'Batch size used for training. NB! Autoscaled based on max length if too large. Default = {choices.DEFAULT_BATCH_SIZE}')
    split_ratio = serializers.FloatField(default=choices.DEFAULT_TRAINING_SPLIT, required=False, help_text=f'Proportion of documents used for training; others are used for validation. Default = {choices.DEFAULT_TRAINING_SPLIT}')
    learning_rate = serializers.FloatField(default=choices.DEFAULT_LEARNING_RATE, required=False, help_text=f'Learning rate used while training. Default = {choices.DEFAULT_LEARNING_RATE}')
    eps = serializers.FloatField(default=choices.DEFAULT_EPS, help_text=f'Default = {choices.DEFAULT_EPS}')

    balance = serializers.BooleanField(default=choices.DEFAULT_BALANCE, required=False, help_text=f'Balance sample sizes of different classes. Only applicable for multiclass taggers. Default = {choices.DEFAULT_BALANCE}')
    use_sentence_shuffle = serializers.BooleanField(default=choices.DEFAULT_USE_SENTENCE_SHUFFLE, required=False, help_text=f'Shuffle sentences in added examples. NB! Only applicable for multiclass taggers with balance=True. Default = {choices.DEFAULT_USE_SENTENCE_SHUFFLE}')
    balance_to_max_limit = serializers.BooleanField(default=choices.DEFAULT_BALANCE_TO_MAX_LIMIT, required=False, help_text=f'If enabled, the number of samples for each class is set to `maximum_sample_size`. Otherwise, it is set to max class size. NB! Only applicable for multiclass taggers with balance=True. Default = {choices.DEFAULT_BALANCE_TO_MAX_LIMIT}')

    task = TaskSerializer(read_only=True)
    plot = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    def validate_bert_model(self, bert_model):
        available_models = get_downloaded_bert_models(BERT_PRETRAINED_MODEL_DIRECTORY)
        if not bert_model in available_models:
            if ALLOW_BERT_MODEL_DOWNLOADS:
                raise serializers.ValidationError(f"Model '{bert_model}' is not downloaded. Please download it first via action 'Download pretrained model'. Currently available models: {available_models}.")
            else:
                raise serializers.ValidationError(f"Model '{bert_model}' is not downloaded. Downloading models via API is disabled. Please contact you system administrator to make it available. Currently available models: {available_models}.")
        return bert_model

    class Meta:
        model = BertTagger
        fields = ('url', 'author_username', 'id', 'description', 'query', 'fields', 'f1_score', 'precision', 'recall', 'accuracy',
                  'validation_loss', 'training_loss', 'maximum_sample_size', 'minimum_sample_size', 'num_epochs', 'plot', 'task', 'fact_name',
                  'indices', 'bert_model', 'learning_rate', 'eps', 'max_length', 'batch_size', 'adjusted_batch_size',
                  'split_ratio','negative_multiplier', 'num_examples', 'confusion_matrix', 'balance', 'use_sentence_shuffle', 'balance_to_max_limit')

        read_only_fields = ('project', 'fields', 'f1_score', 'precision', 'recall', 'accuracy', 'validation_loss', 'training_loss', 'plot',
                            'task', 'fact_name', 'num_examples', 'adjusted_batch_size', 'confusion_matrix')

        fields_to_parse = ['fields']
