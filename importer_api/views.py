from django.http import JsonResponse
from account.models import Profile
from django.views import View
from elasticsearch.helpers import streaming_bulk as elastic_parallelbulk
from texta.settings import es_url, INFO_LOGGER, ELASTICSEARCH_ANALYZERS

import json
import logging
import elasticsearch


class ElasticsearchHandler:

    def __init__(self, doc_type, index, hosts=[es_url], timeout=30):
        self.es = elasticsearch.Elasticsearch(hosts=hosts, timeout=timeout)
        self.es.cluster.health(wait_for_status='yellow', request_timeout=1000)
        self.index = index
        self.doc_type = doc_type

        self.logger = logging.getLogger(INFO_LOGGER)

    def insert_single_document(self, document):
        response = self.es.index(index=self.index, doc_type=self.doc_type, body=document)
        self.logger.info(response)

    def insert_multiple_documents(self, list_of_documents):
        actions = [{"_source": document, "_index": self.index, "_type": self.doc_type} for document in list_of_documents]

        for success, response in elastic_parallelbulk(client=self.es, actions=actions):
            self.logger.info("BulkAPI response: {0}".format(str(response)))
            if not success:
                self.logger.error(str(response))
                raise ValueError(str(response))

    def insert_index_into_es(self, analyzer):
        """
        Low-level helper function to create an index. Without the ignore=400 parameter, it will raise an Exception
        in case an index already exists with that name.
        """
        if not analyzer:
            response = self.es.indices.create(index=self.index, ignore=400)
            self.logger.info(response)

        elif analyzer:
            response = self.es.indices.create(index=self.index, ignore=400, body={
                "mappings": {
                    self.doc_type: {
                        "dynamic_templates": [
                            {"analyzer": {
                                "match_mapping_type": "string",
                                "mapping": {
                                    "analyzer": analyzer,
                                }
                            }
                            }
                        ]
                    }
                }
            })
            self.logger.info(response)

    def insert_mapping_into_doctype(self, mapping_body):
        response = self.es.indices.put_mapping(doc_type=self.doc_type, index=self.index, body=mapping_body)
        self.logger.info(response)

    def create_index_if_not_exist(self, analyzer=None):
        index_exists = self.es.indices.exists(index=self.index)
        if not index_exists:
            self.insert_index_into_es(analyzer)


class ApiInputValidator:
    def __init__(self, post_dict, expected_field_list):
        self.post_dict = post_dict
        self.mandatory_field_list = expected_field_list

        self.validate_field_existence()
        self.validate_value_existence()

    def validate_field_existence(self):
        for mandatory_field in self.mandatory_field_list:
            if mandatory_field not in self.post_dict:
                raise ValueError("Mandatory field '{0}' is missing.".format(mandatory_field))

    def validate_value_existence(self):
        for mandatory_field in self.mandatory_field_list:
            if not self.post_dict[mandatory_field]:
                raise ValueError("Mandatory field '{0}' can not be empty".format(mandatory_field))

    def check_if_analyzer_exists(self):
        user_sent_analyzer = self.post_dict["analyzer"]
        available_analyzer_names = list(map(lambda x: x["analyzer"], ELASTICSEARCH_ANALYZERS))
        if user_sent_analyzer not in available_analyzer_names:
            raise ValueError("Analyzer '{0}' not available. Available analyzers are: '{1}'".format(user_sent_analyzer, available_analyzer_names))


class AuthTokenHandler:

    def __init__(self, auth_token_str):
        self.auth_token_str = auth_token_str
        self.authenticate_token()

    def authenticate_token(self):
        authenticated_token = Profile.objects.filter(auth_token=self.auth_token_str).first()
        if not authenticated_token:
            raise ValueError("Authentication failed - invalid auth token.")


# Create your views here.
class ImporterApiView(View):
    default_mapping = {
        'properties': {
            'texta_facts': {
                'type': 'nested',
                'properties': {
                    'doc_path': {'type': 'keyword'},
                    'fact': {'type': 'keyword'},
                    'num_val': {'type': 'long'},
                    'spans': {'type': 'keyword'},
                    'str_val': {'type': 'keyword'}
                }
            }
        }
    }

    def post(self, request, *args, **kwargs):
        logger = logging.getLogger(INFO_LOGGER)

        try:
            # In Python 3.5, json.loads() accepts only unicode, unlike in Python 3.6.
            utf8_post_payload = request.body.decode("utf-8")
            es_data_payload = json.loads(utf8_post_payload)

            validator = ApiInputValidator(es_data_payload, ["auth_token", "index", "doc_type", "data"])
            analyzer = es_data_payload.get("analyzer", None)

            if analyzer: validator.check_if_analyzer_exists()

            AuthTokenHandler(es_data_payload.get("auth_token"))
            es_handler = ElasticsearchHandler(index=es_data_payload["index"], doc_type=es_data_payload["doc_type"])

            if analyzer:
                es_handler.create_index_if_not_exist(analyzer)
                es_handler.insert_mapping_into_doctype(ImporterApiView.default_mapping)

            else:
                es_handler.create_index_if_not_exist()
                es_handler.insert_mapping_into_doctype(ImporterApiView.default_mapping)

            api_payload = es_data_payload["data"]
            type_of_insertion_data = type(api_payload)

            if "mapping" in es_data_payload:
                es_handler.insert_mapping_into_doctype(es_data_payload["mapping"])

            if type_of_insertion_data == dict:
                es_handler.insert_single_document(api_payload)
            elif type_of_insertion_data == list:
                es_handler.insert_multiple_documents(api_payload)

            return JsonResponse({"message": "Item(s) successfully saved."})

        except ValueError as e:
            logger.info(str(e))
            return JsonResponse({"message": str(e)})


def get_analyzer_names(request):
    analyzer_names = list(map(lambda x: x["analyzer"], ELASTICSEARCH_ANALYZERS))
    return JsonResponse({"analyzers": analyzer_names})
