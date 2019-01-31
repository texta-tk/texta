from ..base_worker import BaseWorker
from utils.fact_manager import FactManager


class FactDeletionWorker(BaseWorker):

    def run(self, task_id):
        fact_m = FactManager(request.POST)
        raise NotImplementedError("Worker should implement run method")
