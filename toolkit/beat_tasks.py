from toolkit.base_tasks import BaseTask
from toolkit.taskman import app


@app.task(bind=True, base=BaseTask, name="sync_indices_in_elasticsearch", ignore_results=True)
def sync_indices_in_elasticsearch(self):
    from texta_elastic.core import ElasticCore
    ec = ElasticCore()
    ec.syncher()
