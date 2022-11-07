import json
import logging

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Avg, Sum
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.core.task.models import Task
from toolkit.core.user_profile.serializers import UserSerializer
from toolkit.elastic.choices import DEFAULT_SNOWBALL_LANGUAGE, get_snowball_choices
from toolkit.embedding.models import Embedding
from toolkit.helper_functions import load_stop_words
from toolkit.serializer_constants import (CommonModelSerializerMixin, ElasticScrollMixIn, FavoriteModelSerializerMixin, FieldParseSerializer, IndicesSerializerMixin,
                                          ProjectFilteredPrimaryKeyRelatedField, ProjectResourceUrlSerializer)
from toolkit.tagger import choices
from toolkit.tagger.models import Tagger, TaggerGroup
from toolkit.validator_constants import validate_pos_label


# NB! Currently not used
class ApplyTaggersSerializer(FieldParseSerializer, IndicesSerializerMixin, ElasticScrollMixIn):
    author = UserSerializer(read_only=True)
    description = serializers.CharField(required=True, help_text="Text for distinguishing this task from others.")
    new_fact_name = serializers.CharField(required=True, help_text="Used as fact name when applying the tagger.")
    fields = serializers.ListField(required=True, child=serializers.CharField(), help_text="Which fields to extract the text from.")
    query = serializers.JSONField(help_text='Filter the documents which to scroll and apply to.', default=EMPTY_QUERY)
    lemmatize = serializers.BooleanField(default=False, help_text='Use MLP lemmatizer if available. Use only if training data was lemmatized. Default: False')
    # num_tags = serializers.IntegerField(read_only=True)
    taggers = serializers.ListField(
        help_text='List of Tagger IDs to be used.',
        child=serializers.IntegerField(),
        default=[]
    )

    def validate_taggers(self, taggers):
        invalid_ids = []
        for tagger_id in taggers:
            try:
                tagger = Tagger.objects.get(pk=tagger_id)
            except ObjectDoesNotExist:
                invalid_ids.append(tagger_id)
        if invalid_ids:
            raise serializers.ValidationError(f"Taggers with following IDs do not exist: {invalid_ids}")
        return taggers


class ApplyTaggerSerializer(FieldParseSerializer, IndicesSerializerMixin, ElasticScrollMixIn):
    description = serializers.CharField(required=True, help_text="Text for distinguishing this task from others.")
    new_fact_name = serializers.CharField(required=True, help_text="Used as fact name when applying the tagger.")
    new_fact_value = serializers.CharField(required=False, default="",
                                           help_text="NB! Only applicable for binary taggers! Used as fact value when applying the tagger. Defaults to tagger description (binary) / tagger result (multiclass).")
    fields = serializers.ListField(required=True, child=serializers.CharField(), help_text="Which fields to extract the text from.")
    query = serializers.JSONField(help_text='Filter the documents which to scroll and apply to.', default=EMPTY_QUERY)
    lemmatize = serializers.BooleanField(default=False, help_text='Use MLP lemmatizer if available. Use only if training data was lemmatized. Default: False')


class ApplyTaggerGroupSerializer(FieldParseSerializer, IndicesSerializerMixin, ElasticScrollMixIn):
    description = serializers.CharField(required=True, help_text="Text for distinguishing this task from others.")
    new_fact_name = serializers.CharField(required=True, help_text="Used as fact name when applying the tagger.")
    fields = serializers.ListField(required=True, child=serializers.CharField(), help_text=f"Fields used for the predictions.")
    query = serializers.JSONField(help_text=f"Filter the documents which to scroll and apply to. Default = all documents.", default=EMPTY_QUERY)
    lemmatize = serializers.BooleanField(default=choices.DEFAULT_LEMMATIZE,
                                         help_text=f"Use MLP lemmatizer if available. Use only if training data was lemmatized. Default:{choices.DEFAULT_LEMMATIZE}.")
    use_ner = serializers.BooleanField(default=choices.DEFAULT_USE_NER, help_text=f"Use MLP Named Entity Recognition to detect tag candidates. Default:{choices.DEFAULT_USE_NER}.")
    n_similar_docs = serializers.IntegerField(default=choices.DEFAULT_NUM_DOCUMENTS,
                                              help_text=f"Number of documents used in unsupervised prefiltering. Default:{choices.DEFAULT_NUM_DOCUMENTS}.")
    n_candidate_tags = serializers.IntegerField(default=choices.DEFAULT_NUM_CANDIDATES,
                                                help_text=f"Number of tag candidates retrieved from unsupervised prefiltering. Default:{choices.DEFAULT_NUM_CANDIDATES}.")
    max_tags = serializers.IntegerField(default=choices.DEFAULT_MAX_TAGS, help_text=f"Maximum number of tags per one document. Default:{choices.DEFAULT_MAX_TAGS}.")


