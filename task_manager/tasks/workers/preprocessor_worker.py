import json
import logging
from datetime import datetime

from searcher.models import Search
from task_manager.document_preprocessor import PREPROCESSOR_INSTANCES, preprocessor_map
from task_manager.models import Task
from task_manager.tools import ShowProgress, TaskCanceledException
from texta.settings import ERROR_LOGGER, FACT_FIELD, FACT_PROPERTIES, INFO_LOGGER
from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from utils.helper_functions import add_dicts
from .base_worker import BaseWorker


class PreprocessorWorker(BaseWorker):

    def __init__(self, scroll_size=200, time_out='10m'):
        self.es_m = None
        self.task_id = None
        self.params = None
        self.scroll_size = scroll_size
        self.scroll_time_out = time_out

        self._reload_env()
        self.info_logger, self.error_logger = self._generate_loggers()

    def _reload_env(self):
        from dotenv import load_dotenv
        from pathlib import Path
        env_path = str(Path('.env'))
        load_dotenv(dotenv_path=env_path)

    def _generate_loggers(self):
        import graypy
        import os
        info_logger = logging.getLogger(INFO_LOGGER)
        error_logger = logging.getLogger(ERROR_LOGGER)
        handler = graypy.GELFUDPHandler(os.getenv("GRAYLOG_HOST_NAME", "localhost"), int(os.getenv("GRAYLOG_PORT", 12201)))

        info_logger.addHandler(handler)
        error_logger.addHandler(handler)

        return info_logger, error_logger

    def run(self, task_id):
        self.task_id = task_id
        task = Task.objects.get(pk=self.task_id)
        params = json.loads(task.parameters)
        task.update_status(Task.STATUS_RUNNING)

        try:
            ds = Datasets().activate_datasets_by_id(params['dataset'])
            es_m = ds.build_manager(ES_Manager)
            es_m.load_combined_query(self._parse_query(params))

            self.es_m = es_m
            self.params = params
            valid, msg = self._check_if_request_bad(self.params)
            if valid:
                self._preprocessor_worker()
            else:
                raise UserWarning(msg)

        except TaskCanceledException as e:
            # If here, task was canceled while processing
            # Delete task
            task = Task.objects.get(pk=self.task_id)
            task.delete()
            self.info_logger.info("Canceled preprocessor", extra={'task': 'PROCESSOR WORK', 'event': 'processor_worker_canceled', 'data': {'task_id': self.task_id}}, exc_info=True)
            print("--- Task canceled")

        except Exception as e:
            self.error_logger.exception("Preprocessor failed", extra={'task': 'PROCESSOR WORK', 'event': 'processor_worker_failed'}, exc_info=True)
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
        preprocessor_key = self.params['preprocessor_key']
        if 'field_properties' in preprocessor_map[preprocessor_key]:
            fields = self.params['{0}_feature_names'.format(preprocessor_key)]
            for field in fields:
                field_paths.append(field)
                new_field_name = '{0}_{1}'.format(field, preprocessor_key)
                new_field_properties = preprocessor_map[preprocessor_key]['field_properties']
                self.es_m.update_mapping_structure(new_field_name, new_field_properties)

        response = self.es_m.scroll(field_scroll=field_paths, size=self.scroll_size, time_out=self.scroll_time_out)
        scroll_id = response['_scroll_id']
        total_docs = response['hits']['total']
        # For partial update
        doc_ids = [x['_id'] for x in response['hits']['hits'] if '_id' in x]

        total_hits = len(response['hits']['hits'])
        show_progress.set_total(total_docs)
        try:
            # Metadata of preprocessor outputs
            meta = {}
            while total_hits > 0:
                documents, parameter_dict, ids, document_locations = self._prepare_preprocessor_data(response)
                # Add facts field if necessary
                if documents:
                    if FACT_FIELD not in documents[0]:
                        self.es_m.update_mapping_structure(FACT_FIELD, FACT_PROPERTIES)

                # Apply all preprocessors
                for preprocessor_code in parameter_dict['preprocessors']:
                    preprocessor = PREPROCESSOR_INSTANCES[preprocessor_code]
                    parameter_dict.update({'document_locations': document_locations})
                    result_map = preprocessor.transform(documents, **parameter_dict)
                    documents = result_map['documents']
                    add_dicts(meta, result_map['meta'])

                self.es_m.bulk_post_documents(documents, ids, document_locations)
                # Update progress is important to check task is alive
                show_progress.update(total_hits)
                self.es_m.update_documents_by_id(doc_ids)
                # Get next page if any
                response = self.es_m.scroll(scroll_id=scroll_id, time_out=self.scroll_time_out)
                total_hits = len(response['hits']['hits'])
                scroll_id = response['_scroll_id']
                # For partial update
                doc_ids = [x['_id'] for x in response['hits']['hits'] if '_id' in x]

            task = Task.objects.get(pk=self.task_id)
            show_progress.update(100)
            task.result = json.dumps({'documents_processed': show_progress.n_total, **meta, 'preprocessor_key': self.params['preprocessor_key']})
            task.update_status(Task.STATUS_UPDATING)
            # Update the last batch of documents
            self.es_m.update_documents_by_id(doc_ids)
            task.update_status(Task.STATUS_COMPLETED, set_time_completed=True)

        # If runs into an exception, give feedback
        except Exception as e:
            log_dict = {'task': '_preprocessor_worker', 'event': 'main_scroll_logic_failed', 'data': {'task_id': self.task_id}}
            self.error_logger.exception("Main scroll logic failed", extra=log_dict, exc_info=True)
            task = Task.objects.get(pk=self.task_id)
            task.status = Task.STATUS_FAILED
            task.result = json.dumps({'documents_processed': show_progress.n_count, 'preprocessor_key': self.params['preprocessor_key'], 'error': str(e)})
            task.time_completed = datetime.now()
            task.save()

    def _prepare_preprocessor_data(self, response: dict):
        """
        Separates document dicts and id strings from the pure ES response and changes
        the suffixes of the necessary parameters for routing purposes.

        :param response:
        :return:
        """
        documents = [hit['_source'] for hit in response['hits']['hits']]
        ids = [hit['_id'] for hit in response['hits']['hits']]
        document_locations = [{'_index': hit['_index'], '_type': hit['_type']} for hit in response['hits']['hits']]
        parameter_dict = {'preprocessors': [self.params['preprocessor_key']]}

        for key, value in self.params.items():
            if key.startswith(self.params['preprocessor_key']):
                new_key_suffix = key[len(self.params['preprocessor_key']) + 1:]
                new_key = '{0}_{1}'.format(self.params['preprocessor_key'], new_key_suffix)
                # TODO: check why this json.dumps is necessary? probably isn't
                parameter_dict[new_key] = json.dumps(value)

        return documents, parameter_dict, ids, document_locations

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

    @staticmethod
    def _check_if_request_bad(args):
        """Check if models/fields are selected"""
        if not any(['feature_names' in k for k in args]):
            return False, "No field selected"

        if args['preprocessor_key'] in ['text_tagger', 'entity_extractor']:
            if not any(['preprocessor_models' in k for k in args]):
                return False, "No preprocessor model selected"

        return True, ""
