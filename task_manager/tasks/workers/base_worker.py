import os

class BaseWorker:

    def run(self, task_id):
        raise NotImplementedError("Worker should implement run method")
