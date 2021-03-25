from rest_framework import serializers

from toolkit.core.task.serializers import TaskSerializer
from toolkit.elastic.index.serializers import IndexSerializer
from toolkit.elastic.tools.searcher import EMPTY_QUERY
from toolkit.serializer_constants import FieldParseSerializer, ProjectResourceUrlSerializer
from toolkit.torchtagger import choices
from toolkit.torchtagger.models import TorchTagger


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


class EpochReportSerializer(serializers.Serializer):
    ignore_fields = serializers.ListField(child=serializers.CharField(), default=choices.DEFAULT_REPORT_IGNORE_FIELDS, required=False, help_text=f'Fields to exclude from the output. Default = {choices.DEFAULT_REPORT_IGNORE_FIELDS}')


class TagRandomDocSerializer(serializers.Serializer):
    indices = IndexSerializer(many=True, default=[])


class TorchTaggerSerializer(FieldParseSerializer, serializers.ModelSerializer, ProjectResourceUrlSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.')
    query = serializers.JSONField(help_text='Query in JSON format', required=False)
    indices = IndexSerializer(many=True, default=[])
    fact_name = serializers.CharField(default=None, required=False, help_text=f'Fact name used to filter tags (fact values). Default: None')
    model_architecture = serializers.ChoiceField(choices=choices.MODEL_CHOICES)
    maximum_sample_size = serializers.IntegerField(default=choices.DEFAULT_MAX_SAMPLE_SIZE, required=False)
    minimum_sample_size = serializers.IntegerField(default=choices.DEFAULT_MIN_SAMPLE_SIZE, required=False)
    num_epochs = serializers.IntegerField(default=choices.DEFAULT_NUM_EPOCHS, required=False)

    task = TaskSerializer(read_only=True)
    plot = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()


    class Meta:
        model = TorchTagger
        fields = (
            'url', 'author_username', 'id', 'description', 'query', 'fields', 'embedding', 'f1_score', 'precision', 'recall', 'accuracy',
            'model_architecture', 'maximum_sample_size', 'minimum_sample_size', 'num_epochs', 'plot', 'task', 'fact_name', 'indices', 'confusion_matrix'
        )
        read_only_fields = ('project', 'fields', 'f1_score', 'precision', 'recall', 'accuracy', 'plot', 'task', 'fact_name', 'confusion_matrix')
        fields_to_parse = ['fields']
