import json
import logging
from time import sleep

import requests

from texta.settings import ERROR_LOGGER


class Helpers:

    @staticmethod
    def chunks(iterator: list, chunk_size=6):
        """
        Divides all the items in a list into equal chunks.
        """
        for i in range(0, len(iterator), chunk_size):
            yield iterator[i:i + chunk_size]


    @staticmethod  # Set a given data in a dictionary with position provided as a list
    def set_in_dict(data_dict, map_list, value):
        for key in map_list[:-1]:
            data_dict = data_dict.setdefault(key, {})
        data_dict[map_list[-1]] = value


    @staticmethod
    def traverse_nested_dict_by_keys(data_dict, keys):
        for k in keys:
            data_dict = data_dict.get(k, "")
            if data_dict == "":
                return ""

        return data_dict


    @staticmethod
    def pars_data_string(data: dict):
        data = json.loads(data["texts"])
        return data


    @staticmethod
    def divide_tasks_into_chunks(data: dict, chunk_size=6):
        """
        Split all the documents inside the dictionary into equally sized objects
        to make the best use out of Celery's multiple workers. All of the gained
        chunks will be thrown into the Celery queue.
        """
        tasks_data = []
        list_of_texts = json.loads(data["texts"])
        chunks = Helpers.chunks(list_of_texts, chunk_size=chunk_size)

        for chunk in chunks:
            input_data = {"texts": json.dumps(chunk, ensure_ascii=False), "doc_path": data["doc_path"]}
            tasks_data.append(input_data)

        return tasks_data


class MLPTaskAdapter(object):
    CELERY_CHUNK_SIZE = 6


    def __init__(self, mlp_url, mlp_type='mlp'):
        self.mlp_url = mlp_url
        self.start_task_url = '{0}/task/start/{1}'.format(mlp_url.strip('/'), mlp_type)
        self.task_status_url = "{0}/task/status/{1}"

        # Progress management.
        self.total_document_count = 0
        self.parsed_document_count = 0

        # Intermediary task management.
        self.tasks = []
        self.finished_task_ids = []
        self.failed_task_ids = []

        # Final return values.
        self.analyzation_data = []
        self.errors = {}


    def _start_mlp_celery_task(self, mlp_input):
        """
        Uses the MLP endpoint to trigger a Celery task inside the MLP server.
        'url': 'http://localhost:5000/task/status/c2b1119e...', 'task': 'c2b1119e...'}
        """
        try:
            response = requests.post(self.start_task_url, data=mlp_input)
            task_info = response.json()

            task_info["position_index"] = len(self.tasks)
            self.tasks.append(task_info)

        except Exception as e:
            logging.getLogger(ERROR_LOGGER).exception("Response Status: {} and Response Content: {}".format(response.status_code, response.text))


    def _poll_task_status(self, task_id: str):
        """
        Get the state of the celery task using MLP's status endpoint.
        This will be good for reporting any retries, errors and successful tasks.
        """
        try:
            url = self.task_status_url.format(self.mlp_url.strip("/"), task_id)
            response = requests.get(url)
            result = response.json()
            return result
        except Exception as e:
            logging.getLogger(ERROR_LOGGER).exception("Response Status: {} and Response Content: {}".format(response.status_code, response.text))


    def _handle_error_status(self, task_status: dict):
        self.failed_task_ids.append(task_status["status"]["id"])


    def _handle_success_status(self, task_state: dict, task_index: int):
        result = task_state["status"]["result"]["result"]

        for index_int, list_of_text_dicts in enumerate(result):
            self.analyzation_data[task_index * MLPTaskAdapter.CELERY_CHUNK_SIZE + index_int] = list_of_text_dicts

        self.finished_task_ids.append(task_state["status"]["id"])


    def process(self, data):
        self.total_document_count = len(Helpers.pars_data_string(data))
        # Split all the documents into chunk, each chunk becomes a SEPARATE Celery task.
        celery_task_chunk = Helpers.divide_tasks_into_chunks(data, chunk_size=MLPTaskAdapter.CELERY_CHUNK_SIZE)
        self.analyzation_data = [None] * len(Helpers.pars_data_string(data))

        # For each previously split chunk, start a separate Celery task.
        for celery_input in celery_task_chunk:
            self._start_mlp_celery_task(celery_input)

        # As long as there are active tasks being processed, poll their status.
        # If one fails or succeeds, they are removed.
        while self.tasks:

            # Get all the states at once to avoid unnecessary delays.
            task_states = [{"status": self._poll_task_status(task["task"]), "position_index": task["position_index"]} for task in self.tasks]

            # Rout all the Celery task results to their respective handlers.
            for index, task_state in enumerate(task_states):
                task_status = task_state["status"]["status"]

                if task_status == "FAILURE":
                    self._handle_error_status(task_state)

                elif task_status == "SUCCESS":
                    self._handle_success_status(task_state, task_state["position_index"])

            # Remove all the tasks that have finished their jobs or failed turning it.
            self.tasks = [task for task in self.tasks if task["task"] not in self.finished_task_ids and task["task"] not in self.failed_task_ids]
            sleep(3)  # Wait a small amount of time until checking wheter the task has finished.

        return self.analyzation_data, self.errors
