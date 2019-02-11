import json
import logging
from datetime import datetime

from texta.settings import ERROR_LOGGER
from texta.settings import INFO_LOGGER
from task_manager.models import Task
from task_manager.tools import TaskCanceledException
from task_manager.tasks.workers.management_workers.fact_deleter_sub_worker import FactDeleterSubWorker
from task_manager.tasks.workers.management_workers.fact_adder_sub_worker import FactAdderSubWorker

from utils.datasets import Datasets
from utils.es_manager import ES_Manager

from task_manager.tasks.workers.base_worker import BaseWorker
from task_manager.tasks.workers.management_workers.management_task_params import ManagerKeys


class ManagementWorker(BaseWorker):

    def __init__(self, scroll_size=10000, time_out='10m'):
        self.es_m = None
        self.task_id = None
        self.params = None
        self.scroll_size = scroll_size
        self.scroll_time_out = time_out
        self.task_obj = None
        # Map of sub-managers for ManagementWorker
        self.manager_map = {
            ManagerKeys.FACT_DELETER: FactDeleterSubWorker,
            ManagerKeys.FACT_ADDER: FactAdderSubWorker,
        }


    def run(self, task_id):
        self.task_id = task_id
        self.task_obj = Task.objects.get(pk=self.task_id)
        params = json.loads(self.task_obj.parameters)
        self.task_obj.update_status(Task.STATUS_RUNNING)

        try:
            ds = Datasets().activate_datasets_by_id(params['dataset'])
            es_m = ds.build_manager(ES_Manager)
            # es_m.load_combined_query(self._parse_query(params))
            self.es_m = es_m
            self.params = params

            result = self._start_subworker()
            self.task_obj.result = result
            self.task_obj.update_status(Task.STATUS_COMPLETED, set_time_completed=True)

        except TaskCanceledException as e:
            # If here, task was canceled while processing
            # Delete task
            self.task_obj.delete()
            logging.getLogger(INFO_LOGGER).info(json.dumps({'process': 'PROCESSOR WORK', 'event': 'management_worker_canceled', 'data': {'task_id': self.task_id}}))
            print("--- Task canceled")

        except Exception as e:
            logging.getLogger(ERROR_LOGGER).exception(json.dumps(
                {'process': 'PROCESSOR WORK', 'event': 'manager_worker_failed', 'data': {'task_id': self.task_id}}), exc_info=True)
            # declare the job as failed.
            self.task_obj.result = json.dumps({'error': repr(e)})
            self.task_obj.update_status(Task.STATUS_FAILED, set_time_completed=True)
        print('Done with management task')


    def _start_subworker(self):
        # Get sub-worker
        sub_worker = self.manager_map[self.params['manager_key']](self.es_m, self.task_id, self.params,self.scroll_size, self.scroll_time_out)
        # Run sub-worker
        result = sub_worker.run()
        return result
