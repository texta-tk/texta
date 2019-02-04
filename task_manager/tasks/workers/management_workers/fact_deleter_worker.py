from ..base_worker import BaseWorker
from utils.fact_manager import FactManager


class FactDeleterWorker(BaseWorker):

    def __init__(self, scroll_size=10000, time_out='10m'):
        self.es_m = None
        self.task_id = None
        self.params = None
        self.scroll_size = scroll_size
        self.scroll_time_out = time_out

    def run(self, task_id):
        # fact_m = FactManager(request.POST)
        # import pdb;pdb.set_trace()
        
        raise NotImplementedError("Worker should implement run method")
