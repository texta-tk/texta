
from task_manager.models import Task


class ShowProgress(object):
	""" Show model training progress
	"""

	def __init__(self, task_pk, multiplier=None):
		self.n_total = None
		self.n_count = 0
		self.task_pk = task_pk
		self.multiplier = multiplier

	def set_total(self, total):
		self.n_total = total
		if self.multiplier:
			self.n_total = self.multiplier * total

	def update(self, amount):
		if amount == 0:
			return
		self.n_count += amount
		percentage = (100.0 * self.n_count) / self.n_total
		self.update_view(percentage)

	def update_view(self, percentage):
        r = Task.get_by_id(self.task_pk)
		# r.status = 'Running [{0:3.0f} %]'.format(percentage)
        r.status = Task.STATUS_RUNNING
        r.progress = percentage
		r.save()


class EsIteratorError(Exception):
	""" EsIterator Exception
	"""
	pass


class EsIterator(object):
	"""  ElasticSearch Iterator
	"""

	def __init__(self, parameters, callback_progress=None):
		ds = Datasets().activate_dataset_by_id(parameters['dataset'])
		query = self._parse_query(parameters)

		self.field = json.loads(parameters['field'])['path']
		self.es_m = ds.build_manager(ES_Manager)
		self.es_m.load_combined_query(query)
		self.callback_progress = callback_progress

		if self.callback_progress:
			total_elements = self.get_total_documents()
			callback_progress.set_total(total_elements)

	@staticmethod
	def _parse_query(parameters):
		search = parameters['search']
		# select search
		if search == 'all_docs':
			query = {"main": {"query": {"bool": {"minimum_should_match": 0, "must": [], "must_not": [], "should": []}}}}
		else:
			query = json.loads(Search.objects.get(pk=int(search)).query)
		return query

	def __iter__(self):
		self.es_m.set_query_parameter('size', 500)
		response = self.es_m.scroll()

		scroll_id = response['_scroll_id']
		l = response['hits']['total']

		while l > 0:
			response = self.es_m.scroll(scroll_id=scroll_id)
			l = len(response['hits']['hits'])
			scroll_id = response['_scroll_id']

			# Check errors in the database request
			if (response['_shards']['total'] > 0 and response['_shards']['successful'] == 0) or response['timed_out']:
				msg = 'Elasticsearch failed to retrieve documents: ' \
					  '*** Shards: {0} *** Timeout: {1} *** Took: {2}'.format(response['_shards'], response['timed_out'], response['took'])
				raise EsIteratorError(msg)

			for hit in response['hits']['hits']:
				try:
					# Take into account nested fields encoded as: 'field.sub_field'
					decoded_text = hit['_source']
					for k in self.field.split('.'):
						decoded_text = decoded_text[k]
					sentences = decoded_text.split('\n')
					for sentence in sentences:
						yield [word.strip().lower() for word in sentence.split(' ')]

				except KeyError:
					# If the field is missing from the document
					logging.getLogger(ERROR_LOGGER).error('Key does not exist.', exc_info=True, extra={'hit': hit, 'scroll_response': response})

			if self.callback_progress:
				self.callback_progress.update(l)

	def get_total_documents(self):
		return self.es_m.get_total_documents()
