from time import sleep
import requests
import logging
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

        self.tasks = []
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
        Use the tasks is to get the overall state of the celery task using MLP's
        status endpoint. This will be good for reporting any retries, errors and successful
        tasks.
        """
        url = self.task_status_url.format(self.mlp_url, task_id)
        response = requests.get(url).json()
        return response


    def _handle_pending_status(self, task_index: int):
        print("Task is still pending")


    def _handle_error_status(self, task_index: int):
        print("Task has failed!")


    def process(self, data):

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
                if task_state["status"] == "PENDING":
                    self._handle_pending_status(index)

                elif task_state["status"] == "FAILURE":
                    self._handle_error_status(index)

                elif task_state["status"] == "SUCCESS":
                    self.analyzation_data.append(task_state["result"])
                    del self.tasks[index]

            sleep(3)  # Wait a small amount of time until checking wheter the task has finished.

        return self.analyzation_data, self.errors


if __name__ == '__main__':
    data_for_processing = [
        "Hello there", "general kenobi", "are you interested", "in some free real estate?",
        "Hello there", "general kenobi", "are you interested", "in some free real estate?",
        "Hello there", "general kenobi", "are you interested", "in some free real estate?",
        "Hello there", "general kenobi", "are you interested", "in some free real estate?"
    ]

    mlp = MLPTaskAdapter("http://localhost:12000")
    result_data, errors = mlp.process({"texts": json.dumps(data_for_processing)})
