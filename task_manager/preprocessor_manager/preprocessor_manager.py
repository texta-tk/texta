from task_manager.models import Task
from searcher.models import Search
from utils.datasets import Datasets
from utils.es_manager import ES_Manager

import json

class Preprocessor:

	def __init__(self):
		pass
	
	def apply(self, task_id):
		task = Task.objects.get(pk=task_id)
		params = json.loads(task.parameters)
		
		ds = Datasets().activate_dataset_by_id(params['dataset'])
		es_m = ds.build_manager(ES_Manager)
		es_m.load_combined_query(self._parse_query(params))
		
		print(params)

	def _preprocessor_worker(self):
		pass

	@staticmethod
	def _parse_query(parameters):
		search = parameters['search']
		# select search
		if search == 'all_docs':
			query = {"main":{"query":{"bool":{"minimum_should_match":0,"must":[],"must_not":[],"should":[]}}}}
		else:
			query = json.loads(Search.objects.get(pk=int(search)).query)
		return query