class StopWordSerializer(serializers.Serializer):
    stop_words = serializers.ListField(child=serializers.CharField(required=False), required=True, help_text=f"List of stop words to add.")
    overwrite_existing = serializers.BooleanField(required=False, default=choices.DEFAULT_OVERWRITE_EXISTING_STOPWORDS,
                                                  help_text=f"If enabled, overwrites all existing stop words, otherwise appends to the existing ones. Default: {choices.DEFAULT_OVERWRITE_EXISTING_STOPWORDS}.")
    ignore_numbers = serializers.BooleanField(required=False, default=choices.DEFAULT_IGNORE_NUMBERS, help_text='If enabled, ignore all numbers as possible features.')


class TagRandomDocSerializer(IndicesSerializerMixin):
    pass


class TaggerTagTextSerializer(serializers.Serializer):
    text = serializers.CharField()
    lemmatize = serializers.BooleanField(default=False, help_text='Use MLP lemmatizer if available. Use only if training data was lemmatized. Default: False')
    feedback_enabled = serializers.BooleanField(default=False,
                                                help_text='Stores tagged response in Elasticsearch and returns additional url for giving feedback to Tagger. Default: False')


class TaggerTagDocumentSerializer(serializers.Serializer):
    doc = serializers.JSONField()
    lemmatize = serializers.BooleanField(default=False, help_text=f'Use MLP lemmatizer if available. Use only if training data was lemmatized. Default: False')
    feedback_enabled = serializers.BooleanField(default=False,
                                                help_text='Stores tagged response in Elasticsearch and returns additional url for giving feedback to Tagger. Default: False')


class TaggerMultiTagSerializer(serializers.Serializer):
    text = serializers.CharField(help_text='Text to be tagged.')
    hide_false = serializers.BooleanField(default=False, help_text='Hide negative tagging results in response.')
    lemmatize = serializers.BooleanField(default=False, help_text='Use MLP lemmatizer if available. Use only if training data was lemmatized. Default: False')
    feedback_enabled = serializers.BooleanField(default=False,
                                                help_text='Stores tagged response in Elasticsearch and returns additional url for giving feedback to Tagger. Default: False')
    taggers = serializers.ListField(
        help_text='List of Tagger IDs to be used.',
        child=serializers.IntegerField(),
        default=[]
    )


class TaggerListFeaturesSerializer(serializers.Serializer):
    size = serializers.IntegerField(default=100, help_text='Number of features to display. Default: 100')


class TaggerGroupTagTextSerializer(serializers.Serializer):
    text = serializers.CharField(help_text=f'Raw text input.')
    lemmatize = serializers.BooleanField(default=False, help_text=f'Use MLP lemmatizer to lemmatize input text. Use only if training data was lemmatized. Default: False')
    use_ner = serializers.BooleanField(default=False, help_text=f'Use MLP Named Entity Recognition to detect tag candidates. Default: False')
    n_similar_docs = serializers.IntegerField(default=choices.DEFAULT_NUM_DOCUMENTS,
                                              help_text=f'Number of documents used in unsupervised prefiltering. Default: {choices.DEFAULT_NUM_DOCUMENTS}')
    n_candidate_tags = serializers.IntegerField(default=choices.DEFAULT_NUM_CANDIDATES,
                                                help_text=f'Number of tag candidates retrieved from unsupervised prefiltering. Default: {choices.DEFAULT_NUM_CANDIDATES}')
    feedback_enabled = serializers.BooleanField(default=False,
                                                help_text='Stores tagged response in Elasticsearch and returns additional url for giving feedback to Tagger. Default: False')


