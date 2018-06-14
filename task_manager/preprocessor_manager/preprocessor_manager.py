from dataset_importer.document_preprocessor.preprocessor import DocumentPreprocessor, preprocessor_map

from task_manager.models import Task
from searcher.models import Search
from utils.datasets import Datasets
from utils.es_manager import ES_Manager

import json

class Preprocessor:

	def __init__(self, scroll_size=1000):
		self.es_m = None
		self.scroll_size = scroll_size
	
	def apply(self, task_id):
		task = Task.objects.get(pk=task_id)
		params = json.loads(task.parameters)
		
		ds = Datasets().activate_dataset_by_id(params['dataset'])
		es_m = ds.build_manager(ES_Manager)
		es_m.load_combined_query(self._parse_query(params))
		
		self.es_m = es_m
		self.params = params
		
		self._preprocessor_worker()

	def _preprocessor_worker(self):
		field_paths = []

		print(self.params)

		# Add new field to mapping definition if necessary
		key = self.params['preprocessor_key'].replace('_','-')
		key = '{0}-processor-feature-names'.format(key)
		for field in self.params[key]:
			field = json.loads(field)['path']
			field_paths.append(field)
			new_field_name = '{0}_{1}'.format(field, self.params['preprocessor_key'])
			print(new_field_name)
			if 'field_properties' in preprocessor_map[self.params['preprocessor_key']]:
				new_field_properties = preprocessor_map[self.params['preprocessor_key']]['field_properties']
				self.es_m.update_mapping_structure(new_field_name, new_field_properties)
	
		
		response = self.es_m.scroll(field_scroll=field_paths, size=self.scroll_size)
		scroll_id = response['_scroll_id']
		l = response['hits']['total']  

		print(self.params)

		while l > 0:
			response = self.es_m.scroll(scroll_id=scroll_id)
			l = len(response['hits']['hits'])
			scroll_id = response['_scroll_id']

			documents, parameter_dict, ids = self._prepare_preprocessor_data(field_paths, self.params['preprocessor_key'], response)
			
			print(parameter_dict)
			
			processed_documents = list(DocumentPreprocessor.process(documents=documents, **parameter_dict))
    
			#es_m.update_documents(processed_documents,ids)


	@staticmethod
	def _prepare_preprocessor_data(field_paths, preprocessor_key, response):
		documents = [hit['_source'] for hit in response['hits']['hits']]
		ids = [hit['_id'] for hit in response['hits']['hits']]
		preprocessor_input_features = '{0}_preprocessor_input_features'.format(preprocessor_key)
		parameter_dict = {'preprocessors': [preprocessor_key], preprocessor_input_features: json.dumps([field_paths])}
		return documents, parameter_dict, ids
	

	@staticmethod
	def _parse_query(parameters):
		search = parameters['search']
		# select search
		if search == 'all_docs':
			query = {"main":{"query":{"bool":{"minimum_should_match":0,"must":[],"must_not":[],"should":[]}}}}
		else:
			query = json.loads(Search.objects.get(pk=int(search)).query)
		return query
