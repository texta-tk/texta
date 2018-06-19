from dataset_importer.document_preprocessor.preprocessor import DocumentPreprocessor, preprocessor_map

from task_manager.models import Task
from searcher.models import Search
from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from task_manager.progress_manager import ShowProgress

import platform
if platform.system() == 'Windows':
    from threading import Thread as Process
else:
    from multiprocessing import Process

from datetime import datetime
import json

class Preprocessor:

	def __init__(self, scroll_size=1000):
		self.es_m = None
		self.scroll_size = scroll_size
	
	def apply(self, task_id):
		self.task_id = task_id
		task = Task.objects.get(pk=self.task_id)
		params = json.loads(task.parameters)
		
		ds = Datasets().activate_dataset_by_id(params['dataset'])
		es_m = ds.build_manager(ES_Manager)
		es_m.load_combined_query(self._parse_query(params))
		
		self.es_m = es_m
		self.params = params
		
		Process(target=self._preprocessor_worker()).start()
		return True

	def _preprocessor_worker(self):
		field_paths = []

		show_progress = ShowProgress(self.task_id)
		show_progress.update(0)

		# Add new field to mapping definition if necessary
		if 'field_properties' in preprocessor_map[self.params['preprocessor_key']]:
			preprocessor_key = self.params['preprocessor_key']
			fields = self.params['{0}_feature_names'.format(preprocessor_key)]
			for field in fields:
				field = json.loads(field)['path']
				field_paths.append(field)
				new_field_name = '{0}_{1}'.format(field, preprocessor_key)
				new_field_properties = preprocessor_map[preprocessor_key]['field_properties']
				self.es_m.update_mapping_structure(new_field_name, new_field_properties)
	
		
		response = self.es_m.scroll(field_scroll=field_paths, size=self.scroll_size)
		scroll_id = response['_scroll_id']
		l = response['hits']['total']	
		show_progress.set_total(l)

		while l > 0:
			response = self.es_m.scroll(scroll_id=scroll_id)
			l = len(response['hits']['hits'])
			scroll_id = response['_scroll_id']

			documents, parameter_dict, ids = self._prepare_preprocessor_data(field_paths, response)
			show_progress.update(l)
			
			processed_documents = list(DocumentPreprocessor.process(documents=documents, **parameter_dict))
			self.es_m.update_documents(processed_documents,ids)

		task = Task.objects.get(pk=self.task_id)
		task.status = 'completed'
		task.time_completed = datetime.now()
		task.result = json.dumps({'documents_processed': show_progress.n_total, 'preprocessor_key': self.params['preprocessor_key']})
		task.save()


	def _prepare_preprocessor_data(self, field_paths, response):
		documents = [hit['_source'] for hit in response['hits']['hits']]
		ids = [hit['_id'] for hit in response['hits']['hits']]
		parameter_dict = {'preprocessors': [self.params['preprocessor_key']]}
		
		for k,v in self.params.items():
			if k.startswith(self.params['preprocessor_key']):
				new_key_suffix = k[len(self.params['preprocessor_key'])+1:]
				new_key = '{0}_preprocessor_{1}'.format(self.params['preprocessor_key'], new_key_suffix)
				if new_key_suffix == 'feature_names':
					v = [json.loads(a)['path'] for a in v]
				parameter_dict[new_key] = json.dumps(v)
		
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