class TaggerGroupTagDocumentSerializer(serializers.Serializer):
    doc = serializers.JSONField(help_text=f'Document in JSON format.')
    lemmatize = serializers.BooleanField(default=False, help_text=f'Use MLP lemmatizer if available. Use only if training data was lemmatized. Default: False')
    use_ner = serializers.BooleanField(default=False, help_text=f'Use MLP Named Entity Recognition to detect tag candidates. Default: False')
    n_similar_docs = serializers.IntegerField(default=choices.DEFAULT_NUM_DOCUMENTS,
                                              help_text=f'Number of documents used in unsupervised prefiltering. Default: {choices.DEFAULT_NUM_DOCUMENTS}')
    n_candidate_tags = serializers.IntegerField(default=choices.DEFAULT_NUM_CANDIDATES,
                                                help_text=f'Number of tag candidates retrieved from unsupervised prefiltering. Default: {choices.DEFAULT_NUM_CANDIDATES}')
    feedback_enabled = serializers.BooleanField(default=False,
                                                help_text='Stores tagged response in Elasticsearch and returns additional url for giving feedback to Tagger. Default: False')


class TaggerSerializer(FieldParseSerializer, serializers.ModelSerializer, IndicesSerializerMixin, ProjectResourceUrlSerializer, FavoriteModelSerializerMixin,
                       CommonModelSerializerMixin):
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.')
    vectorizer = serializers.ChoiceField(choices=choices.get_vectorizer_choices(), default=choices.DEFAULT_VECTORIZER,
                                         help_text='Vectorizer algorithm to create document vectors. NB! HashingVectorizer does not support feature name extraction!')
    analyzer = serializers.ChoiceField(choices=choices.get_analyzer_choices(), default=choices.DEFAULT_ANALYZER, help_text="Analyze text as words or characters.")
    classifier = serializers.ChoiceField(choices=choices.get_classifier_choices(), default=choices.DEFAULT_CLASSIFIER, help_text='Classification algorithm used in the model.')
    embedding = ProjectFilteredPrimaryKeyRelatedField(queryset=Embedding.objects, many=False, read_only=False, allow_null=True, default=None, help_text='Embedding to use')
    negative_multiplier = serializers.FloatField(default=choices.DEFAULT_NEGATIVE_MULTIPLIER,
                                                 help_text=f'Multiplies the size of positive samples to determine negative example set size. Default: {choices.DEFAULT_NEGATIVE_MULTIPLIER}')
    maximum_sample_size = serializers.IntegerField(default=choices.DEFAULT_MAX_SAMPLE_SIZE,
                                                   help_text=f'Maximum number of documents used to build a model. Default: {choices.DEFAULT_MAX_SAMPLE_SIZE}')
    minimum_sample_size = serializers.IntegerField(default=choices.DEFAULT_MIN_SAMPLE_SIZE,
                                                   help_text=f'Minimum number of documents required to train a model. Default: {choices.DEFAULT_MIN_SAMPLE_SIZE}')
    score_threshold = serializers.FloatField(default=choices.DEFAULT_SCORE_THRESHOLD,
                                             help_text=f'Elasticsearch score threshold for filtering out irrelevant examples. All examples below first document\'s score * score threshold are ignored. Float between 0 and 1. Default: {choices.DEFAULT_SCORE_THRESHOLD}')
    snowball_language = serializers.ChoiceField(choices=get_snowball_choices(), default=DEFAULT_SNOWBALL_LANGUAGE,
                                                help_text=f'Uses Snowball stemmer with specified language to normalize the texts. Default: {DEFAULT_SNOWBALL_LANGUAGE}')
    scoring_function = serializers.ChoiceField(choices=choices.DEFAULT_SCORING_OPTIONS, default=choices.DEFAULT_SCORING_FUNCTION, required=False,
                                               help_text=f'Scoring function used while evaluating the results on dev set. Default: {choices.DEFAULT_SCORING_FUNCTION}')
    stop_words = serializers.ListField(child=serializers.CharField(), default=[], required=False, help_text='Stop words to add. Default = [].', write_only=True)
    ignore_numbers = serializers.BooleanField(default=choices.DEFAULT_IGNORE_NUMBERS, required=False, help_text='If enabled, ignore all numbers as possible features.')
    detect_lang = serializers.BooleanField(default=False, help_text="Whether to detect the language for the stemmer from the document itself.")
    plot = serializers.SerializerMethodField()
    query = serializers.JSONField(help_text='Query in JSON format', required=False, default=json.dumps(EMPTY_QUERY))
    fact_name = serializers.CharField(default=None, required=False, help_text=f'Fact name used to filter tags (fact values). Default: None')
    pos_label = serializers.CharField(default="", required=False, allow_blank=True,
                                      help_text=f'Fact value used as positive label while evaluating the results. This is needed only, if the selected fact has exactly two possible values. Default = ""')
    url = serializers.SerializerMethodField()
    tagger_groups = serializers.SerializerMethodField(read_only=True)

    balance = serializers.BooleanField(default=choices.DEFAULT_BALANCE, required=False,
                                       help_text=f'Balance sample sizes of different classes. Only applicable for multiclass taggers. Default = {choices.DEFAULT_BALANCE}')
    balance_to_max_limit = serializers.BooleanField(default=choices.DEFAULT_BALANCE_TO_MAX_LIMIT, required=False,
                                                    help_text=f'If enabled, the number of samples for each class is set to `maximum_sample_size`. Otherwise, it is set to max class size. NB! Only applicable for multiclass taggers with balance == True. Default = {choices.DEFAULT_BALANCE_TO_MAX_LIMIT}')

    class Meta:
        model = Tagger
        fields = (
            'id', 'url', 'author', 'description', 'query', 'fact_name', 'indices', 'fields', 'detect_lang', 'embedding',
            'vectorizer', 'analyzer', 'classifier', 'stop_words',
            'maximum_sample_size', 'minimum_sample_size', 'is_favorited', 'score_threshold',
            'negative_multiplier', 'precision', 'recall', 'f1_score', 'snowball_language', 'scoring_function',
            'num_features', 'num_examples', 'confusion_matrix', 'is_favorited', 'plot', 'tasks', 'tagger_groups',
            'ignore_numbers', 'balance', 'balance_to_max_limit', 'pos_label', 'classes')
        read_only_fields = (
            'precision', 'recall', 'f1_score', 'num_features', 'num_examples', 'tagger_groups', 'confusion_matrix',
            'classes')
        fields_to_parse = ('fields', 'classes',)

    def validate(self, data):
        if data.get("detect_lang", None) is True and data.get("snowball_language", None):
            raise ValidationError("Values 'detect_lang' and 'snowball_language' are mutually exclusive, please opt for one!")

        # use custom validation for pos label as some other serializer fields are also required
        data = validate_pos_label(data)

        return data

    def __init__(self, *args, **kwargs):
        """
        Add the ability to pass extra arguments such as "remove_fields".
        Useful for the Serializer eg in another Serializer, without making a new one.
        """
        remove_fields = kwargs.pop('remove_fields', None)
        super(TaggerSerializer, self).__init__(*args, **kwargs)

        if remove_fields:
            # for multiple fields in a list
            for field_name in remove_fields:
                self.fields.pop(field_name)

    def get_tagger_groups(self, value: Tagger):
        return json.loads(value.tagger_groups)


