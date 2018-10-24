
import json
import logging

from dataset_importer.document_preprocessor import preprocessor_map
from dataset_importer.document_preprocessor import PREPROCESSOR_INSTANCES
from dataset_importer.document_preprocessor import convert_to_utf8

from texta.settings import ERROR_LOGGER
from texta.settings import INFO_LOGGER
from searcher.models import Search
from task_manager.models import Task
from task_manager.tools import ShowProgress
from task_manager.tools import TaskCanceledException

from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from texta.settings import FACT_PROPERTIES

from .base_worker import BaseWorker


class PreprocessorWorker(BaseWorker):

    def __init__(self, scroll_size=1000, time_out='10m'):
        self.es_m = None
        self.task_id = None
        self.params = None
        self.scroll_size = scroll_size
        self.scroll_time_out = time_out

    def run(self, task_id):

        self.task_id = task_id
        task = Task.objects.get(pk=self.task_id)
        params = json.loads(task.parameters)
        task.update_status(Task.STATUS_RUNNING)

        try:
        
            ds = Datasets().activate_dataset_by_id(params['dataset'])
            es_m = ds.build_manager(ES_Manager)
            es_m.load_combined_query(self._parse_query(params))

            self.es_m = es_m
            self.params = params
            self._preprocessor_worker()
        
        except TaskCanceledException as e:
            # If here, task was canceled while processing
            # Delete task
            task = Task.objects.get(pk=self.task_id)
            task.delete()
            logging.getLogger(INFO_LOGGER).info(json.dumps({'process': 'PROCESSOR WORK', 'event': 'processor_worker_canceled', 'data': {'task_id': self.task_id}}), exc_info=True)
            print("--- Task canceled")
        
        except Exception as e:
            logging.getLogger(ERROR_LOGGER).exception(json.dumps(
                {'process': 'PROCESSOR WORK', 'event': 'processor_worker_failed', 'data': {'task_id': self.task_id}}), exc_info=True)
            # declare the job as failed.
            task = Task.objects.get(pk=self.task_id)
            task.result = json.dumps({'error': repr(e)})
            task.update_status(Task.STATUS_FAILED, set_time_completed=True)

    def _preprocessor_worker(self):

        field_paths = []
        show_progress = ShowProgress(self.task_id)
        show_progress.update(0)

        # TODO: remove "preprocessor_key" need from here? this should be worked out in the view (controller interface)
        # Add new field to mapping definition if necessary
        if 'field_properties' in preprocessor_map[self.params['preprocessor_key']]:
            preprocessor_key = self.params['preprocessor_key']
            fields = self.params['{0}_feature_names'.format(preprocessor_key)]
            for field in fields:
                field_paths.append(field)
                new_field_name = '{0}_{1}'.format(field, preprocessor_key)
                new_field_properties = preprocessor_map[preprocessor_key]['field_properties']
                self.es_m.update_mapping_structure(new_field_name, new_field_properties)

        response = self.es_m.scroll(field_scroll=field_paths, size=self.scroll_size, time_out=self.scroll_time_out)
        scroll_id = response['_scroll_id']
        total_docs = response['hits']['total']

        total_hits = len(response['hits']['hits'])
        show_progress.set_total(total_docs)
        total_positive = 0

        while total_hits > 0:

            documents, parameter_dict, ids = self._prepare_preprocessor_data(response)
            # Add facts field if necessary
            if documents:
                if 'texta_facts' not in documents[0]:
                    self.es_m.update_mapping_structure('texta_facts', FACT_PROPERTIES)

            documents = list(map(convert_to_utf8, documents))

            # Apply all preprocessors
            for preprocessor_code in parameter_dict['preprocessors']:
                preprocessor = PREPROCESSOR_INSTANCES[preprocessor_code]
                result_map = preprocessor.transform(documents, **parameter_dict)
                documents = result_map['documents']
                total_positive += result_map['meta'].get('total_positives', 0)

            self.es_m.update_documents(documents, ids)
            # Update progress is important to check task is alive
            show_progress.update(total_hits)
            # Get next page if any
            response = self.es_m.scroll(scroll_id=scroll_id, time_out=self.scroll_time_out)
            total_hits = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']

        task = Task.objects.get(pk=self.task_id)
        task.result = json.dumps({'documents_processed': show_progress.n_total, 'positive_tags': total_positive, 'preprocessor_key': self.params['preprocessor_key']})
        show_progress.update(100)
        task.update_status(Task.STATUS_COMPLETED, set_time_completed=True)

    def _prepare_preprocessor_data(self, response: dict):
        """
        Seperates document dicts and id strings from the pure ES response and changes
        the suffixes of the necessary parameters for routing purposes.

        :param response:
        :return:
        """

        documents = [hit['_source'] for hit in response['hits']['hits']]
        ids = [hit['_id'] for hit in response['hits']['hits']]
        parameter_dict = {'preprocessors': [self.params['preprocessor_key']]}

        for key, value in self.params.items():
            if key.startswith(self.params['preprocessor_key']):
                new_key_suffix = key[len(self.params['preprocessor_key']) + 1:]
                new_key = '{0}_preprocessor_{1}'.format(self.params['preprocessor_key'], new_key_suffix)
                # TODO: check why this json.dumps is necessary? probably isn't
                parameter_dict[new_key] = json.dumps(value)

        return documents, parameter_dict, ids

    @staticmethod
    def _parse_query(parameters):
        """
        Returns the query to be sent into elasticsearch depending on the Search
        being used. In case no search is selected, it returns a ready-made query
        to get all documents.

        :param parameters: Task parameters send from the form.
        :return: Query to be sent towards the ES instance.
        """
        search = parameters['search']
        # select search
        if search == 'all_docs':
            query = {"main": {"query": {"bool": {"minimum_should_match": 0, "must": [], "must_not": [], "should": []}}}}
        else:
            query = json.loads(Search.objects.get(pk=int(search)).query)
        return query
