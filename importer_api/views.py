from django.http import JsonResponse
from account.models import Profile
from django.views import View
from elasticsearch.helpers import streaming_bulk as elastic_parallelbulk
from texta.settings import es_url, INFO_LOGGER

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
		for ok, response in elastic_parallelbulk(client=self.es, actions=actions):
			if not ok:
				self.logger.error(response)

	def insert_index_into_es(self):
		response = self.es.indices.create(index=self.index, ignore=400)
		self.logger.info(response)

	def insert_mapping_into_doctype(self, mapping_body):
		response = self.es.indices.put_mapping(doc_type=self.doc_type, index=self.index, body=mapping_body)
		self.logger.info(response)

	def create_index_if_not_exist(self):
		index_exists = self.es.indices.exists(index=self.index)
		if not index_exists:
			self.insert_index_into_es()

			# Add default mapping for texta_facts.
			self.insert_mapping_into_doctype(ImporterApiView.default_mapping)


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
				'type':       'nested',
				'properties': {
					'doc_path': {'type': 'keyword'},
					'fact':     {'type': 'keyword'},
					'num_val':  {'type': 'long'},
					'spans':    {'type': 'keyword'},
					'str_val':  {'type': 'keyword'}
				}
			}
		}
	}

	def post(self, request, *args, **kwargs):
		logger = logging.getLogger(INFO_LOGGER)

		try:

			# In Python 3.5, json.loads() accepts only unicode, unlike in Python 3.6.
			utf8_post_payload = request.body.decode("utf-8")
			logger.info(str(utf8_post_payload))

			post_payload_dict = json.loads(utf8_post_payload)
			logger.info(post_payload_dict)

			logger.info("Validating mandatory field and value existences in ImportAPI")
			ApiInputValidator(post_payload_dict, ["auth_token", "index", "doc_type", "data"])

			logger.info("Authenticating user for ImportAPI.")
			AuthTokenHandler(post_payload_dict.get("auth_token"))

			logger.info("Creating ES client.")
			es_handler = ElasticsearchHandler(index=post_payload_dict["index"], doc_type=post_payload_dict["doc_type"])
			logger.info("Finished creating ES client.")

			es_handler.create_index_if_not_exist()

			api_payload = post_payload_dict["data"]
			type_of_insertion_data = type(api_payload)

			if "mapping" in post_payload_dict:
				es_handler.insert_mapping_into_doctype(post_payload_dict["mapping"])

			if type_of_insertion_data == dict:
				es_handler.insert_single_document(api_payload)
			elif type_of_insertion_data == list:
				es_handler.insert_multiple_documents(api_payload)

			return JsonResponse({"message": "Item(s) successfully saved."})

		except ValueError as e:
			logger.info(str(e))
			return JsonResponse({"message": str(e)})