class TaggerGroupSerializer(serializers.ModelSerializer, ProjectResourceUrlSerializer, FavoriteModelSerializerMixin, CommonModelSerializerMixin):
    minimum_sample_size = serializers.IntegerField(default=choices.DEFAULT_MIN_SAMPLE_SIZE,
                                                   help_text=f'Minimum number of documents required to train a model. Default: {choices.DEFAULT_MIN_SAMPLE_SIZE}')
    fact_name = serializers.CharField(default=choices.DEFAULT_TAGGER_GROUP_FACT_NAME,
                                      help_text=f'Fact name used to filter tags (fact values). Default: {choices.DEFAULT_TAGGER_GROUP_FACT_NAME}')
    tagger = TaggerSerializer(write_only=True, remove_fields=['description', 'query', 'fact_name', 'minimum_sample_size'])
    num_tags = serializers.IntegerField(read_only=True)
    blacklisted_facts = serializers.ListField(child=serializers.CharField(), default=[], help_text="Which fact values to ignore when creating the taggers.")
    tagger_status = serializers.SerializerMethodField()
    tagger_statistics = serializers.SerializerMethodField()
    tagger_params = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    def to_representation(self, instance):
        data = super(TaggerGroupSerializer, self).to_representation(instance)
        try:
            data["blacklisted_facts"] = json.loads(instance.blacklisted_facts)
        except Exception as e:
            logging.getLogger(settings.ERROR_LOGGER).exception(e)
        return data

    class Meta:
        model = TaggerGroup
        fields = ('id', 'url', 'author', 'description', 'fact_name', 'num_tags', 'blacklisted_facts', 'minimum_sample_size',
                  'tagger_status', 'tagger_params', 'tagger', 'tagger_statistics', 'is_favorited', 'tasks')

    # TODO This can be optimised into a single query.
    def get_tagger_status(self, obj: TaggerGroup):
        tagger_status = {
            'total': obj.num_tags,
            'completed': obj.taggers.filter(tasks__task_type=Task.TYPE_TRAIN, tasks__status=Task.STATUS_COMPLETED).distinct().count(),
            'training': obj.taggers.filter(tasks__task_type=Task.TYPE_TRAIN, tasks__status=Task.STATUS_RUNNING).distinct().count(),
            'created': obj.taggers.filter(tasks__task_type=Task.TYPE_TRAIN, tasks__status=Task.STATUS_CREATED).distinct().count(),
            'failed': obj.taggers.filter(tasks__task_type=Task.TYPE_TRAIN, tasks__status=Task.STATUS_FAILED).distinct().count(),
        }
        return tagger_status

    def get_tagger_statistics(self, obj):
        tagger_objects = obj.taggers
        if tagger_objects.exists():
            try:
                tagger_size_sum = round(tagger_objects.filter(model_size__isnull=False).aggregate(Sum('model_size'))['model_size__sum'], 1)
            except TypeError as e:
                # if models are not ready
                tagger_size_sum = 0
            tagger_stats = {
                'avg_precision': tagger_objects.aggregate(Avg('precision'))['precision__avg'],
                'avg_recall': tagger_objects.aggregate(Avg('recall'))['recall__avg'],
                'avg_f1_score': tagger_objects.aggregate(Avg('f1_score'))['f1_score__avg'],
                'sum_size': {"size": tagger_size_sum, "unit": "mb"}
            }
            return tagger_stats

    def _embedding_details(self, instance: Tagger):
        if instance.embedding:
            return {"id": instance.embedding.pk, "description": instance.embedding.description}
        else:
            return None

    def get_tagger_params(self, obj):
        if obj.taggers.exists():
            first_tagger: Tagger = obj.taggers.first()
            params = {
                'fields': json.loads(first_tagger.fields),
                'detect_lang': first_tagger.detect_lang,
                'scoring_function': first_tagger.scoring_function,
                'maximum_sample_size': first_tagger.maximum_sample_size,
                'negative_multiplier': first_tagger.negative_multiplier,
                'snowball_language': first_tagger.snowball_language,
                'embedding': self._embedding_details(first_tagger),
                'indices': first_tagger.get_indices(),
                'vectorizer': first_tagger.vectorizer,
                'classifier': first_tagger.classifier,
                'analyzer': first_tagger.analyzer,
                'stop_words': load_stop_words(first_tagger.stop_words),
                'ignore_numbers': first_tagger.ignore_numbers,
                'balance': first_tagger.balance,
                'balance_to_max_limit': first_tagger.balance_to_max_limit
            }
            return params
