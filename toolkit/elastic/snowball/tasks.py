import json
import logging
from typing import List

from celery.task import task

from toolkit.base_tasks import TransactionAwareTask
from toolkit.core.task.models import Task
from toolkit.elastic.snowball.helpers import process_stemmer_actions
from toolkit.elastic.snowball.models import ApplyStemmerWorker
from toolkit.elastic.tools.document import ElasticDocument
from toolkit.elastic.tools.searcher import ElasticSearcher
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, ERROR_LOGGER
from toolkit.tools.show_progress import ShowProgress


@task(name="apply_snowball_on_indices", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE, bind=True)
def apply_snowball_on_indices(self, worker_id: int):
    worker_object = ApplyStemmerWorker.objects.get(pk=worker_id)
    task_object = worker_object.task
    try:
        show_progress = ShowProgress(task_object, multiplier=1)
        show_progress.update_step('scrolling through the indices to apply lang')

        # Get the necessary fields.
        indices: List[str] = worker_object.get_indices()
        fields = json.loads(worker_object.fields)
        detect_lang = worker_object.detect_lang
        snowball_language = worker_object.stemmer_lang
        scroll_timeout = f"{worker_object.es_timeout}m"
        scroll_size = worker_object.bulk_size

        searcher = ElasticSearcher(
            query=json.loads(worker_object.query),
            indices=indices,
            field_data=fields,
            output=ElasticSearcher.OUT_RAW,
            callback_progress=show_progress,
            scroll_size=scroll_size,
            scroll_timeout=scroll_timeout
        )

        actions = process_stemmer_actions(
            generator=searcher,
            worker=worker_object,
            detect_lang=detect_lang,
            snowball_language=snowball_language,
            fields_to_parse=fields
        )

        # Send the data towards Elasticsearch
        ed = ElasticDocument("_all")
        ed.bulk_update(actions=actions)

        worker_object.task.complete()

        return worker_id

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise e
