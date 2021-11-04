from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from texta_elastic.searcher import EMPTY_QUERY
from toolkit.serializer_constants import IndicesSerializerMixin


class ElasticMoreLikeThisSerializer(IndicesSerializerMixin):
    fields = serializers.ListField(required=True, help_text="List of strings of the fields you wish to use for analysis.")
    like = serializers.ListField(child=serializers.DictField(), required=True, help_text="List of document metas (_id, _index, _type) which is used as a baseline for fetching similar documents")
    min_term_freq = serializers.IntegerField(default=1, help_text="The minimum term frequency below which the terms will be ignored from the input document. Default: 1")
    max_query_terms = serializers.IntegerField(default=12, help_text="The maximum number of query terms that will be selected. Increasing this value gives greater accuracy at the expense of query execution speed. Default: 12")
    min_doc_freq = serializers.IntegerField(default=5, help_text="The minimum document frequency below which the terms will be ignored from the input document. Default: 5")
    min_word_length = serializers.IntegerField(default=0, help_text="The minimum word length below which the terms will be ignored. Default: 0")
    max_word_length = serializers.IntegerField(default=0, help_text="The maximum word length above which the terms will be ignored. Default: 0")
    stop_words = serializers.ListField(default=[], help_text="An array of stop words. Any word in this set is considered 'uninteresting' and ignored.")
    include_meta = serializers.BooleanField(default=False, help_text="Whether to add the documents meta information (id, index, doctype) into the returning set of documents.")
    size = serializers.IntegerField(min_value=1, max_value=10000, default=10, help_text="How many documents to return with the end result. Default: 10")


class ElasticFactSerializer(serializers.Serializer):
    fact = serializers.CharField()
    str_val = serializers.CharField()
    num_val = serializers.IntegerField(required=False)
    spans = serializers.CharField(default="[[0,0]]")
    doc_path = serializers.CharField()
    sent_index = serializers.IntegerField(required=False)


class ElasticDocumentSerializer(serializers.Serializer):
    doc_id = serializers.CharField(required=True)
    fact = serializers.JSONField(required=False)
    fields_to_update = serializers.JSONField(required=False)


class ElasticScrollSerializer(serializers.Serializer):
    indices = serializers.ListField(child=serializers.CharField(), default=[], help_text="From which indices to search, by default all project indices are chosen.")
    scroll_id = serializers.CharField(required=False)
    query = serializers.DictField(default=EMPTY_QUERY, help_text="Query to limit returned documents.")
    documents_size = serializers.IntegerField(min_value=1, max_value=1500, default=300, help_text="How many documents should be returned in the response. Max is 1500.")
    fields = serializers.ListField(default=["*"], help_text="List of field names you wish to be return by Elasticsearch.")
    with_meta = serializers.BooleanField(default=False, help_text="Whether to return raw Elasticsearch hits or remove the metadata from the documents.")


    # Change what is returned to serializer_instance.validated_data
    def to_internal_value(self, data):
        values = super(ElasticScrollSerializer, self).to_internal_value(data)
        if "query" in values:
            query_field = values.get("query", None)
            if query_field:
                values["query"] = {"query": query_field["query"]}  # Make sure we only keep the query, without aggregations.
            else:
                raise ValidationError("Query must have an 'query' key to conduct a search.")
        return values
