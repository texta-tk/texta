from time import sleep
import requests
import json


class Helpers:

    @staticmethod
    def chunks(iterator: list, chunk_size=6):
        """
        Divides all the items in a list into equal chunks.
        """
        for i in range(0, len(iterator), chunk_size):
            yield iterator[i:i + chunk_size]


    @staticmethod
    def pars_data_string(data: dict):
        data = json.loads(data["texts"])
        return data


    @staticmethod
    def divide_tasks_into_chunks(data: dict):
        """
        Split all the documents inside the dictionary into equally sized objects
        to make the best use out of Celery's multiple workers. All of the gained
        chunks will be thrown into the Celery queue.
        """
        tasks_data = []
        list_of_texts = json.loads(data["texts"])
        chunks = Helpers.chunks(list_of_texts)

        for chunk in chunks:
            input_data = {"texts": json.dumps(chunk)}
            tasks_data.append(input_data)

        return tasks_data


class MLPTaskAdapter(object):

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
        """
        response = requests.post(self.start_task_url, data=mlp_input)
        task_info = response.json()

        # {'url': 'http://localhost:5000/task/status/c2b1119e...', 'task': 'c2b1119e...'}
        self.tasks.append(task_info)


    def _poll_task_status(self, task_id: str):
        """
        Get the state of the celery task using MLP's status endpoint.
        This will be good for reporting any retries, errors and successful tasks.
        """
        url = self.task_status_url.format(self.mlp_url.strip("/"), task_id)
        response = requests.get(url)

        print(url, response, response.text)
        return response.json()


    def _handle_error_status(self, task_status: dict):
        self.failed_task_ids.append(task_status["id"])


    def _handle_success_status(self, task_state: dict):
        result = task_state["result"]

        self.parsed_document_count += len(result)
        self.analyzation_data.extend(result)
        self.finished_task_ids.append(task_state["id"])


    def process(self, data):
        self.total_document_count = len(Helpers.pars_data_string(data))

        # Split all the documents into chunk, each chunk becomes a SEPARATE Celery task.
        celery_task_chunk = Helpers.divide_tasks_into_chunks(data)

        # For each previously split chunk, start a separate Celery task.
        for celery_input in celery_task_chunk:
            self._start_mlp_celery_task(celery_input)

        # As long as there are active tasks being processed, poll their status.
        # If one fails or succeeds, they are removed.
        while self.tasks:

            # Get all the states at once to avoid unnecessary delays.
            task_states = [self._poll_task_status(task["task"]) for task in self.tasks]

            # Rout all the Celery task results to their respective handlers.
            for index, task_state in enumerate(task_states):

                task_status = task_state["status"]

                if task_status == "FAILURE":
                    self._handle_error_status(task_state)

                elif task_status == "SUCCESS":
                    self._handle_success_status(task_state)

            # Remove all the tasks that have finished their jobs or failed turning it.
            self.tasks = [task for task in self.tasks if task["task"] not in self.finished_task_ids and task["task"] not in self.failed_task_ids]
            sleep(3)  # Wait a small amount of time until checking wheter the task has finished.
            print(self.tasks)
        return self.analyzation_data, self.errors
