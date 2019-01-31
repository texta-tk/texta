from datetime import datetime
import json
import logging
from datetime import datetime


from texta.settings import ERROR_LOGGER
from texta.settings import INFO_LOGGER
from searcher.models import Search
from task_manager.models import Task
from task_manager.tools import ShowProgress
from task_manager.tools import TaskCanceledException

from utils.datasets import Datasets
from utils.helper_functions import add_dicts
from utils.es_manager import ES_Manager
from texta.settings import FACT_PROPERTIES

from ..base_worker import BaseWorker


class ManagementWorker(BaseWorker):

    def __init__(self, scroll_size=10000, time_out='10m'):
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
            ds = Datasets().activate_datasets_by_id(params['dataset'])
            es_m = ds.build_manager(ES_Manager)
            # es_m.load_combined_query(self._parse_query(params))

            self.es_m = es_m
            self.params = params
            # valid, msg = self._check_if_request_bad(self.params)
            # if valid:
                # self._preprocessor_worker()
            # else:
                # raise UserWarning(msg)
            self._start_subworker()

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


    def _start_subworker(self):
        # Get sub-worker
        sub_worker = manager_map[self.params['manager_key']]
        sub_worker.run()



    @staticmethod
    def _check_if_request_bad(args):
        '''Check if models/fields are selected'''
        if not any(['feature_names' in k for k in args]):
            return False, "No field selected"

        if args['preprocessor_key'] in ['text_tagger', 'entity_extractor']:
            if not any(['preprocessor_models' in k for k in args]):
                return False, "No preprocessor model selected"

        return True, ""
