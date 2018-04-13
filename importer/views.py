from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from account.models import Profile
from django.views import View
from elasticsearch.helpers import bulk as elastic_bulkapi
import json
import elasticsearch


class ElasticsearchHandler:

	def __init__(self, doc_type, index):
		self.es = elasticsearch.Elasticsearch()
		self.index = index
		self.doc_type = doc_type

	def insert_single_document(self, document):
		self.es.index(index=self.index, doc_type=self.doc_type, body=document)

	def insert_multiple_documents(self, list_of_documents):
		metadata = {"_index": self.index, "_type": self.doc_type}
		actions = [{"_source": document}.update(metadata) for document in list_of_documents]
		elastic_bulkapi(client=self.es, actions=actions)

	def insert_index_into_es(self):
		self.es.indices.create(index=self.index, ignore=400)

	def insert_mapping_into_doctype(self, mapping_body):
		self.es.indices.put_mapping(doc_type=self.doc_type, index=self.index, body=mapping_body)

	def check_for_index_existance(self):
		return self.es.indices.exists(index=self.index)

	def create_index_if_not_exist(self):
		index_exists = self.check_for_index_existance()
		if not index_exists:
			self.insert_index_into_es()


class ApiInputValidator:
	def __init__(self, post_dict, expected_field_list):
		self.post_dict = post_dict
		self.expected_field_list = expected_field_list

		self.validate_field_existence()
		self.validate_value_existence()

	def validate_field_existence(self):
		for mandatory_field in self.expected_field_list:
			if mandatory_field not in self.post_dict:
				raise Exception("Mandatory field '{0}' is missing.".format(mandatory_field))

	def validate_value_existence(self):
		for mandatory_field in self.expected_field_list:
			if not self.post_dict[mandatory_field]:
				raise Exception("Mandatory field '{0}' can not be empty".format(mandatory_field))


class AuthTokenHandler:

	def __init__(self, auth_token_str):
		self.auth_token_str = auth_token_str
		self.authenticate_token()

	def authenticate_token(self):
		authenticated_token = Profile.objects.first(auth_token=self.auth_token_str)
		if not authenticated_token:
			raise Exception("Authentication failed - invalid auth token.")


# Create your views here.
class ImporterApiView(View):

	def post(self, *args, **kwargs):
		try:
			post_payload = json.loads(self.request.body)
			post_handler = ApiInputValidator(post_payload, ["auth_token", "index", "doc_type", "data"])
			auth_handler = AuthTokenHandler(post_payload.get("auth_token"))
			es_handler = ElasticsearchHandler(index=post_payload["index"], doc_type=post_payload["doc_type"])

			payload = post_payload["data"]
			es_handler.create_index_if_not_exist()
			insert_data_type = str(type(payload))

			if "mapping" in post_payload:
				es_handler.insert_mapping_into_doctype(post_payload["mapping"])

			if insert_data_type == "dict":
				es_handler.insert_single_document(payload)
			elif insert_data_type == "list":
				es_handler.insert_multiple_documents(payload)

		except Exception as e:
			return JsonResponse({"message": e.message})
